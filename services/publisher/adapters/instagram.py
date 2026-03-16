"""Instagram Reels publisher using the Graph API."""

from __future__ import annotations

import time

import requests

from shared.config import settings


class InstagramPublishError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


def _required(value: str, field: str) -> str:
    if not value:
        raise InstagramPublishError(f"{field} is not configured", retryable=False)
    return value


def publish(*, asset_url: str, caption: str, session: requests.sessions.Session | None = None) -> str:
    sess = session or requests
    account_id = _required(settings.INSTAGRAM_BUSINESS_ACCOUNT_ID, "INSTAGRAM_BUSINESS_ACCOUNT_ID")
    access_token = _required(settings.INSTAGRAM_ACCESS_TOKEN, "INSTAGRAM_ACCESS_TOKEN")
    base_url = settings.INSTAGRAM_GRAPH_API_BASE.rstrip("/")
    create = sess.post(
        f"{base_url}/{account_id}/media",
        data={
            "media_type": "REELS",
            "video_url": asset_url,
            "caption": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    if create.status_code >= 400:
        raise InstagramPublishError(f"Instagram media creation failed: {create.text}")
    container_id = (create.json() or {}).get("id")
    if not container_id:
        raise InstagramPublishError("Instagram media creation did not return a container id")
    for _ in range(30):
        status_resp = sess.get(
            f"{base_url}/{container_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=30,
        )
        if status_resp.status_code >= 400:
            raise InstagramPublishError(f"Instagram media polling failed: {status_resp.text}")
        status_code = (status_resp.json() or {}).get("status_code")
        if status_code == "FINISHED":
            break
        if status_code in {"ERROR", "EXPIRED"}:
            raise InstagramPublishError(f"Instagram media container failed with status {status_code}")
        time.sleep(2)
    else:
        raise InstagramPublishError("Instagram media container did not finish in time")
    publish_resp = sess.post(
        f"{base_url}/{account_id}/media_publish",
        data={"creation_id": container_id, "access_token": access_token},
        timeout=30,
    )
    if publish_resp.status_code >= 400:
        raise InstagramPublishError(f"Instagram publish failed: {publish_resp.text}")
    media_id = (publish_resp.json() or {}).get("id")
    if not media_id:
        raise InstagramPublishError("Instagram publish did not return a media id")
    return str(media_id)
