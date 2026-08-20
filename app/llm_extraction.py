import os
from typing import Protocol

from dotenv import load_dotenv
from openai import APITimeoutError, AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.schemas import Invoice

DEFAULT_MODEL = "gpt-5.4-nano"
DEFAULT_TIMEOUT_SECONDS = 30.0


class InvoiceExtractor(Protocol):
    """Application-owned boundary for structured invoice extraction."""

    async def extract(self, document_text: str) -> Invoice:
        """Return schema-valid invoice facts from document text."""


class LLMExtractionError(Exception):
    """Base error for failures at the LLM extraction boundary."""


class LLMConfigurationError(LLMExtractionError):
    """Raised when required local/provider configuration is invalid."""


class LLMTimeoutError(LLMExtractionError):
    """Raised when the provider does not respond before the deadline."""


class LLMProviderError(LLMExtractionError):
    """Raised when the provider cannot complete the request."""


class InvalidLLMOutputError(LLMExtractionError):
    """Raised when provider output does not satisfy the Invoice contract."""


class OpenAIInvoiceExtractor:
    """OpenAI adapter that returns the application-owned Invoice model."""

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

    async def extract(self, document_text: str) -> Invoice:
        client, model = self._configured_client()

        try:
            response = await client.responses.parse(
                model=model,
                input=[
                    {
                        "role": "developer",
                        "content": (
                            "Extract invoice facts only from the supplied document "
                            "text. Never invent missing values. Use null for missing "
                            "scalar fields, an empty list when no line items are "
                            "present, and warnings for ambiguous or uncertain facts. "
                            "Use a three-letter uppercase ISO currency code only when "
                            "the document supports it. Do not calculate values that "
                            "are not explicitly present."
                        ),
                    },
                    {"role": "user", "content": document_text},
                ],
                text_format=Invoice,
            )
        except APITimeoutError as exc:
            raise LLMTimeoutError("The invoice extraction provider timed out.") from exc
        except ValidationError as exc:
            raise InvalidLLMOutputError(
                "The invoice extraction provider returned an invalid structured result."
            ) from exc
        except OpenAIError as exc:
            raise LLMProviderError(
                "The invoice extraction provider could not complete the request."
            ) from exc

        if response.output_parsed is None:
            raise InvalidLLMOutputError(
                "The invoice extraction provider returned no structured result."
            )

        try:
            return Invoice.model_validate(response.output_parsed)
        except (TypeError, ValidationError) as exc:
            raise InvalidLLMOutputError(
                "The invoice extraction provider returned an invalid structured result."
            ) from exc

    def _configured_client(self) -> tuple[AsyncOpenAI, str]:
        if self._client is not None:
            return self._client, self._model or DEFAULT_MODEL

        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMConfigurationError(
                "Invoice extraction is not configured on this server."
            )

        model = self._model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        timeout_seconds = self._timeout_seconds or _read_timeout_seconds()
        return AsyncOpenAI(api_key=api_key, timeout=timeout_seconds), model


def _read_timeout_seconds() -> float:
    raw_value = os.getenv("OPENAI_TIMEOUT_SECONDS")
    if raw_value is None:
        return DEFAULT_TIMEOUT_SECONDS

    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise LLMConfigurationError(
            "OPENAI_TIMEOUT_SECONDS must be a positive number."
        ) from exc

    if timeout <= 0:
        raise LLMConfigurationError(
            "OPENAI_TIMEOUT_SECONDS must be a positive number."
        )
    return timeout


def get_invoice_extractor() -> InvoiceExtractor:
    """Build the default provider adapter for FastAPI dependency injection."""
    return OpenAIInvoiceExtractor()
