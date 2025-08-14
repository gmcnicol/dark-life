from __future__ import annotations

"""Structured JSON logging for renderer services.

Logs are emitted as single-line JSON objects. Secrets such as
``API_AUTH_TOKEN`` or ``ELEVENLABS_API_KEY`` are masked before logging.
"""

import json
import logging
import os
from typing import Any

from shared.config import settings


SERVICE_NAME = "renderer"

# Configure root logger for JSON output. Only the JSON message body is printed.
_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", settings.LOG_LEVEL).upper(), logging.INFO)
logging.basicConfig(level=_LEVEL, format="%(message)s")

_SECRET_KEYS = {"API_AUTH_TOKEN", "ELEVENLABS_API_KEY"}


def _current_secrets() -> list[str]:
    return [settings.API_AUTH_TOKEN, settings.ELEVENLABS_API_KEY]


def _mask(value: Any) -> Any:
    """Replace occurrences of known secret values with ``[MASKED]``."""
    if isinstance(value, str):
        for secret in _current_secrets():
            if secret and secret in value:
                value = value.replace(secret, "[MASKED]")
    return value


def _log(level: int, event: str, **fields: object) -> None:
    data: dict[str, Any] = {"service": SERVICE_NAME, "event": event}
    for key, value in fields.items():
        if key in _SECRET_KEYS:
            data[key] = "[MASKED]"
        else:
            data[key] = _mask(value)
    logging.log(level, json.dumps(data))


def log_info(event: str, **fields: object) -> None:
    """Emit an informational JSON log line."""
    _log(logging.INFO, event, **fields)


def log_error(event: str, **fields: object) -> None:
    """Emit an error JSON log line."""
    _log(logging.ERROR, event, **fields)


def log_debug(event: str, **fields: object) -> None:
    """Emit a debug-level JSON log line."""
    _log(logging.DEBUG, event, **fields)


__all__ = ["log_info", "log_error", "log_debug", "SERVICE_NAME"]

