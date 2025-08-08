"""Database models for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class StoryBase(SQLModel):
    """Shared fields for Story models."""

    title: str
    subreddit: Optional[str] = None
    source_url: Optional[str] = None
    body_md: Optional[str] = None
    status: str = "draft"


class Story(StoryBase, table=True):
    """Story table model."""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime | None = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        )
    )


class StoryCreate(StoryBase):
    """Payload for creating stories."""


class StoryRead(StoryBase):
    """Story representation returned by the API."""

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StoryUpdate(SQLModel):
    """Payload for updating stories."""

    title: Optional[str] = None
    subreddit: Optional[str] = None
    source_url: Optional[str] = None
    body_md: Optional[str] = None
    status: Optional[str] = None


__all__ = [
    "Story",
    "StoryCreate",
    "StoryRead",
    "StoryUpdate",
]

