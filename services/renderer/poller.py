from __future__ import annotations

"""Simple poller that processes queued render_part jobs from the database."""

import json
import time
from pathlib import Path

import requests
import typer
from sqlmodel import Session, create_engine, select

from apps.api.models import Asset, Job
from shared.config import settings
from shared.types import RenderJob
from video_renderer import render_job_runner

app = typer.Typer(add_completion=False)


def process_once(session: Session) -> bool:
    """Process a single queued render_part job."""
    job = session.exec(
        select(Job)
        .where(Job.status == "queued", Job.kind == "render_part")
        .order_by(Job.created_at)
        .limit(1)
    ).first()
    if job is None:
        return False

    job.status = "running"
    session.add(job)
    session.commit()
    session.refresh(job)

    payload = job.payload or {}
    story_id = payload.get("story_id")
    asset_ids = payload.get("asset_ids") or []
    if not story_id or not asset_ids:
        job.status = "failed"
        session.add(job)
        session.commit()
        return True

    assets = session.exec(select(Asset).where(Asset.id.in_(asset_ids))).all()

    image_paths: list[Path] = []
    settings.VISUALS_DIR.mkdir(parents=True, exist_ok=True)
    for idx, asset in enumerate(assets):
        dest = settings.VISUALS_DIR / f"{story_id}_{idx}.jpg"
        try:
            resp = requests.get(asset.remote_url, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            image_paths.append(dest)
        except Exception:
            job.status = "failed"
            session.add(job)
            session.commit()
            return True

    job_obj = RenderJob(
        story_path=settings.STORIES_DIR / f"{story_id}.md",
        image_paths=image_paths,
    )

    try:
        success = render_job_runner._process_job(job_obj)
    except Exception:
        success = False

    job.status = "success" if success else "failed"
    session.add(job)
    session.commit()

    # Log payload for debugging
    print(json.dumps(payload))
    return True


@app.command()
def run(interval: float = 1.0) -> None:
    """Continuously poll for queued render_part jobs."""
    engine = create_engine(settings.DATABASE_URL, echo=False)
    while True:
        with Session(engine) as session:
            processed = process_once(session)
        if not processed:
            time.sleep(interval)


if __name__ == "__main__":  # pragma: no cover
    app()
