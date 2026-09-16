import base64
import os
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Protocol

from dotenv import load_dotenv
from openai import APITimeoutError, AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.image_processing import InvoiceImage
from app.observability import log_event
from app.provider_schemas import (
    ProviderInvoice,
    ProviderInvoiceConversionError,
    provider_invoice_to_domain,
)
from app.schemas import Invoice

DEFAULT_MODEL = "gpt-5.4-nano"
DEFAULT_TIMEOUT_SECONDS = 30.0
INVOICE_MAX_OUTPUT_TOKENS = 4096
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
    " Return monetary values and quantities as plain decimal strings without "
    "currency symbols or thousands separators."
)


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


@dataclass(frozen=True)
class ProviderResponseStructure:
    """Content-free metadata describing one parsed provider response."""

    response_type: str
    status: str | None
    output_count: int
    output_item_types: tuple[str, ...]
    content_item_types: tuple[str, ...]
    parsed_present: bool
    output_parsed_supported: bool
    refusal_present: bool
    incomplete_category: str | None
    provider_request_id: str | None

    def as_safe_dict(self) -> dict[str, object]:
        return asdict(self)


def describe_provider_response(response: Any) -> ProviderResponseStructure:
    """Return structural metadata without reading or exposing provider content."""
    output = getattr(response, "output", None)
    output_items = output if isinstance(output, list) else []
    output_types: list[str] = []
    content_types: list[str] = []
    parsed_present = False
    refusal_present = False

    for item in output_items:
        item_type = getattr(item, "type", None)
        if isinstance(item_type, str):
            output_types.append(item_type)
        content = getattr(item, "content", None)
        if not isinstance(content, list):
            continue
        for content_item in content:
            content_type = getattr(content_item, "type", None)
            if isinstance(content_type, str):
                content_types.append(content_type)
            if getattr(content_item, "parsed", None) is not None:
                parsed_present = True
            if content_type == "refusal":
                refusal_present = True

    output_parsed_supported = hasattr(type(response), "output_parsed") or hasattr(
        response, "output_parsed"
    )
    if output_parsed_supported and getattr(response, "output_parsed", None) is not None:
        parsed_present = True

    incomplete_details = getattr(response, "incomplete_details", None)
    incomplete_reason = getattr(incomplete_details, "reason", None)
    provider_request_id = getattr(response, "_request_id", None)

    return ProviderResponseStructure(
        response_type=type(response).__name__,
        status=_safe_string(getattr(response, "status", None)),
        output_count=len(output_items),
        output_item_types=tuple(output_types),
        content_item_types=tuple(content_types),
        parsed_present=parsed_present,
        output_parsed_supported=output_parsed_supported,
        refusal_present=refusal_present,
        incomplete_category=_safe_string(incomplete_reason),
        provider_request_id=_safe_string(provider_request_id),
    )


def _safe_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _log_validation_failure(
    stage: str,
    error: ValidationError | TypeError | ProviderInvoiceConversionError,
) -> None:
    """Log schema diagnostics without rejected values or provider content."""
    if isinstance(error, ValidationError):
        for detail in error.errors(
            include_url=False,
            include_context=False,
            include_input=False,
        ):
            field = ".".join(str(part) for part in detail["loc"]) or "<root>"
            log_event(
                "structured_output_validation_failed",
                component="invoice_extraction",
                outcome="failed",
                stage=stage,
                field=field,
                error_type=detail["type"],
            )
        return

    log_event(
        "structured_output_validation_failed",
        component="invoice_extraction",
        outcome="failed",
        stage=stage,
        field="<root>",
        error_type=type(error).__name__,
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
        started = perf_counter()
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
                text_format=ProviderInvoice,
                max_output_tokens=INVOICE_MAX_OUTPUT_TOKENS,
            )
        except APITimeoutError as exc:
            _log_provider_call(
                started, model, "timeout", "provider_timeout", "invoice_extraction"
            )
            raise LLMTimeoutError("The invoice extraction provider timed out.") from exc
        except ValidationError as exc:
            _log_provider_call(
                started,
                model,
                "failed",
                "invalid_structured_output",
                "invoice_extraction",
            )
            _log_validation_failure("responses.parse", exc)
            raise InvalidLLMOutputError(
                "The invoice extraction provider returned an invalid structured result."
            ) from exc
        except OpenAIError as exc:
            _log_provider_call(
                started, model, "failed", "provider_error", "invoice_extraction"
            )
            raise LLMProviderError(
                "The invoice extraction provider could not complete the request."
            ) from exc

        response_structure = describe_provider_response(response)
        if response_structure.status == "incomplete":
            _log_provider_call(
                started,
                model,
                "failed",
                "incomplete_response",
                "invoice_extraction",
                response_structure=response_structure,
            )
            raise InvalidLLMOutputError(
                "The invoice extraction provider returned an incomplete response."
            )

        if response_structure.refusal_present:
            _log_provider_call(
                started,
                model,
                "failed",
                "provider_refusal",
                "invoice_extraction",
                response_structure=response_structure,
            )
            raise InvalidLLMOutputError(
                "The invoice extraction provider refused the structured request."
            )

        if response.output_parsed is None:
            _log_provider_call(
                started,
                model,
                "failed",
                "missing_structured_output",
                "invoice_extraction",
                response_structure=response_structure,
            )
            raise InvalidLLMOutputError(
                "The invoice extraction provider returned no structured result."
            )

        try:
            provider_invoice = ProviderInvoice.model_validate(response.output_parsed)
        except (TypeError, ValidationError) as exc:
            _log_provider_call(
                started,
                model,
                "failed",
                "invalid_structured_output",
                "invoice_extraction",
            )
            _log_validation_failure("ProviderInvoice.model_validate", exc)
            raise InvalidLLMOutputError(
                "The invoice extraction provider returned an invalid structured result."
            ) from exc

        try:
            invoice = provider_invoice_to_domain(provider_invoice)
        except ProviderInvoiceConversionError as exc:
            _log_provider_call(
                started,
                model,
                "failed",
                "invalid_structured_output",
                "invoice_extraction",
                response_structure=response_structure,
                conversion_success=False,
                domain_validation_success=False,
            )
            _log_validation_failure("provider_invoice_to_domain", exc)
            raise InvalidLLMOutputError(
                "The invoice extraction provider returned an invalid structured result."
            ) from exc

        _log_provider_call(
            started,
            model,
            "success",
            None,
            "invoice_extraction",
            response_structure=response_structure,
            conversion_success=True,
            domain_validation_success=True,
        )
        return invoice

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
        return AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=0,
        ), model


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
        raise LLMConfigurationError("OPENAI_TIMEOUT_SECONDS must be a positive number.")
    return timeout


def _log_provider_call(
    started: float,
    model: str,
    outcome: str,
    error_category: str | None,
    operation: str,
    *,
    response_structure: ProviderResponseStructure | None = None,
    conversion_success: bool | None = None,
    domain_validation_success: bool | None = None,
) -> None:
    log_event(
        "provider_call_completed",
        component="openai",
        provider_operation=operation,
        model=model,
        outcome=outcome,
        error_category=error_category,
        duration_ms=round((perf_counter() - started) * 1000, 2),
        provider_request_id=(
            response_structure.provider_request_id if response_structure else None
        ),
        response_status=response_structure.status if response_structure else None,
        parsed_present=(
            response_structure.parsed_present if response_structure else None
        ),
        conversion_success=conversion_success,
        domain_validation_success=domain_validation_success,
    )


def get_invoice_extractor() -> InvoiceExtractor:
    """Build the default provider adapter for FastAPI dependency injection."""
    return OpenAIInvoiceExtractor()


def get_vision_invoice_extractor() -> VisionInvoiceExtractor:
    """Build the default vision-capable provider adapter."""
    return OpenAIInvoiceExtractor()
