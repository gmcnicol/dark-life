"""Publishing helpers shared by operator and worker routes."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlmodel import Session, select

from shared.config import settings
from shared.workflow import PublishApprovalStatus, PublishDeliveryMode, ReleaseStatus, RenderVariant

from .models import PublishJob, Release, ReleaseRead, RenderArtifact, Story


AUTOMATED_PLATFORMS = {"youtube", "instagram"}
MANUAL_PLATFORMS = {"tiktok"}
SHORT_PLATFORMS = {"youtube", "instagram", "tiktok"}
WEEKLY_PLATFORMS = {"youtube"}
SIGNED_URL_TTL_SECONDS = 15 * 60


def delivery_mode_for_platform(platform: str) -> str:
    return (
        PublishDeliveryMode.MANUAL.value
        if platform in MANUAL_PLATFORMS
        else PublishDeliveryMode.AUTOMATED.value
    )


def validate_release_platform(platform: str, variant: str) -> None:
    allowed = SHORT_PLATFORMS if variant == RenderVariant.SHORT.value else WEEKLY_PLATFORMS
    if platform not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Platform '{platform}' is not supported for variant '{variant}'",
        )


def signing_secret() -> str:
    secret = settings.ARTIFACT_SIGNING_SECRET or settings.API_AUTH_TOKEN
    if not secret:
        raise HTTPException(status_code=500, detail="Artifact signing is not configured")
    return secret


def build_signature(kind: str, identifier: int, exp: int) -> str:
    payload = f"{kind}:{identifier}:{exp}".encode("utf-8")
    return hmac.new(signing_secret().encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_signature(kind: str, identifier: int, exp: int, sig: str) -> None:
    if exp < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=403, detail="Link expired")
    expected = build_signature(kind, identifier, exp)
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")


def build_signed_artifact_url(*, artifact_id: int | None = None, release_id: int | None = None, expires_in: int = SIGNED_URL_TTL_SECONDS) -> str:
    if artifact_id is None and release_id is None:
        raise ValueError("artifact_id or release_id is required")
    exp = int(datetime.now(timezone.utc).timestamp()) + expires_in
    if artifact_id is not None:
        sig = build_signature("artifact", artifact_id, exp)
        query = urlencode({"exp": exp, "sig": sig})
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/public/artifacts/{artifact_id}?{query}"
    sig = build_signature("release", int(release_id), exp)
    query = urlencode({"exp": exp, "sig": sig})
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/public/releases/{int(release_id)}/asset?{query}"


def resolve_release_artifact(session: Session, release: Release) -> RenderArtifact | None:
    if release.render_artifact_id:
        return session.get(RenderArtifact, release.render_artifact_id)
    if release.story_part_id is not None:
        return session.exec(
            select(RenderArtifact)
            .where(
                RenderArtifact.story_id == release.story_id,
                RenderArtifact.story_part_id == release.story_part_id,
            )
            .order_by(RenderArtifact.id.desc())
        ).first()
    return session.exec(
        select(RenderArtifact)
        .where(
            RenderArtifact.story_id == release.story_id,
            RenderArtifact.compilation_id == release.compilation_id,
        )
        .order_by(RenderArtifact.id.desc())
    ).first()


def resolve_publish_job(session: Session, release_id: int) -> PublishJob | None:
    return session.exec(select(PublishJob).where(PublishJob.release_id == release_id)).first()


def release_read(session: Session, release: Release) -> ReleaseRead:
    artifact = resolve_release_artifact(session, release)
    publish_job = resolve_publish_job(session, release.id or 0) if release.id else None
    payload = release.model_dump()
    payload["artifact_path"] = artifact.video_path if artifact else None
    payload["signed_asset_url"] = build_signed_artifact_url(release_id=release.id) if artifact and release.id else None
    payload["publish_job_id"] = publish_job.id if publish_job else None
    return ReleaseRead.model_validate(payload)


def ensure_publish_job(
    session: Session,
    release: Release,
    *,
    not_before: datetime | None,
    payload: dict[str, Any] | None = None,
) -> PublishJob:
    if not release.id:
        session.flush()
    publish_job = resolve_publish_job(session, release.id or 0)
    if not publish_job:
        publish_job = PublishJob(
            release_id=release.id or 0,
            platform=release.platform,
            correlation_id=f"release-{release.id}-{release.platform}",
        )
    publish_job.platform = release.platform
    publish_job.status = "queued"
    publish_job.not_before = not_before
    publish_job.lease_expires_at = None
    publish_job.error_class = None
    publish_job.error_message = None
    publish_job.stderr_snippet = None
    publish_job.result = None
    publish_job.payload = payload or {}
    session.add(publish_job)
    session.flush()
    return publish_job


def maybe_mark_story_published(session: Session, story_id: int) -> None:
    story = session.get(Story, story_id)
    if not story:
        return
    pending = session.exec(
        select(Release)
        .where(
            Release.story_id == story_id,
            Release.status != ReleaseStatus.PUBLISHED.value,
        )
    ).all()
    if pending:
        return
    story.status = "published"
    session.add(story)


def resolve_public_video_path(raw_path: str) -> Path:
    path = Path(raw_path)
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    output_root = settings.OUTPUT_DIR.resolve()
    if not str(resolved).startswith(str(output_root)):
        raise HTTPException(status_code=403, detail="Artifact outside output root")
    return resolved


def approval_payload_status(publish_at: datetime | None) -> str:
    if publish_at and publish_at.tzinfo is None:
        publish_at = publish_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if publish_at and publish_at > now:
        return ReleaseStatus.SCHEDULED.value
    return ReleaseStatus.APPROVED.value


def manual_handoff_metadata(release: Release, signed_asset_url: str) -> dict[str, Any]:
    return {
        "asset_url": signed_asset_url,
        "title": release.title,
        "description": release.description,
        "hashtags": release.hashtags or [],
        "publish_at": release.publish_at.isoformat() if release.publish_at else None,
    }
