"""Insights service API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from shared.config import settings


def auth_headers() -> dict[str, str]:
    if settings.API_AUTH_TOKEN:
        return {"Authorization": f"Bearer {settings.API_AUTH_TOKEN}"}
    return {}


@dataclass
class InsightsApiClient:
    session: requests.sessions.Session | Any = requests

    @property
    def base_url(self) -> str:
        return settings.API_BASE_URL.rstrip("/")

    def list_sync_targets(self, *, limit: int) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{self.base_url}/insights/sync-targets",
            params={"limit": limit},
            timeout=30,
            headers=auth_headers(),
        )
        response.raise_for_status()
        return response.json() or []

    def post_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/insights/snapshots",
            json=payload,
            timeout=30,
            headers=auth_headers(),
        )
        response.raise_for_status()
        return response.json() or {}
