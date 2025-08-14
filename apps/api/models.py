"""Database models for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, JSON, Index, UniqueConstraint, func
from sqlmodel import Field, SQLModel


class StoryBase(SQLModel):
    """Shared fields for Story models."""

    title: str
    subreddit: Optional[str] = None
    source_url: Optional[str] = None
    body_md: Optional[str] = None
    status: str = "draft"
    source: Optional[str] = None
    external_id: Optional[str] = None
    author: Optional[str] = None
    created_utc: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    nsfw: Optional[bool] = None
    flair: Optional[str] = None
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON))


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

    __table_args__ = (
        Index("ix_story_source_external", "source", "external_id", unique=True),
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
    source: Optional[str] = None
    external_id: Optional[str] = None
    author: Optional[str] = None
    created_utc: datetime | None = None
    nsfw: Optional[bool] = None
    flair: Optional[str] = None
    tags: list[str] | None = None


class StoryPart(SQLModel, table=True):
    """Story part table model."""

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int = Field(foreign_key="story.id")
    index: int
    body_md: str
    est_seconds: int
    created_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime | None = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        )
    )


class StoryPartRead(SQLModel):
    """Representation of a story part returned by the API."""

    id: int
    index: int
    body_md: str
    est_seconds: int


class Asset(SQLModel, table=True):
    """Generic asset associated with a story."""

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int = Field(foreign_key="story.id")
    type: str = Field(default="image")
    remote_url: str
    provider: Optional[str] = None
    provider_id: Optional[str] = None
    selected: bool = False
    rank: Optional[int] = None
    created_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime | None = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        )
    )


class AssetRead(SQLModel):
    """Representation of an asset returned by the API."""

    id: int
    remote_url: str
    selected: bool = False
    rank: Optional[int] = None


class AssetUpdate(SQLModel):
    """Payload for updating an asset."""

    selected: Optional[bool] = None
    rank: Optional[int] = None


class Job(SQLModel, table=True):
    """Background job table model."""

    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int | None = Field(default=None, foreign_key="story.id")
    kind: str
    status: str
    lease_expires_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    retries: int = 0
    error_class: str | None = None
    error_message: str | None = None
    stderr_snippet: str | None = None
    payload: dict | None = Field(default=None, sa_column=Column(JSON))
    result: dict | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime | None = Field(
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        )
    )

    __table_args__ = (
        Index("ix_jobs_status_kind", "status", "kind"),
        Index("ix_jobs_story_id", "story_id"),
    )


class JobUpdate(SQLModel):
    """Payload for updating job status/result."""

    status: str | None = None
    result: dict | None = None


class Upload(SQLModel, table=True):
    """Record of a story part uploaded to an external platform."""

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int = Field(foreign_key="story.id")
    part_index: int
    platform: str
    platform_video_id: str
    uploaded_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    __table_args__ = (
        UniqueConstraint("story_id", "part_index", "platform"),
    )


__all__ = [
    "Story",
    "StoryCreate",
    "StoryRead",
    "StoryUpdate",
    "StoryPart",
    "StoryPartRead",
    "Asset",
    "AssetRead",
    "AssetUpdate",
    "Job",
    "JobUpdate",
    "Upload",
]

