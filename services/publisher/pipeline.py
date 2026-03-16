"""Platform publishing pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from shared.workflow import ReleaseStatus

from .adapters.instagram import InstagramPublishError, publish as publish_instagram
from .adapters.tiktok_manual import build_handoff
from .adapters.youtube import YouTubePublishError, publish as publish_youtube


class PublishPipelineError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, stderr: str | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.stderr = stderr


def _caption(context: dict[str, Any]) -> str:
    release = context["release"]
    hashtags = " ".join(f"#{tag}" for tag in (release.get("hashtags") or []))
    body = release.get("description") or ""
    return f"{body}\n\n{hashtags}".strip()


def publish_release(context: dict[str, Any], session: requests.sessions.Session | None = None) -> dict[str, Any]:
    release = context["release"]
    platform = release["platform"]
    if platform == "youtube":
        artifact = context["artifact"]
        try:
            platform_video_id = publish_youtube(
                Path(artifact["video_path"]),
                release["title"],
                _caption(context),
            )
        except YouTubePublishError as exc:
            raise PublishPipelineError(str(exc), retryable=False) from exc
        return {"platform_video_id": platform_video_id}
    if platform == "instagram":
        try:
            platform_video_id = publish_instagram(
                asset_url=release["signed_asset_url"],
                caption=_caption(context),
                session=session,
            )
        except InstagramPublishError as exc:
            raise PublishPipelineError(str(exc), retryable=exc.retryable) from exc
        return {"platform_video_id": platform_video_id}
    if platform == "tiktok":
        handoff = build_handoff(
            title=release["title"],
            description=release["description"],
            hashtags=release.get("hashtags") or [],
            asset_url=release["signed_asset_url"],
            publish_at=release.get("publish_at"),
        )
        return {
            "release_status_override": ReleaseStatus.MANUAL_HANDOFF.value,
            "metadata": {"manual_handoff": handoff},
        }
    raise PublishPipelineError(f"Unsupported platform: {platform}", retryable=False)
