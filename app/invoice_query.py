import json
import os
from typing import Protocol

from dotenv import load_dotenv
from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.llm_extraction import (
    DEFAULT_MODEL,
    InvalidLLMOutputError,
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
    _read_timeout_seconds,
)
from app.schemas import Invoice

INVOICE_QUERY_INSTRUCTIONS = (
    "You answer questions about one invoice.\n\n"
    "Use only the supplied validated invoice data.\n"
    "Do not use outside knowledge to invent invoice facts.\n"
    "If the answer cannot be determined from the provided invoice data, "
    "explicitly say that the information is not available in this invoice.\n"
    "Be concise and factual. Use plain text without Markdown formatting."
)


class InvoiceQueryService(Protocol):
    """Application boundary for grounded questions about one invoice."""

    async def answer(self, question: str, invoice: Invoice) -> str:
        """Answer one question using only the validated invoice."""


class OpenAIInvoiceQueryService:
    """OpenAI adapter for independent, invoice-grounded questions."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def answer(self, question: str, invoice: Invoice) -> str:
        client, model = self._configured_client()
        invoice_json = json.dumps(
            invoice.model_dump(mode="json"), separators=(",", ":")
        )

        try:
            response = await client.responses.create(
                model=model,
                instructions=INVOICE_QUERY_INSTRUCTIONS,
                input=(
                    f"Validated invoice JSON:\n{invoice_json}\n\n"
                    f"Question:\n{question}"
                ),
            )
        except APITimeoutError as exc:
            raise LLMTimeoutError("The invoice query provider timed out.") from exc
        except OpenAIError as exc:
            raise LLMProviderError(
                "The invoice query provider could not complete the request."
            ) from exc

        answer = getattr(response, "output_text", None)
        if not isinstance(answer, str) or not answer.strip():
            raise InvalidLLMOutputError(
                "The invoice query provider returned an invalid answer."
            )
        return answer.strip()

    def _configured_client(self) -> tuple[AsyncOpenAI, str]:
        if self._client is not None:
            return self._client, self._model or DEFAULT_MODEL

        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMConfigurationError(
                "Invoice querying is not configured on this server."
            )

        model = self._model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        timeout_seconds = self._timeout_seconds or _read_timeout_seconds()
        return AsyncOpenAI(api_key=api_key, timeout=timeout_seconds), model


def get_invoice_query_service() -> InvoiceQueryService:
    """Build the default provider adapter for FastAPI dependency injection."""
    return OpenAIInvoiceQueryService()
