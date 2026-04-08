from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session

from shared.config import settings
from shared.workflow import JobStatus, ReleaseStatus, StoryStatus

from .db import get_session
from .models import Compilation, Job, JobRead, Story
from .pipeline import release_for_artifact

router = APIRouter(prefix="/admin/render-jobs", tags=["admin-render-jobs"])


def require_token(authorization: str | None = Header(default=None)) -> None:
    expected = settings.API_AUTH_TOKEN
    if not expected or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/{job_id}/requeue", response_model=JobRead)
def requeue_render_job(
    job_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in {
        JobStatus.ERRORED.value,
        JobStatus.CLAIMED.value,
        JobStatus.RENDERING.value,
    }:
        raise HTTPException(status_code=409, detail="Job is not eligible for requeue")

    job.status = JobStatus.QUEUED.value
    job.lease_expires_at = None
    job.error_class = None
    job.error_message = None
    job.stderr_snippet = None
    job.result = None

    story = session.get(Story, job.story_id) if job.story_id else None
    if story and story.status in {
        StoryStatus.QUEUED.value,
        StoryStatus.RENDERING.value,
        StoryStatus.ERRORED.value,
    }:
        story.status = StoryStatus.QUEUED.value
        session.add(story)

    if job.compilation_id:
        compilation = session.get(Compilation, job.compilation_id)
        if compilation and compilation.status in {
            StoryStatus.RENDERING.value,
            StoryStatus.ERRORED.value,
        }:
            compilation.status = StoryStatus.APPROVED.value
            session.add(compilation)

    for release in release_for_artifact(
        session,
        story_id=job.story_id or 0,
        story_part_id=job.story_part_id,
        compilation_id=job.compilation_id,
        script_version_id=job.script_version_id,
    ):
        release.render_artifact_id = None
        release.status = ReleaseStatus.DRAFT.value
        release.publish_status = ReleaseStatus.DRAFT.value
        release.last_error = None
        session.add(release)

    session.add(job)
    session.commit()
    session.refresh(job)
    return job


__all__ = ["router"]
