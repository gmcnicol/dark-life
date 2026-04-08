"""Worker-facing render job API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Session, select

from shared.config import settings
from shared.workflow import (
    JobStatus,
    PublishApprovalStatus,
    ReleaseStatus,
    StoryStatus,
    can_transition_job,
)

from .db import get_session
from .media_refs import bundle_asset_refs, bundle_part_asset_map
from .models import (
    AssetBundle,
    Compilation,
    Job,
    JobRead,
    Release,
    RenderArtifact,
    RenderPreset,
    ScriptVersion,
    Story,
    StoryPart,
)
from .publishing import approval_payload_status, delivery_mode_for_platform, ensure_publish_job
from .pipeline import release_for_artifact

router = APIRouter(prefix="/render-jobs", tags=["render-jobs"])

DEFAULT_LEASE_SECONDS = 180


class ClaimRequest(SQLModel):
    lease_seconds: int = DEFAULT_LEASE_SECONDS


class RenderJobStatusUpdate(BaseModel):
    status: str
    artifact_path: str | None = None
    subtitle_path: str | None = None
    waveform_path: str | None = None
    bytes: int | None = None
    duration_ms: int | None = None
    error_class: str | None = None
    error_message: str | None = None
    stderr_snippet: str | None = None
    metadata: dict | None = None


def require_worker_token(authorization: str | None = Header(default=None)) -> None:
    expected = settings.API_AUTH_TOKEN
    if not expected or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

def _assemble_render_context(job: Job, session: Session) -> dict[str, Any]:
    story = session.get(Story, job.story_id) if job.story_id else None
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    script_version_id = job.script_version_id or story.active_script_version_id
    script_version = session.get(ScriptVersion, script_version_id) if script_version_id else None
    render_preset = session.get(RenderPreset, job.render_preset_id) if job.render_preset_id else None
    parts = session.exec(
        select(StoryPart)
        .where(StoryPart.story_id == story.id)
        .order_by(StoryPart.index)
    ).all()
    bundle = session.get(AssetBundle, job.asset_bundle_id) if job.asset_bundle_id else None
    asset_refs = bundle_asset_refs(bundle, session) if bundle else []
    part_asset_map = bundle_part_asset_map(bundle, parts, session) if bundle else []
    selected_asset = None
    story_part = None
    if job.story_part_id:
        story_part = session.get(StoryPart, job.story_part_id)
        selected_row = next((row for row in part_asset_map if row["story_part_id"] == job.story_part_id), None)
        if selected_row:
            selected_asset = selected_row["asset"]
        elif story_part and asset_refs:
            selected_asset = asset_refs[(max(story_part.index, 1) - 1) % len(asset_refs)]

    compilation = session.get(Compilation, job.compilation_id) if job.compilation_id else None
    prior_artifacts = session.exec(
        select(RenderArtifact)
        .where(RenderArtifact.story_id == story.id)
        .order_by(RenderArtifact.id.desc())
    ).all()
    releases = session.exec(
        select(Release)
        .where(Release.story_id == story.id)
        .order_by(Release.id.desc())
    ).all()

    bundle_data = None
    if bundle:
        bundle_data = bundle.model_dump()
        bundle_data["asset_refs"] = asset_refs
        bundle_data["part_asset_map"] = part_asset_map

    return {
        "job": JobRead.model_validate(job).model_dump(),
        "story": story.model_dump(),
        "story_part": story_part.model_dump() if story_part else None,
        "compilation": compilation.model_dump() if compilation else None,
        "script_version": script_version.model_dump() if script_version else None,
        "render_preset": render_preset.model_dump() if render_preset else None,
        "asset_bundle": bundle_data,
        "assets": asset_refs,
        "selected_asset": selected_asset,
        "parts": [part.model_dump() for part in parts],
        "artifacts": [artifact.model_dump() for artifact in prior_artifacts],
        "releases": [release.model_dump() for release in releases],
    }


def _compilation_dependencies_ready(job: Job, session: Session) -> bool:
    if job.kind != "render_compilation" or not job.story_id:
        return True
    parts = session.exec(
        select(StoryPart)
        .where(StoryPart.story_id == job.story_id)
    ).all()
    if not parts:
        return False
    part_ids = {part.id for part in parts}
    short_jobs = session.exec(
        select(Job)
        .where(
            Job.story_id == job.story_id,
            Job.kind == "render_part",
            Job.story_part_id.is_not(None),
        )
    ).all()
    jobs_by_part = {short_job.story_part_id: short_job for short_job in short_jobs if short_job.story_part_id is not None}
    if set(jobs_by_part) != part_ids:
        return False
    terminal_statuses = {
        JobStatus.PUBLISH_READY.value,
        JobStatus.PUBLISHED.value,
    }
    return all(short_job.status in terminal_statuses for short_job in jobs_by_part.values())


@router.get("/", response_model=list[JobRead])
def list_render_jobs(
    status: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> list[Job]:
    query = select(Job).where(Job.kind.ilike("render_%"))
    if status:
        query = query.where(Job.status == status)
    query = query.order_by(Job.id)
    jobs = session.exec(query).all()
    ready_jobs = [job for job in jobs if _compilation_dependencies_ready(job, session)]
    return ready_jobs[:limit]


@router.post("/{job_id}/claim")
def claim_render_job(
    job_id: int,
    request: ClaimRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not _compilation_dependencies_ready(job, session):
        raise HTTPException(status_code=409, detail="Compilation dependencies not ready")
    if job.status != JobStatus.QUEUED.value:
        raise HTTPException(status_code=409, detail="Invalid state")
    job.status = JobStatus.CLAIMED.value
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.lease_seconds)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


@router.post("/{job_id}/heartbeat")
def heartbeat_render_job(
    job_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {JobStatus.CLAIMED.value, JobStatus.RENDERING.value}:
        raise HTTPException(status_code=409, detail="Invalid state")
    if job.lease_expires_at and job.lease_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Lease expired")
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=DEFAULT_LEASE_SECONDS)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


@router.get("/{job_id}/context")
def get_render_job_context(
    job_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _assemble_render_context(job, session)


def _upsert_artifact(job: Job, update: RenderJobStatusUpdate, session: Session) -> RenderArtifact | None:
    if not update.artifact_path:
        return None
    artifact = session.exec(
        select(RenderArtifact).where(RenderArtifact.job_id == job.id)
    ).first()
    metadata = update.metadata or {}
    if not artifact:
        artifact = RenderArtifact(
            job_id=job.id,
            story_id=job.story_id or 0,
            story_part_id=job.story_part_id,
            script_version_id=job.script_version_id,
            compilation_id=job.compilation_id,
            variant=job.variant,
            video_path=update.artifact_path,
            subtitle_path=update.subtitle_path,
            waveform_path=update.waveform_path,
            bytes=update.bytes,
            duration_ms=update.duration_ms,
            details=metadata,
        )
    else:
        artifact.video_path = update.artifact_path
        artifact.subtitle_path = update.subtitle_path
        artifact.waveform_path = update.waveform_path
        artifact.bytes = update.bytes
        artifact.duration_ms = update.duration_ms
        artifact.details = metadata
        artifact.script_version_id = job.script_version_id
    session.add(artifact)
    session.flush()
    return artifact


@router.post("/{job_id}/status", response_model=JobRead)
def update_render_job_status(
    job_id: int,
    update: RenderJobStatusUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if update.status != job.status and not can_transition_job(job.status, update.status):
        raise HTTPException(status_code=409, detail="Invalid state transition")

    job.status = update.status
    job.error_class = update.error_class
    job.error_message = update.error_message
    job.stderr_snippet = update.stderr_snippet
    if update.metadata or update.artifact_path:
        job.result = {
            **(job.result or {}),
            **(update.metadata or {}),
        }
        if update.artifact_path is not None:
            job.result["artifact_path"] = update.artifact_path
        if update.subtitle_path is not None:
            job.result["subtitle_path"] = update.subtitle_path
        if update.bytes is not None:
            job.result["bytes"] = update.bytes
        if update.duration_ms is not None:
            job.result["duration_ms"] = update.duration_ms

    artifact = _upsert_artifact(job, update, session)
    if artifact and update.status == JobStatus.RENDERED.value:
        story = session.get(Story, job.story_id) if job.story_id else None
        if story:
            story.status = StoryStatus.RENDERED.value
            session.add(story)
        for release in release_for_artifact(
            session,
            story_id=job.story_id or 0,
            story_part_id=job.story_part_id,
            compilation_id=job.compilation_id,
            script_version_id=job.script_version_id,
        ):
            release.render_artifact_id = artifact.id
            release.delivery_mode = delivery_mode_for_platform(release.platform)
            release.last_error = None
            if release.approval_status == PublishApprovalStatus.APPROVED.value:
                next_status = approval_payload_status(release.publish_at)
                release.status = next_status
                release.publish_status = next_status
                ensure_publish_job(
                    session,
                    release,
                    not_before=release.publish_at,
                    payload={
                        "delivery_mode": release.delivery_mode,
                        "variant": release.variant,
                        "auto_scheduled": True,
                    },
                )
            else:
                release.status = ReleaseStatus.READY.value
                release.publish_status = ReleaseStatus.READY.value
                release.approval_status = PublishApprovalStatus.PENDING.value
            session.add(release)
        if job.compilation_id:
            compilation = session.get(Compilation, job.compilation_id)
            if compilation:
                compilation.render_artifact_id = artifact.id
                compilation.status = StoryStatus.RENDERED.value
                session.add(compilation)
        job.status = JobStatus.PUBLISH_READY.value
        if story:
            story.status = StoryStatus.PUBLISH_READY.value
            session.add(story)
    elif update.status == JobStatus.ERRORED.value:
        for release in release_for_artifact(
            session,
            story_id=job.story_id or 0,
            story_part_id=job.story_part_id,
            compilation_id=job.compilation_id,
            script_version_id=job.script_version_id,
        ):
            release.status = ReleaseStatus.ERRORED.value
            release.publish_status = ReleaseStatus.ERRORED.value
            release.last_error = update.error_message or update.stderr_snippet or "Render failed"
            session.add(release)

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


__all__ = ["router"]
