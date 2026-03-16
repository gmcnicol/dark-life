"""Manual TikTok handoff generator."""

from __future__ import annotations

from typing import Any


def build_handoff(*, title: str, description: str, hashtags: list[str], asset_url: str, publish_at: str | None) -> dict[str, Any]:
    return {
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "asset_url": asset_url,
        "publish_at": publish_at,
    }
