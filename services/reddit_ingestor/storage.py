from __future__ import annotations

"""API-based persistence helpers for the Reddit ingestion service.

This module exposes a single ``insert_post`` function which translates a
normalized Reddit payload into the API's ``StoryIn`` schema and POSTs it to the
``/admin/stories`` endpoint.  Database access has been removed; callers are
expected to interact solely with the HTTP API.
"""

from datetime import datetime
from typing import Any, Dict

import requests

from shared.config import settings


def insert_post(payload: Dict[str, Any]) -> bool:
    """Persist a Reddit post via the API.

    Returns ``True`` when the story was created/updated and ``False`` when the
    API reports a duplicate (HTTP 409).
    """

    if not settings.API_BASE_URL:
        raise RuntimeError("API_BASE_URL must be configured for ingestion")

    story = {
        "external_id": payload["reddit_id"],
        "source": "reddit",
        "title": payload["title"],
        "author": payload.get("author"),
        "created_utc": int(payload["created_utc"].timestamp())
        if isinstance(payload["created_utc"], datetime)
        else int(payload["created_utc"]),
        "text": payload.get("selftext"),
        "url": payload.get("url"),
        "nsfw": payload.get("nsfw"),
        "flair": None,
        "tags": None,
    }

    headers: Dict[str, str] = {}
    if settings.ADMIN_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.ADMIN_API_TOKEN}"

    resp = requests.post(
        f"{settings.API_BASE_URL.rstrip('/')}/admin/stories",
        json=story,
        headers=headers,
        timeout=10,
    )
    if resp.status_code in (200, 201):
        return True
    if resp.status_code == 409:
        return False
    resp.raise_for_status()
    return False


__all__ = ["insert_post"]
