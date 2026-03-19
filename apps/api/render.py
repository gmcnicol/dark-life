from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from .db import get_session
from .media_refs import bundle_asset_refs
from .models import AssetBundle, Job, Story, StoryPart

router = APIRouter(prefix="/render", tags=["render"])


@router.get("/next-series")
def next_series(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Return the next story with queued render_part jobs and mark them running."""
    job = (
        session.exec(
            select(Job)
            .where(Job.kind == "render_part", Job.status == "queued")
            .order_by(Job.story_id, Job.id)
            .limit(1)
        ).first()
    )
    if not job:
        return {}
    story_id = job.story_id
    jobs = session.exec(
        select(Job)
        .where(Job.kind == "render_part", Job.status == "queued", Job.story_id == story_id)
        .order_by(Job.id)
    ).all()
    if not jobs:
        return {}
    story = session.get(Story, story_id)
    bundle = session.get(AssetBundle, job.asset_bundle_id) if job.asset_bundle_id else None
    assets = bundle_asset_refs(bundle, session) if bundle else []
    parts: list[dict[str, Any]] = []
    for j in jobs:
        p_index = (j.payload or {}).get("part_index")
        part = session.exec(
            select(StoryPart).where(StoryPart.story_id == story_id, StoryPart.index == p_index)
        ).first()
        if part:
            parts.append({"job_id": j.id, "index": part.index, "body_md": part.body_md or ""})
        j.status = "running"
        session.add(j)
    session.commit()
    return {
        "story": {"id": story.id, "title": story.title} if story else None,
        "assets": assets,
        "parts": parts,
    }


__all__ = ["router"]
