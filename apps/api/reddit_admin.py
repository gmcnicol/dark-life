from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session, select
from sqlalchemy import Table, Column, DateTime, Text, MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, insert as pg_insert

from .db import get_session
from .models import Job

router = APIRouter(prefix="/admin/reddit", tags=["admin-reddit"])

ADMIN_TOKEN = os.getenv("ADMIN_API_TOKEN")


def require_token(authorization: str = Header(...)) -> None:
    if not ADMIN_TOKEN or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _default_subreddits() -> List[str]:
    env = os.getenv("REDDIT_DEFAULT_SUBREDDITS", "")
    return [s.strip() for s in env.split(",") if s.strip()]


# ---------------------------------------------------------------------------
# Table definition for reddit_fetch_state
# ---------------------------------------------------------------------------
metadata = MetaData()
reddit_fetch_state = Table(
    "reddit_fetch_state",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("subreddit", Text, unique=True, nullable=False),
    Column("last_fullname", Text),
    Column("last_created_utc", DateTime(timezone=True)),
    Column("backfill_earliest_utc", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
from pydantic import BaseModel

class BackfillRequest(BaseModel):
    subreddits: Optional[List[str]] = None
    earliest: Optional[str] = None

class IncrementalRequest(BaseModel):
    subreddits: Optional[List[str]] = None

class FetchStateUpdate(BaseModel):
    subreddit: str
    last_fullname: str
    last_created_utc: datetime


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/backfill")
def enqueue_backfill(
    req: BackfillRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> dict:
    subs = req.subreddits or _default_subreddits()
    jobs: List[dict] = []
    for sub in subs:
        job = Job(kind="reddit_backfill", status="queued", payload={"subreddit": sub, "earliest": req.earliest})
        session.add(job)
        session.commit()
        session.refresh(job)
        jobs.append({"id": job.id, "subreddit": sub, "kind": job.kind, "status": job.status})
    return {"jobs": jobs}


@router.post("/incremental")
def enqueue_incremental(
    req: IncrementalRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> dict:
    subs = req.subreddits or _default_subreddits()
    jobs: List[dict] = []
    for sub in subs:
        job = Job(kind="reddit_incremental", status="queued", payload={"subreddit": sub})
        session.add(job)
        session.commit()
        session.refresh(job)
        jobs.append({"id": job.id, "subreddit": sub, "kind": job.kind, "status": job.status})
    return {"jobs": jobs}


@router.get("/state")
def fetch_state(
    subreddit: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
):
    stmt = select(
        reddit_fetch_state.c.subreddit,
        reddit_fetch_state.c.last_fullname,
        reddit_fetch_state.c.last_created_utc,
        reddit_fetch_state.c.backfill_earliest_utc,
        reddit_fetch_state.c.updated_at,
    )
    if subreddit:
        stmt = stmt.where(reddit_fetch_state.c.subreddit == subreddit)
    rows = session.exec(stmt).all()
    return [dict(r._mapping) for r in rows]


@router.post("/state")
def upsert_state(
    payload: FetchStateUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> dict:
    stmt = pg_insert(reddit_fetch_state).values(
        id=uuid.uuid4(),
        subreddit=payload.subreddit,
        last_fullname=payload.last_fullname,
        last_created_utc=payload.last_created_utc,
        mode="incremental",
        updated_at=func.now(),
    ).on_conflict_do_update(
        index_elements=[reddit_fetch_state.c.subreddit],
        set_={
            "last_fullname": payload.last_fullname,
            "last_created_utc": payload.last_created_utc,
            "mode": "incremental",
            "updated_at": func.now(),
        },
    )
    session.exec(stmt)
    session.commit()
    return {"status": "ok"}


@router.get("/jobs", response_model=list[Job])
def list_reddit_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> list[Job]:
    stmt = select(Job).where(Job.kind.ilike("reddit_%"))
    if status:
        stmt = stmt.where(Job.status == status)
    if kind:
        stmt = stmt.where(Job.kind == kind)
    stmt = stmt.order_by(Job.id.desc()).limit(100)
    return session.exec(stmt).all()




__all__ = ["router"]
