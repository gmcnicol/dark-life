from __future__ import annotations

"""Structured logging helpers for renderer services."""

import json
import logging

SERVICE_NAME = "renderer"


def _log(level: int, event: str, **fields: object) -> None:
    logging.log(level, json.dumps({"service": SERVICE_NAME, "event": event, **fields}))


def log_info(event: str, **fields: object) -> None:
    """Emit an informational JSON log line."""
    _log(logging.INFO, event, **fields)


def log_error(event: str, **fields: object) -> None:
    """Emit an error JSON log line."""
    _log(logging.ERROR, event, **fields)


def log_debug(event: str, **fields: object) -> None:
    """Emit a debug-level JSON log line."""
    _log(logging.DEBUG, event, **fields)
