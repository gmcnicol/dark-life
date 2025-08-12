from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from .db import get_session
from .models import Story

router = APIRouter(prefix="/admin/stories", tags=["admin-stories"])

ADMIN_TOKEN = os.getenv("ADMIN_API_TOKEN")


def require_token(authorization: str = Header(...)) -> None:
    if not ADMIN_TOKEN or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


class StoryIn(BaseModel):
    external_id: str
    source: str
    title: str
    author: str | None = None
    created_utc: int
    text: str | None = None
    url: str | None = None
    nsfw: bool | None = None
    flair: str | None = None
    tags: List[str] | None = None


@router.post("/", response_model=Story)
def upsert_story(
    payload: StoryIn,
    session: Session = Depends(get_session),
    _: None = Depends(require_token),
):
    stmt = select(Story).where(
        Story.source == payload.source, Story.external_id == payload.external_id
    )
    story = session.exec(stmt).first()
    if story:
        story.title = payload.title
        story.author = payload.author
        story.body_md = payload.text
        story.source_url = payload.url
        story.nsfw = payload.nsfw
        story.flair = payload.flair
        story.tags = payload.tags
        session.add(story)
        session.commit()
        session.refresh(story)
        return story
    story = Story(
        external_id=payload.external_id,
        source=payload.source,
        title=payload.title,
        author=payload.author,
        created_utc=datetime.fromtimestamp(payload.created_utc, tz=timezone.utc),
        body_md=payload.text,
        source_url=payload.url,
        nsfw=payload.nsfw,
        flair=payload.flair,
        tags=payload.tags,
        status="draft",
    )
    session.add(story)
    session.commit()
    session.refresh(story)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED, content=jsonable_encoder(story)
    )


__all__ = ["router"]
