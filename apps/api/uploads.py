"""Helpers for selecting story parts ready for upload."""

from __future__ import annotations

from typing import Tuple, Optional

from sqlmodel import Session, select

from .models import Job, Story, Upload


def next_part_ready_for_upload(
    session: Session, platform: str = "youtube"
) -> Optional[Tuple[Job, Story]]:
    """Return the next rendered part that hasn't been uploaded.

    Prefers the lowest story ID and part index.
    """
    jobs = session.exec(
        select(Job)
        .where(Job.kind == "render_part", Job.status == "success")
        .order_by(Job.story_id, Job.id)
    ).all()
    for job in jobs:
        payload = job.payload or {}
        part_index = payload.get("part_index")
        if part_index is None:
            continue
        uploaded = session.exec(
            select(Upload).where(
                Upload.story_id == job.story_id,
                Upload.part_index == part_index,
                Upload.platform == platform,
            )
        ).first()
        if uploaded:
            continue
        story = session.get(Story, job.story_id)
        if not story:
            continue
        return job, story
    return None


__all__ = ["next_part_ready_for_upload"]
