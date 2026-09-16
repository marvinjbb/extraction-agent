import json
from types import SimpleNamespace

import pytest

from app.provider_schemas import ProviderInvoice
from scripts.diagnose_structured_response import (
    collect_safe_request_metadata,
    emit_response_diagnostic,
)


def response(
    *,
    status: str | None = "completed",
    output: list[object] | None = None,
    parsed: object = None,
    incomplete_reason: str | None = None,
    error: object = None,
    usage: object = None,
    include_optional: bool = True,
) -> object:
    values: dict[str, object] = {
        "status": status,
        "output": [] if output is None else output,
        "output_parsed": parsed,
        "error": error,
    }
    if include_optional:
        values.update(
            {
                "id": "safe-response-id",
                "incomplete_details": (
                    SimpleNamespace(reason=incomplete_reason)
                    if incomplete_reason is not None
                    else None
                ),
                "usage": usage,
                "_request_id": "safe-request-id",
            }
        )
    return SimpleNamespace(**values)


def run_and_read(
    capsys: pytest.CaptureFixture[str], value: object
) -> tuple[int, dict, dict]:
    result = emit_response_diagnostic(
        value,
        model="test-model",
        elapsed_ms=123,
        sdk_version="test-sdk",
    )
    lines = capsys.readouterr().out.splitlines()
    return result, json.loads(lines[0]), json.loads(lines[1])


def test_diagnostic_reports_completed_parsed_invoice(
    capsys: pytest.CaptureFixture[str],
) -> None:
    invoice = ProviderInvoice(vendor="private vendor", total="108.25")
    content = SimpleNamespace(type="output_text", parsed=invoice, text="private text")
    item = SimpleNamespace(type="message", status="completed", content=[content])
    result, metadata, validation = run_and_read(
        capsys, response(output=[item], parsed=invoice)
    )

    assert result == 0
    assert metadata["classification"] == "A. completed + parsed Invoice"
    assert metadata["parsed_object_present"] is True
    assert validation["invoice_validation_succeeded"] is True
    assert "private vendor" not in json.dumps(metadata)
    assert "private text" not in json.dumps(metadata)


def test_diagnostic_reports_incomplete_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    usage = SimpleNamespace(
        input_tokens=120,
        output_tokens=4096,
        total_tokens=4216,
        output_tokens_details=SimpleNamespace(reasoning_tokens=4000),
    )
    result, metadata, validation = run_and_read(
        capsys,
        response(
            status="incomplete",
            incomplete_reason="max_output_tokens",
            usage=usage,
        ),
    )

    assert result == 2
    assert metadata["classification"] == "B. incomplete due to max_output_tokens"
    assert metadata["usage"] == {
        "input_tokens": 120,
        "output_tokens": 4096,
        "reasoning_tokens": 4000,
        "total_tokens": 4216,
    }
    assert validation["invoice_validation_attempted"] is False


def test_diagnostic_reports_refusal_without_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    content = SimpleNamespace(type="refusal", refusal="private refusal")
    item = SimpleNamespace(type="message", status="completed", content=[content])
    result, metadata, _ = run_and_read(capsys, response(output=[item]))

    assert result == 2
    assert metadata["classification"] == "D. refusal"
    assert metadata["refusal_present"] is True
    assert "private refusal" not in json.dumps(metadata)


def test_diagnostic_reports_completed_without_parsed_object(
    capsys: pytest.CaptureFixture[str],
) -> None:
    item = SimpleNamespace(type="reasoning", status="completed")
    result, metadata, validation = run_and_read(capsys, response(output=[item]))

    assert result == 2
    assert metadata["classification"] == "H. another documented structural state"
    assert metadata["parsed_object_present"] is False
    assert validation["invoice_validation_attempted"] is False


def test_diagnostic_reports_zero_output_items(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result, metadata, _ = run_and_read(capsys, response())

    assert result == 2
    assert metadata["classification"] == "F. completed + empty output"
    assert metadata["output_item_count"] == 0


def test_diagnostic_reports_output_text_without_exposing_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    value = response(output=[SimpleNamespace(type="message", status="completed")])
    value.output_text = "private generated output"
    result, metadata, _ = run_and_read(capsys, value)

    assert result == 2
    assert metadata["classification"] == (
        "E. completed + output text but no parsed structured object"
    )
    assert metadata["output_text_present"] is True
    assert "private generated output" not in json.dumps(metadata)


def test_diagnostic_reports_provider_error_state(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result, metadata, _ = run_and_read(
        capsys, response(error=SimpleNamespace(message="private provider detail"))
    )

    assert result == 2
    assert metadata["classification"] == "G. provider/API error"
    assert metadata["response_error_type"] == "SimpleNamespace"
    assert "private provider detail" not in json.dumps(metadata)


def test_diagnostic_tolerates_missing_optional_metadata(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result, metadata, validation = run_and_read(
        capsys, response(status=None, include_optional=False)
    )

    assert result == 2
    assert metadata["classification"] == "H. another documented structural state"
    assert metadata["response_id"] is None
    assert metadata["provider_request_id"] is None
    assert metadata["usage"] == {
        "input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "total_tokens": None,
    }
    assert validation["invoice_validation_attempted"] is False


def test_request_metadata_contains_only_safe_request_shape() -> None:
    metadata = collect_safe_request_metadata(model="test-model", timeout=30.0)

    assert metadata == {
        "model": "test-model",
        "api_method": "responses.parse",
        "text_format_schema": "ProviderInvoice",
        "max_output_tokens": 4096,
        "reasoning_effort": "not explicitly supplied",
        "stream_enabled": False,
        "background_enabled": False,
        "store": "not explicitly supplied",
        "input_modality": "text",
        "timeout_seconds": 30.0,
        "custom_base_url": False,
    }


def test_request_metadata_reports_explicit_none_reasoning() -> None:
    metadata = collect_safe_request_metadata(
        model="test-model", timeout=30.0, reasoning_effort="none"
    )

    assert metadata["reasoning_effort"] == "none"
