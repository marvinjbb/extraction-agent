import base64
import logging
import os
from typing import Protocol

from dotenv import load_dotenv
from openai import APITimeoutError, AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.image_processing import InvoiceImage
from app.schemas import Invoice

DEFAULT_MODEL = "gpt-5.4-nano"
DEFAULT_TIMEOUT_SECONDS = 30.0
INVOICE_EXTRACTION_INSTRUCTIONS = (
    "Extract invoice facts only from the supplied invoice content. Never invent "
    "missing values. Use null for missing scalar fields, an empty list when there "
    "are no line items, and warnings for unclear facts. Return invoice_date only "
    "as YYYY-MM-DD. Normalize unambiguous printed dates: 08/18/26 means "
    "2026-08-18; 20-AUG-2026 means 2026-08-20; and 18/08/2026 means "
    "2026-08-18. A numeric date such as 08/09/26 is ambiguous unless document "
    "context establishes its ordering; otherwise use null and add a warning. If no "
    "date is visible, use null. If a visible date is partially unreadable or cannot "
    "be safely normalized, use null and add a warning. Never copy receipt date "
    "formats such as MM/DD/YY, DD/MM/YYYY, or DD-MMM-YYYY directly into "
    "invoice_date. Use a three-letter uppercase ISO currency code only when the "
    "document supports it. Do not calculate values that are not explicitly present."
)
logger = logging.getLogger(__name__)


class InvoiceExtractor(Protocol):
    """Application-owned boundary for structured invoice extraction."""

    async def extract(self, document_text: str) -> Invoice:
        """Return schema-valid invoice facts from document text."""


class VisionInvoiceExtractor(Protocol):
    """Application-owned boundary for structured extraction from page images."""

    async def extract_images(self, images: list[InvoiceImage]) -> Invoice:
        """Return schema-valid invoice facts from one or more images."""


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


def _log_validation_failure(
    stage: str, error: ValidationError | TypeError
) -> None:
    """Log schema diagnostics without rejected values or provider content."""
    if isinstance(error, ValidationError):
        for detail in error.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        ):
            field = ".".join(str(part) for part in detail["loc"]) or "<root>"
            logger.warning(
                "Invoice structured-output validation failed "
                "stage=%s field=%s error_type=%s reason=%s",
                stage,
                field,
                detail["type"],
                detail["msg"],
            )
        return

    logger.warning(
        "Invoice structured-output validation failed "
        "stage=%s field=<root> error_type=type_error "
        "reason=Result could not be validated as an Invoice",
        stage,
    )


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

        return await self._parse(
            client,
            model,
            [{"role": "user", "content": document_text}],
        )

    async def extract_images(self, images: list[InvoiceImage]) -> Invoice:
        client, model = self._configured_client()
        content: list[dict[str, str]] = [
            {
                "type": "input_text",
                "text": "Extract the invoice facts visible in these page images.",
            }
        ]
        content.extend(
            {
                "type": "input_image",
                "image_url": (
                    f"data:{image.media_type};base64,"
                    f"{base64.b64encode(image.content).decode('ascii')}"
                ),
                "detail": "high",
            }
            for image in images
        )
        return await self._parse(
            client,
            model,
            [{"role": "user", "content": content}],
        )

    async def _parse(
        self,
        client: AsyncOpenAI,
        model: str,
        user_input: list[dict[str, object]],
    ) -> Invoice:

        try:
            response = await client.responses.parse(
                model=model,
                input=[
                    {
                        "role": "developer",
                        "content": INVOICE_EXTRACTION_INSTRUCTIONS,
                    },
                    *user_input,
                ],
                text_format=Invoice,
            )
        except APITimeoutError as exc:
            raise LLMTimeoutError("The invoice extraction provider timed out.") from exc
        except ValidationError as exc:
            _log_validation_failure("responses.parse", exc)
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
            _log_validation_failure("Invoice.model_validate", exc)
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


def get_vision_invoice_extractor() -> VisionInvoiceExtractor:
    """Build the default vision-capable provider adapter."""
    return OpenAIInvoiceExtractor()
