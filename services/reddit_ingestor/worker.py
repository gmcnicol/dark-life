"""Worker that processes queued reddit ingestion jobs."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import typer
from sqlmodel import Session, select, create_engine

from apps.api.models import Job
from shared.config import settings

from .backfill import orchestrate_backfill
from .incremental import fetch_incremental

app = typer.Typer(add_completion=False)


def _process(session: Session) -> bool:
    job = (
        session.exec(
            select(Job)
            .where(Job.status == "queued", Job.kind.in_(["reddit_backfill", "reddit_incremental"]))
            .order_by(Job.created_at)
            .limit(1)
        ).first()
    )
    if not job:
        return False

    job.status = "running"
    session.add(job)
    session.commit()
    session.refresh(job)

    payload = job.payload or {}
    subreddit = payload.get("subreddit")
    try:
        if job.kind == "reddit_backfill":
            earliest_str = payload.get("earliest")
            earliest_ts = None
            if earliest_str:
                earliest_ts = int(
                    datetime.fromisoformat(earliest_str).replace(tzinfo=timezone.utc).timestamp()
                )
            inserted = orchestrate_backfill(subreddit, earliest_target_utc=earliest_ts)
            job.result = {"inserted": inserted}
        else:
            inserted = fetch_incremental(subreddit)
            job.result = {"inserted": inserted}
        job.status = "success"
    except Exception as exc:  # pragma: no cover - error path
        job.status = "failed"
        job.result = {"error": str(exc)}

    session.add(job)
    session.commit()
    # log payload for debugging
    print(json.dumps(job.result))
    return True


@app.command()
def run(interval: float = 1.0) -> None:
    """Continuously process queued reddit ingestion jobs."""
    engine = create_engine(settings.DATABASE_URL, echo=False)
    while True:
        with Session(engine) as session:
            processed = _process(session)
        if not processed:
            time.sleep(interval)


if __name__ == "__main__":  # pragma: no cover
    app()
