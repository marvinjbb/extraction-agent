import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError
from openai.types.responses import (
    ParsedResponse,
    ParsedResponseOutputMessage,
    ParsedResponseOutputText,
)
from pydantic import ValidationError

from app.image_processing import InvoiceImage
from app.llm_extraction import (
    INVOICE_EXTRACTION_INSTRUCTIONS,
    INVOICE_MAX_OUTPUT_TOKENS,
    InvalidLLMOutputError,
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
    OpenAIInvoiceExtractor,
    describe_provider_response,
)
from app.schemas import Invoice


@pytest.mark.parametrize(
    "required_instruction",
    [
        "08/18/26 means 2026-08-18",
        "20-AUG-2026 means 2026-08-20",
        "18/08/2026 means 2026-08-18",
        "08/09/26 is ambiguous unless document context establishes its ordering; "
        "otherwise use null and add a warning",
        "If no date is visible, use null",
        "partially unreadable or cannot be safely normalized, use null and add a "
        "warning",
    ],
)
def test_date_normalization_instruction_regressions(
    required_instruction: str,
) -> None:
    assert required_instruction in INVOICE_EXTRACTION_INSTRUCTIONS


def test_date_instructions_forbid_copying_receipt_formats() -> None:
    assert "Return invoice_date only as YYYY-MM-DD" in (INVOICE_EXTRACTION_INSTRUCTIONS)
    assert (
        "Never copy receipt date formats such as MM/DD/YY, DD/MM/YYYY, or "
        "DD-MMM-YYYY directly into invoice_date" in INVOICE_EXTRACTION_INSTRUCTIONS
    )


def build_client(output: object) -> SimpleNamespace:
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=output))
    return SimpleNamespace(responses=SimpleNamespace(parse=parse))


def build_response_client(response: object) -> SimpleNamespace:
    parse = AsyncMock(return_value=response)
    return SimpleNamespace(responses=SimpleNamespace(parse=parse))


def build_sdk_response(parsed: object) -> ParsedResponse[object]:
    content = ParsedResponseOutputText[object].model_construct(
        annotations=[],
        text="content intentionally not inspected",
        type="output_text",
        parsed=parsed,
    )
    message = ParsedResponseOutputMessage[object].model_construct(
        id="message-safe-id",
        content=[content],
        role="assistant",
        status="completed",
        type="message",
    )
    return ParsedResponse[object].model_construct(
        id="response-safe-id",
        output=[message],
        status="completed",
        incomplete_details=None,
    )


def test_provider_structure_describes_sdk_nested_parsed_invoice() -> None:
    response = build_sdk_response(Invoice(vendor="private value"))

    structure = describe_provider_response(response)

    assert response.output_parsed == Invoice(vendor="private value")
    assert structure.output_parsed_supported is True
    assert structure.parsed_present is True
    assert structure.output_item_types == ("message",)
    assert structure.content_item_types == ("output_text",)
    assert "private value" not in repr(structure)


def test_provider_structure_supports_top_level_output_parsed() -> None:
    response = SimpleNamespace(
        output_parsed=Invoice(vendor="private value"),
        output=[],
        status="completed",
        incomplete_details=None,
    )

    structure = describe_provider_response(response)

    assert structure.output_parsed_supported is True
    assert structure.parsed_present is True
    assert "private value" not in repr(structure)


def test_provider_structure_detects_refusal_without_exposing_text() -> None:
    response = SimpleNamespace(
        output_parsed=None,
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="refusal", refusal="private refusal")],
            )
        ],
        status="completed",
        incomplete_details=None,
    )

    structure = describe_provider_response(response)

    assert structure.refusal_present is True
    assert structure.parsed_present is False
    assert "private refusal" not in repr(structure)


def test_provider_structure_detects_incomplete_response() -> None:
    response = SimpleNamespace(
        output_parsed=None,
        output=[],
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )

    structure = describe_provider_response(response)

    assert structure.status == "incomplete"
    assert structure.incomplete_category == "max_output_tokens"
    assert structure.parsed_present is False


def test_provider_structure_detects_completed_response_without_parsed_output() -> None:
    response = SimpleNamespace(
        output_parsed=None,
        output=[SimpleNamespace(type="reasoning")],
        status="completed",
        incomplete_details=None,
    )

    structure = describe_provider_response(response)

    assert structure.output_item_types == ("reasoning",)
    assert structure.parsed_present is False


def test_provider_structure_does_not_treat_malformed_parsed_value_as_validated() -> (
    None
):
    response = build_sdk_response({"currency": "not-a-code"})
    structure = describe_provider_response(response)

    assert structure.parsed_present is True
    with pytest.raises(ValidationError):
        Invoice.model_validate(response.output_parsed)


def test_openai_adapter_returns_validated_invoice() -> None:
    client = build_client(
        {
            "vendor": "Acme Supplies",
            "invoice_number": "INV-1001",
            "invoice_date": "2026-08-20",
            "currency": "USD",
            "subtotal": "100.00",
            "tax": "8.25",
            "total": "108.25",
            "line_items": [],
            "warnings": [],
        }
    )
    extractor = OpenAIInvoiceExtractor(client=client, model="test-model")

    invoice = asyncio.run(extractor.extract("Acme Supplies invoice INV-1001"))

    assert isinstance(invoice, Invoice)
    assert invoice.vendor == "Acme Supplies"
    call = client.responses.parse.await_args
    assert call.kwargs["model"] == "test-model"
    assert call.kwargs["text_format"] is Invoice
    assert call.kwargs["max_output_tokens"] == INVOICE_MAX_OUTPUT_TOKENS
    assert call.kwargs["input"][0]["content"] == INVOICE_EXTRACTION_INSTRUCTIONS


def test_openai_adapter_accepts_sdk_nested_parsed_invoice() -> None:
    expected = Invoice(vendor="Acme Supplies")
    client = build_response_client(build_sdk_response(expected))
    extractor = OpenAIInvoiceExtractor(client=client, model="test-model")

    invoice = asyncio.run(extractor.extract("synthetic invoice"))

    assert invoice == expected


def test_openai_adapter_rejects_provider_refusal() -> None:
    response = SimpleNamespace(
        output_parsed=None,
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="refusal", refusal="private refusal")],
            )
        ],
        status="completed",
        incomplete_details=None,
    )
    extractor = OpenAIInvoiceExtractor(client=build_response_client(response))

    with pytest.raises(InvalidLLMOutputError, match="refused"):
        asyncio.run(extractor.extract("private invoice"))


def test_openai_adapter_rejects_incomplete_max_output_tokens_response() -> None:
    response = SimpleNamespace(
        output_parsed=None,
        output=[],
        status="incomplete",
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )
    extractor = OpenAIInvoiceExtractor(client=build_response_client(response))

    with pytest.raises(InvalidLLMOutputError, match="incomplete response"):
        asyncio.run(extractor.extract("private invoice"))


def test_openai_adapter_sends_images_as_multimodal_input() -> None:
    client = build_client(
        {
            "vendor": "Vision Vendor",
            "line_items": [],
            "warnings": [],
        }
    )
    extractor = OpenAIInvoiceExtractor(client=client, model="test-model")

    invoice = asyncio.run(
        extractor.extract_images([InvoiceImage(content=b"jpeg-bytes")])
    )

    assert invoice.vendor == "Vision Vendor"
    user_content = client.responses.parse.await_args.kwargs["input"][1]["content"]
    assert user_content[0]["type"] == "input_text"
    assert user_content[1]["type"] == "input_image"
    assert user_content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert user_content[1]["detail"] == "high"


def test_openai_adapter_rejects_missing_structured_output() -> None:
    extractor = OpenAIInvoiceExtractor(client=build_client(None))

    with pytest.raises(InvalidLLMOutputError, match="no structured result"):
        asyncio.run(extractor.extract("invoice text"))


def test_final_validation_failure_logs_safe_field_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.llm_extraction.log_event",
        lambda event, **fields: events.append((event, fields)),
    )
    extractor = OpenAIInvoiceExtractor(
        client=build_client({"currency": "secret-rejected-value"})
    )

    with pytest.raises(InvalidLLMOutputError, match="invalid structured result"):
        asyncio.run(extractor.extract("private invoice contents"))

    validation = next(
        fields
        for event, fields in events
        if event == "structured_output_validation_failed"
    )
    assert validation["stage"] == "Invoice.model_validate"
    assert validation["field"] == "currency"
    assert validation["error_type"] == "string_pattern_mismatch"
    assert "secret-rejected-value" not in repr(events)
    assert "private invoice contents" not in repr(events)


def test_responses_parse_failure_logs_safe_field_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "app.llm_extraction.log_event",
        lambda event, **fields: events.append((event, fields)),
    )
    client = build_client(None)
    client.responses.parse.side_effect = ValidationError.from_exception_data(
        "Invoice",
        [
            {
                "type": "string_pattern_mismatch",
                "loc": ("currency",),
                "input": "secret-provider-value",
                "ctx": {"pattern": "^[A-Z]{3}$"},
            }
        ],
    )
    extractor = OpenAIInvoiceExtractor(client=client)

    with pytest.raises(InvalidLLMOutputError, match="invalid structured result"):
        asyncio.run(extractor.extract("private provider document"))

    validation = next(
        fields
        for event, fields in events
        if event == "structured_output_validation_failed"
    )
    assert validation["stage"] == "responses.parse"
    assert validation["field"] == "currency"
    assert validation["error_type"] == "string_pattern_mismatch"
    assert "secret-provider-value" not in repr(events)
    assert "private provider document" not in repr(events)


def test_openai_adapter_rejects_missing_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("app.llm_extraction.load_dotenv", lambda: None)
    extractor = OpenAIInvoiceExtractor()

    with pytest.raises(LLMConfigurationError, match="not configured"):
        asyncio.run(extractor.extract("invoice text"))


def test_openai_adapter_maps_timeout() -> None:
    client = build_client(None)
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    client.responses.parse.side_effect = APITimeoutError(request=request)
    extractor = OpenAIInvoiceExtractor(client=client)

    with pytest.raises(LLMTimeoutError, match="timed out"):
        asyncio.run(extractor.extract("invoice text"))


def test_openai_adapter_maps_provider_failure() -> None:
    client = build_client(None)
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    client.responses.parse.side_effect = APIConnectionError(request=request)
    extractor = OpenAIInvoiceExtractor(client=client)

    with pytest.raises(LLMProviderError, match="could not complete"):
        asyncio.run(extractor.extract("invoice text"))
