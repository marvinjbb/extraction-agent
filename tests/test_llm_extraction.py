import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from app.llm_extraction import (
    InvalidLLMOutputError,
    LLMProviderError,
    LLMTimeoutError,
    OpenAIInvoiceExtractor,
)
from app.schemas import Invoice


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


def test_openai_adapter_rejects_missing_structured_output() -> None:
    extractor = OpenAIInvoiceExtractor(client=build_client(None))

    with pytest.raises(InvalidLLMOutputError, match="no structured result"):
        asyncio.run(extractor.extract("invoice text"))


def test_openai_adapter_rejects_invalid_structured_output() -> None:
    extractor = OpenAIInvoiceExtractor(
        client=build_client({"currency": "dollars"})
    )

    with pytest.raises(InvalidLLMOutputError, match="invalid structured result"):
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
