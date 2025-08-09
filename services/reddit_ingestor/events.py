from __future__ import annotations

"""Light-weight event publisher for newly ingested stories.

Posts that are successfully stored are forwarded to a web API so that other
components of the system can react to new content in near real time. The target
endpoint is configured via the ``LIVE_UPDATE_URL`` environment variable. When
unset, publishing is skipped.
"""

import logging
import os
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

LIVE_UPDATE_URL = os.getenv("LIVE_UPDATE_URL")


def push_new_story(payload: Dict[str, Any]) -> None:
    """Send ``payload`` to the configured live update API.

    Any network errors are logged and swallowed to avoid interfering with the
    ingestion pipeline.
    """

    if not LIVE_UPDATE_URL:
        return
    try:
        requests.post(LIVE_UPDATE_URL, json=payload, timeout=5)
    except requests.RequestException as exc:  # pragma: no cover - network failure
        logger.warning("push_new_story_failed", extra={"error": str(exc)})


__all__ = ["push_new_story"]
