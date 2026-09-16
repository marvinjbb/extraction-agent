import json
import logging

from app.observability import (
    JsonTelemetryFormatter,
    reset_request_id,
    set_request_id,
)


def test_formatter_emits_json_with_request_id_and_allowlisted_fields() -> None:
    formatter = JsonTelemetryFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="provider_call_completed",
        args=(),
        exc_info=None,
    )
    record.event_data = {
        "outcome": "success",
        "duration_ms": 12.5,
        "question": "private question",
        "document": "private invoice",
        "api_key": "secret-key",
    }
    token = set_request_id("application-owned-id")
    try:
        payload = json.loads(formatter.format(record))
    finally:
        reset_request_id(token)

    assert payload["event"] == "provider_call_completed"
    assert payload["request_id"] == "application-owned-id"
    assert payload["outcome"] == "success"
    assert payload["duration_ms"] == 12.5
    assert "question" not in payload
    assert "document" not in payload
    assert "api_key" not in payload


def test_formatter_omits_request_id_outside_request_context() -> None:
    formatter = JsonTelemetryFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="startup",
        args=(),
        exc_info=None,
    )
    record.event_data = {}

    payload = json.loads(formatter.format(record))

    assert "request_id" not in payload
