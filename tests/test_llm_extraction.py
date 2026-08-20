import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError
from pydantic import ValidationError

from app.image_processing import InvoiceImage
from app.llm_extraction import (
    INVOICE_EXTRACTION_INSTRUCTIONS,
    InvalidLLMOutputError,
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
    OpenAIInvoiceExtractor,
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
    assert "Return invoice_date only as YYYY-MM-DD" in (
        INVOICE_EXTRACTION_INSTRUCTIONS
    )
    assert (
        "Never copy receipt date formats such as MM/DD/YY, DD/MM/YYYY, or "
        "DD-MMM-YYYY directly into invoice_date"
        in INVOICE_EXTRACTION_INSTRUCTIONS
    )


def build_client(output: object) -> SimpleNamespace:
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=output))
    return SimpleNamespace(responses=SimpleNamespace(parse=parse))


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
    assert call.kwargs["input"][0]["content"] == INVOICE_EXTRACTION_INSTRUCTIONS


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
    caplog: pytest.LogCaptureFixture,
) -> None:
    extractor = OpenAIInvoiceExtractor(
        client=build_client({"currency": "secret-rejected-value"})
    )

    with caplog.at_level(logging.WARNING, logger="app.llm_extraction"):
        with pytest.raises(InvalidLLMOutputError, match="invalid structured result"):
            asyncio.run(extractor.extract("private invoice contents"))

    assert "stage=Invoice.model_validate" in caplog.text
    assert "field=currency" in caplog.text
    assert "error_type=string_pattern_mismatch" in caplog.text
    assert "reason=String should match pattern" in caplog.text
    assert "secret-rejected-value" not in caplog.text
    assert "private invoice contents" not in caplog.text


def test_responses_parse_failure_logs_safe_field_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
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

    with caplog.at_level(logging.WARNING, logger="app.llm_extraction"):
        with pytest.raises(InvalidLLMOutputError, match="invalid structured result"):
            asyncio.run(extractor.extract("private provider document"))

    assert "stage=responses.parse" in caplog.text
    assert "field=currency" in caplog.text
    assert "error_type=string_pattern_mismatch" in caplog.text
    assert "reason=String should match pattern" in caplog.text
    assert "secret-provider-value" not in caplog.text
    assert "private provider document" not in caplog.text


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
