"""Refinement-side API client for authenticated job operations."""

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
class RefinementApiClient:
    session: requests.sessions.Session | Any = requests

    @property
    def base_url(self) -> str:
        return settings.API_BASE_URL.rstrip("/")

    def list_jobs(self, *, status: str, limit: int) -> list[dict[str, Any]]:
        resp = self.session.get(
            f"{self.base_url}/refinement-jobs",
            params={"status": status, "limit": limit},
            timeout=30,
            headers=auth_headers(),
        )
        resp.raise_for_status()
        return resp.json() or []

    def set_status(self, job_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self.session.post(
            f"{self.base_url}/refinement-jobs/{job_id}/status",
            json=payload,
            timeout=30,
            headers=auth_headers(),
        )
        resp.raise_for_status()
        return resp.json() or {}

    def get_context(self, job_id: int) -> dict[str, Any]:
        resp = self.session.get(
            f"{self.base_url}/refinement-jobs/{job_id}/context",
            timeout=30,
            headers=auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()

