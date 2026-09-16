"""Safe, structured operational telemetry for the extraction service."""

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

_REQUEST_ID = ContextVar[str | None]("extraction_request_id", default=None)
_SAFE_FIELDS = frozenset(
    {
        "component",
        "conversion_success",
        "domain_validation_success",
        "duration_ms",
        "error_category",
        "error_type",
        "extraction_path",
        "field",
        "media_type",
        "method",
        "model",
        "outcome",
        "parsed_present",
        "path",
        "provider_operation",
        "provider_request_id",
        "response_status",
        "size_bucket",
        "stage",
        "status_code",
    }
)


class JsonTelemetryFormatter(logging.Formatter):
    """Serialize only application-controlled telemetry fields as one JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        request_id = current_request_id()
        if request_id:
            payload["request_id"] = request_id
        event_data = getattr(record, "event_data", {})
        payload.update(
            {
                key: value
                for key, value in event_data.items()
                if key in _SAFE_FIELDS
                and (value is None or isinstance(value, str | int | float | bool))
            }
        )
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


logger = logging.getLogger("extraction_agent.telemetry")


def configure_logging() -> None:
    """Configure the application telemetry logger once."""
    if not any(
        getattr(handler, "extraction_agent_json", False) for handler in logger.handlers
    ):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonTelemetryFormatter())
        handler.extraction_agent_json = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def create_request_id() -> str:
    """Create an application-owned correlation identifier."""
    return uuid4().hex


def set_request_id(request_id: str) -> Token[str | None]:
    return _REQUEST_ID.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _REQUEST_ID.reset(token)


def current_request_id() -> str | None:
    return _REQUEST_ID.get()


def log_event(event: str, **fields: object) -> None:
    """Emit a named event while discarding every non-allowlisted field."""
    safe_fields = {key: value for key, value in fields.items() if key in _SAFE_FIELDS}
    logger.info(event, extra={"event_data": safe_fields})
