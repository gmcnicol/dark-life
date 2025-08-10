from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel import Session, select
from sqlalchemy import Table, Column, DateTime, Text, MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .db import get_session
from .models import Job, Story
from services.reddit_ingestor.storage import reddit_posts

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

class PromoteRequest(BaseModel):
    reddit_ids: List[str]


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


@router.get("/posts")
def list_posts(
    subreddit: Optional[str] = None,
    q: Optional[str] = None,
    since: Optional[datetime] = None,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
):
    stmt = select(reddit_posts)
    if subreddit:
        stmt = stmt.where(reddit_posts.c.subreddit == subreddit)
    if q:
        stmt = stmt.where(reddit_posts.c.title.ilike(f"%{q}%"))
    if since:
        stmt = stmt.where(reddit_posts.c.created_utc >= since)
    stmt = stmt.order_by(reddit_posts.c.created_utc.desc()).limit(100)
    rows = session.exec(stmt).all()
    return [dict(r._mapping) for r in rows]


@router.post("/promote")
def promote_posts(
    req: PromoteRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
) -> dict:
    created: List[int] = []
    for rid in req.reddit_ids:
        row = session.exec(
            select(reddit_posts).where(reddit_posts.c.reddit_id == rid)
        ).first()
        if row:
            payload = row._mapping
            story = Story(
                title=payload.get("title"),
                subreddit=payload.get("subreddit"),
                source_url=payload.get("url"),
                body_md=payload.get("selftext"),
                status="draft",
            )
            session.add(story)
            session.commit()
            session.refresh(story)
            created.append(story.id)
    return {"created_story_ids": created}


__all__ = ["router"]
