import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError, APITimeoutError

from app.invoice_query import (
    INVOICE_QUERY_INSTRUCTIONS,
    OpenAIInvoiceQueryService,
    get_invoice_query_service,
)
from app.llm_extraction import (
    InvalidLLMOutputError,
    LLMProviderError,
    LLMTimeoutError,
)
from app.main import app
from app.schemas import Invoice

client = TestClient(app)

INVOICE_PAYLOAD = {
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


class FakeQueryService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.received: tuple[str, Invoice] | None = None

    async def answer(self, question: str, invoice: Invoice) -> str:
        self.received = (question, invoice)
        if self.error:
            raise self.error
        return "The invoice total is USD 108.25."


@pytest.fixture(autouse=True)
def use_fake_query_service() -> FakeQueryService:
    service = FakeQueryService()
    app.dependency_overrides[get_invoice_query_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


def test_valid_question_returns_grounded_answer(
    use_fake_query_service: FakeQueryService,
) -> None:
    response = client.post(
        "/extractions/invoice/query",
        json={"question": "What is the total?", "invoice": INVOICE_PAYLOAD},
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "The invoice total is USD 108.25."}
    assert use_fake_query_service.received is not None
    question, invoice = use_fake_query_service.received
    assert question == "What is the total?"
    assert invoice.total is not None
    assert "OPENAI_API_KEY" not in response.text


@pytest.mark.parametrize("question", ["", "   "])
def test_empty_question_is_rejected(question: str) -> None:
    response = client.post(
        "/extractions/invoice/query",
        json={"question": question, "invoice": INVOICE_PAYLOAD},
    )

    assert response.status_code == 422


def test_oversized_question_is_rejected() -> None:
    response = client.post(
        "/extractions/invoice/query",
        json={"question": "x" * 501, "invoice": INVOICE_PAYLOAD},
    )

    assert response.status_code == 422


def test_existing_invoice_schema_is_enforced() -> None:
    invalid_invoice = {**INVOICE_PAYLOAD, "currency": "dollars"}
    response = client.post(
        "/extractions/invoice/query",
        json={"question": "What is the currency?", "invoice": invalid_invoice},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (LLMProviderError("safe provider failure"), 502),
        (LLMTimeoutError("safe provider timeout"), 504),
        (InvalidLLMOutputError("safe invalid answer"), 502),
    ],
)
def test_query_failures_map_to_safe_http_errors(
    error: Exception,
    status_code: int,
) -> None:
    app.dependency_overrides[get_invoice_query_service] = lambda: FakeQueryService(
        error
    )

    response = client.post(
        "/extractions/invoice/query",
        json={"question": "What is the total?", "invoice": INVOICE_PAYLOAD},
    )

    assert response.status_code == status_code
    assert response.json() == {"detail": str(error)}


def build_openai_client(output_text: object) -> SimpleNamespace:
    create = AsyncMock(return_value=SimpleNamespace(output_text=output_text))
    return SimpleNamespace(responses=SimpleNamespace(create=create))


def test_openai_query_includes_grounding_instructions_and_invoice() -> None:
    openai_client = build_openai_client("The vendor is Acme Supplies.")
    service = OpenAIInvoiceQueryService(client=openai_client, model="test-model")

    answer = asyncio.run(
        service.answer("Who is the vendor?", Invoice.model_validate(INVOICE_PAYLOAD))
    )

    assert answer == "The vendor is Acme Supplies."
    call = openai_client.responses.create.await_args
    assert call.kwargs["instructions"] == INVOICE_QUERY_INSTRUCTIONS
    assert "Use only the supplied validated invoice data" in INVOICE_QUERY_INSTRUCTIONS
    assert "plain text without Markdown" in INVOICE_QUERY_INSTRUCTIONS
    assert '"vendor":"Acme Supplies"' in call.kwargs["input"]
    assert "Who is the vendor?" in call.kwargs["input"]


def test_openai_query_maps_timeout_and_provider_failure() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    timeout_client = build_openai_client(None)
    timeout_client.responses.create.side_effect = APITimeoutError(request=request)
    provider_client = build_openai_client(None)
    provider_client.responses.create.side_effect = APIConnectionError(request=request)

    with pytest.raises(LLMTimeoutError):
        asyncio.run(
            OpenAIInvoiceQueryService(client=timeout_client).answer(
                "Total?", Invoice.model_validate(INVOICE_PAYLOAD)
            )
        )
    with pytest.raises(LLMProviderError):
        asyncio.run(
            OpenAIInvoiceQueryService(client=provider_client).answer(
                "Total?", Invoice.model_validate(INVOICE_PAYLOAD)
            )
        )


def test_openai_query_rejects_malformed_answer() -> None:
    service = OpenAIInvoiceQueryService(client=build_openai_client(None))

    with pytest.raises(InvalidLLMOutputError):
        asyncio.run(
            service.answer("Total?", Invoice.model_validate(INVOICE_PAYLOAD))
        )
