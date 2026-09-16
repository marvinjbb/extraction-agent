"""Run one content-free Structured Outputs diagnostic against synthetic input."""

import asyncio
import json
import os
import sys
from importlib.metadata import version
from time import perf_counter

from openai import AsyncOpenAI, OpenAIError

from app import llm_extraction
from app.provider_schemas import (
    ProviderInvoice,
    ProviderInvoiceConversionError,
    provider_invoice_to_domain,
)
from app.schemas import Invoice

DEFAULT_MODEL = llm_extraction.DEFAULT_MODEL
INVOICE_EXTRACTION_INSTRUCTIONS = llm_extraction.INVOICE_EXTRACTION_INSTRUCTIONS
REQUEST_MAX_OUTPUT_TOKENS = getattr(llm_extraction, "INVOICE_MAX_OUTPUT_TOKENS", None)

SYNTHETIC_INVOICE = (
    "SYNTHETIC SAMPLE INVOICE - NOT A REAL TRANSACTION; "
    "Vendor: Example Test Supplies; Invoice Number: SYN-2026-0916; "
    "Invoice Date: 2026-09-16; Currency: USD; Subtotal: 100.00; "
    "Tax: 8.25; Total: 108.25"
)


def _safe_attr(value: object, name: str) -> object | None:
    """Read optional SDK metadata without allowing a property error to abort output."""
    try:
        return getattr(value, name, None)
    except Exception:  # pragma: no cover - defensive against future SDK properties
        return None


def _safe_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _safe_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def collect_safe_metadata(
    response: object,
    *,
    model: str,
    elapsed_ms: int,
    sdk_version: str,
) -> dict[str, object]:
    """Return allowlisted response structure without provider-generated content."""
    output = _safe_attr(response, "output")
    output_items = output if isinstance(output, list) else []
    items: list[dict[str, object]] = []
    parsed_content_present = False
    refusal_present = False

    for item in output_items:
        content = _safe_attr(item, "content")
        content_items = content if isinstance(content, list) else []
        safe_content: list[dict[str, object]] = []
        for content_item in content_items:
            content_type = _safe_string(_safe_attr(content_item, "type"))
            parsed_present = _safe_attr(content_item, "parsed") is not None
            item_refusal_present = (
                content_type == "refusal"
                or _safe_attr(content_item, "refusal") is not None
            )
            parsed_content_present = parsed_content_present or parsed_present
            refusal_present = refusal_present or item_refusal_present
            safe_content.append(
                {
                    "content_type": content_type,
                    "parsed_object_present": parsed_present,
                    "refusal_present": item_refusal_present,
                }
            )
        items.append(
            {
                "item_type": _safe_string(_safe_attr(item, "type")),
                "item_status": _safe_string(_safe_attr(item, "status")),
                "content": safe_content,
            }
        )

    output_parsed_supported = hasattr(type(response), "output_parsed") or hasattr(
        response, "output_parsed"
    )
    output_parsed_present = (
        output_parsed_supported and _safe_attr(response, "output_parsed") is not None
    )
    output_text = _safe_attr(response, "output_text")
    output_text_present = isinstance(output_text, str) and bool(output_text)

    incomplete_details = _safe_attr(response, "incomplete_details")
    error = _safe_attr(response, "error")
    usage = _safe_attr(response, "usage")
    output_token_details = (
        _safe_attr(usage, "output_tokens_details") if usage is not None else None
    )

    return {
        "openai_sdk_version": sdk_version,
        "configured_model": model,
        "elapsed_ms": elapsed_ms,
        "response_class": type(response).__name__,
        "response_status": _safe_string(_safe_attr(response, "status")),
        "response_id": _safe_string(_safe_attr(response, "id")),
        "response_error_present": error is not None,
        "response_error_type": type(error).__name__ if error is not None else None,
        "incomplete_details_present": incomplete_details is not None,
        "incomplete_reason": (
            _safe_string(_safe_attr(incomplete_details, "reason"))
            if incomplete_details is not None
            else None
        ),
        "output_item_count": len(output_items),
        "output_items": items,
        "output_parsed_supported": output_parsed_supported,
        "parsed_object_present": output_parsed_present,
        "parsed_content_present": parsed_content_present,
        "output_text_present": output_text_present,
        "refusal_present": refusal_present,
        "usage": {
            "input_tokens": _safe_integer(_safe_attr(usage, "input_tokens")),
            "output_tokens": _safe_integer(_safe_attr(usage, "output_tokens")),
            "reasoning_tokens": _safe_integer(
                _safe_attr(output_token_details, "reasoning_tokens")
            ),
            "total_tokens": _safe_integer(_safe_attr(usage, "total_tokens")),
        },
        "provider_request_id": _safe_string(_safe_attr(response, "_request_id")),
        "requested_max_output_tokens": REQUEST_MAX_OUTPUT_TOKENS,
    }


def collect_safe_request_metadata(
    *, model: str, timeout: float, reasoning_effort: str | None = None
) -> dict[str, object]:
    """Describe the request shape without input content or schema internals."""
    return {
        "model": model,
        "api_method": "responses.parse",
        "text_format_schema": ProviderInvoice.__name__,
        "max_output_tokens": REQUEST_MAX_OUTPUT_TOKENS,
        "reasoning_effort": reasoning_effort or "not explicitly supplied",
        "stream_enabled": False,
        "background_enabled": False,
        "store": "not explicitly supplied",
        "input_modality": "text",
        "timeout_seconds": timeout,
        "custom_base_url": bool(os.getenv("OPENAI_BASE_URL")),
    }


def classify_response(metadata: dict[str, object]) -> str:
    """Classify one response using only allowlisted structural metadata."""
    if metadata["response_error_present"]:
        return "G. provider/API error"
    if metadata["response_status"] == "incomplete":
        if metadata["incomplete_reason"] == "max_output_tokens":
            return "B. incomplete due to max_output_tokens"
        return "C. incomplete for another reason"
    if metadata["refusal_present"]:
        return "D. refusal"
    if metadata["response_status"] == "completed":
        if metadata["parsed_object_present"]:
            return "A. completed + parsed Invoice"
        if metadata["output_text_present"]:
            return "E. completed + output text but no parsed structured object"
        if metadata["output_item_count"] == 0:
            return "F. completed + empty output"
    return "H. another documented structural state"


def emit_response_diagnostic(
    response: object,
    *,
    model: str,
    elapsed_ms: int,
    sdk_version: str,
) -> int:
    """Print structure first, then safely attempt validation when possible."""
    metadata = collect_safe_metadata(
        response,
        model=model,
        elapsed_ms=elapsed_ms,
        sdk_version=sdk_version,
    )
    metadata["classification"] = classify_response(metadata)
    print(json.dumps(metadata, separators=(",", ":"), sort_keys=True), flush=True)

    parsed = _safe_attr(response, "output_parsed")
    if parsed is None:
        print(
            json.dumps(
                {
                    "invoice_validation_attempted": False,
                    "invoice_validation_succeeded": False,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            flush=True,
        )
        return 2

    try:
        provider_invoice = ProviderInvoice.model_validate(parsed)
        invoice = provider_invoice_to_domain(provider_invoice)
        Invoice.model_validate(invoice)
    except (TypeError, ValueError, ProviderInvoiceConversionError):
        print(
            json.dumps(
                {
                    "invoice_validation_attempted": True,
                    "invoice_validation_succeeded": False,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            flush=True,
        )
        return 3

    print(
        json.dumps(
            {
                "invoice_validation_attempted": True,
                "invoice_validation_succeeded": True,
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


async def main() -> None:
    """Print only allowlisted structural metadata about one provider response."""
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
    reasoning_effort = os.getenv("DIAGNOSTIC_REASONING_EFFORT")
    if reasoning_effort not in {None, "none"}:
        raise ValueError("DIAGNOSTIC_REASONING_EFFORT only accepts 'none'.")
    client = AsyncOpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=timeout,
        max_retries=0,
    )
    print(
        json.dumps(
            {
                "request_metadata": collect_safe_request_metadata(
                    model=model,
                    timeout=timeout,
                    reasoning_effort=reasoning_effort,
                )
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        flush=True,
    )
    request: dict[str, object] = {
        "model": model,
        "input": [
            {"role": "developer", "content": INVOICE_EXTRACTION_INSTRUCTIONS},
            {"role": "user", "content": SYNTHETIC_INVOICE},
        ],
        "text_format": ProviderInvoice,
    }
    if REQUEST_MAX_OUTPUT_TOKENS is not None:
        request["max_output_tokens"] = REQUEST_MAX_OUTPUT_TOKENS
    if reasoning_effort is not None:
        request["reasoning"] = {"effort": reasoning_effort}
    started = perf_counter()
    try:
        response = await client.responses.parse(**request)
    except OpenAIError as exc:
        diagnostic = {
            "openai_sdk_version": version("openai"),
            "configured_model": model,
            "elapsed_ms": round((perf_counter() - started) * 1000),
            "classification": "G. provider/API error",
            "provider_error_present": True,
            "provider_error_type": type(exc).__name__,
            "requested_max_output_tokens": REQUEST_MAX_OUTPUT_TOKENS,
        }
        print(json.dumps(diagnostic, separators=(",", ":"), sort_keys=True))
        raise SystemExit(4) from None

    exit_code = emit_response_diagnostic(
        response,
        model=model,
        elapsed_ms=round((perf_counter() - started) * 1000),
        sdk_version=version("openai"),
    )
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
