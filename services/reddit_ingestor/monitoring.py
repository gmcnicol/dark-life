"""Logging and metrics utilities for the Reddit ingestor.

This module configures logging and exposes Prometheus metrics counters and
histograms for ingestion statistics. Configuration is driven by environment
variables:

``LOG_LEVEL``        Logging level (default: ``INFO``)
``LOG_FORMAT``       ``json`` for structured logs or ``plain`` (default)
``METRICS_ENABLED``  Whether to expose metrics via HTTP (default: true)
``METRICS_PORT``     Port for the Prometheus HTTP server (default: 8000)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from prometheus_client import Counter, Histogram, start_http_server

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """Simple JSON formatter that includes any extra fields."""

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting
        data: Dict[str, Any] = {
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
            ):
                continue
            data[key] = value
        return json.dumps(data)


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "plain").lower()

_handler = logging.StreamHandler()
if LOG_FORMAT == "json":
    _handler.setFormatter(JsonFormatter())
else:  # pragma: no cover - standard formatter
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

logging.basicConfig(level=LOG_LEVEL, handlers=[_handler])

# ---------------------------------------------------------------------------
# Metrics configuration
# ---------------------------------------------------------------------------

METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() in {"1", "true", "yes"}
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
if METRICS_ENABLED:  # pragma: no cover - side effect
    start_http_server(METRICS_PORT)

FETCHED_POSTS = Counter(
    "reddit_fetched_posts_total", "Number of Reddit posts fetched", ["subreddit"]
)
INSERTED_POSTS = Counter(
    "reddit_inserted_posts_total", "Number of Reddit posts inserted", ["subreddit"]
)
DUPLICATE_POSTS = Counter(
    "reddit_duplicate_posts_total", "Number of duplicate Reddit posts", ["subreddit"]
)
REJECTED_POSTS = Counter(
    "reddit_rejected_posts_total", "Number of Reddit posts rejected", ["subreddit"]
)
API_LATENCY = Histogram(
    "reddit_api_latency_seconds", "Latency of Reddit API requests", ["endpoint"]
)
PROCESSING_LATENCY = Histogram(
    "reddit_processing_latency_seconds", "Latency for processing post batches", ["subreddit"]
)
INGESTION_ERRORS = Counter(
    "reddit_ingestor_errors_total", "Number of ingestion errors", ["component"]
)

__all__ = [
    "FETCHED_POSTS",
    "INSERTED_POSTS",
    "DUPLICATE_POSTS",
    "REJECTED_POSTS",
    "API_LATENCY",
    "PROCESSING_LATENCY",
    "INGESTION_ERRORS",
    "METRICS_ENABLED",
]
