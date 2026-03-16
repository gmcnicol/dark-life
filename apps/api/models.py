"""Database and API models for the canonical Dark Life workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, JSON, String, Text, UniqueConstraint, func
from sqlmodel import Field, SQLModel

from shared.workflow import AssetKind, JobStatus, ReleaseStatus, RenderVariant, StoryStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampedModel(SQLModel):
    created_at: datetime | None = Field(
        default_factory=utc_now,
    )
    updated_at: datetime | None = Field(
        default_factory=utc_now,
    )


class StoryBase(SQLModel):
    title: str
    subreddit: Optional[str] = None
    source_url: Optional[str] = None
    body_md: Optional[str] = None
    status: str = Field(default=StoryStatus.INGESTED.value)
    source: Optional[str] = None
    external_id: Optional[str] = None
    author: Optional[str] = None
    created_utc: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    nsfw: Optional[bool] = None
    flair: Optional[str] = None
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    narration_notes: Optional[str] = None


class Story(StoryBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    active_script_version_id: int | None = Field(default=None, foreign_key="scriptversion.id")
    active_asset_bundle_id: int | None = Field(default=None, foreign_key="assetbundle.id")


class StoryCreate(StoryBase):
    pass


class StoryRead(StoryBase):
    id: int
    active_script_version_id: int | None = None
    active_asset_bundle_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StoryUpdate(SQLModel):
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
    narration_notes: Optional[str] = None
    active_script_version_id: int | None = None
    active_asset_bundle_id: int | None = None


class ScriptVersionBase(SQLModel):
    story_id: int = Field(foreign_key="story.id")
    source_text: str
    hook: str = ""
    narration_text: str
    outro: str = ""
    model_name: str = "rule_based"
    prompt_version: str = "v1"
    is_active: bool = True


class ScriptVersion(ScriptVersionBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class ScriptVersionRead(ScriptVersionBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StoryPartBase(SQLModel):
    story_id: int = Field(foreign_key="story.id")
    script_version_id: int | None = Field(default=None, foreign_key="scriptversion.id")
    asset_bundle_id: int | None = Field(default=None, foreign_key="assetbundle.id")
    index: int
    body_md: str
    source_text: str = ""
    script_text: str = ""
    est_seconds: int
    start_char: int = 0
    end_char: int = 0
    approved: bool = False
    notes: str | None = None


class StoryPart(StoryPartBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class StoryPartRead(StoryPartBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssetBase(SQLModel):
    story_id: int | None = Field(default=None, foreign_key="story.id")
    type: str = Field(default=AssetKind.VIDEO.value)
    remote_url: str | None = None
    local_path: str | None = None
    provider: Optional[str] = None
    provider_id: Optional[str] = None
    source: str = "local"
    selected: bool = False
    rank: Optional[int] = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    orientation: str | None = None
    file_hash: str | None = None
    rating: int | None = None
    attribution: str | None = None
    tags: list[str] | None = Field(default=None, sa_column=Column(JSON))


class Asset(AssetBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class AssetRead(AssetBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssetUpdate(SQLModel):
    selected: Optional[bool] = None
    rank: Optional[int] = None
    rating: Optional[int] = None
    tags: list[str] | None = None


class AssetBundleBase(SQLModel):
    story_id: int = Field(foreign_key="story.id")
    name: str
    variant: str = Field(default=RenderVariant.SHORT.value)
    asset_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    part_asset_map: list[dict[str, int]] = Field(default_factory=list, sa_column=Column(JSON))
    music_policy: str = "first"
    music_track: str | None = None


class AssetBundle(AssetBundleBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class AssetBundleRead(AssetBundleBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RenderPresetBase(SQLModel):
    slug: str
    name: str
    variant: str = Field(default=RenderVariant.SHORT.value)
    width: int
    height: int
    fps: int
    burn_subtitles: bool = True
    target_min_seconds: int = 45
    target_max_seconds: int = 60
    music_enabled: bool = True
    music_gain_db: float = -3.0
    ducking_db: float = -12.0
    description: str | None = None


class RenderPreset(RenderPresetBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class RenderPresetRead(RenderPresetBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CompilationBase(SQLModel):
    story_id: int = Field(foreign_key="story.id")
    title: str
    status: str = Field(default=StoryStatus.APPROVED.value)
    script_version_id: int | None = Field(default=None, foreign_key="scriptversion.id")
    render_preset_id: int | None = Field(default=None, foreign_key="renderpreset.id")
    notes: str | None = None


class Compilation(CompilationBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    render_artifact_id: int | None = Field(default=None, foreign_key="renderartifact.id")


class CompilationRead(CompilationBase):
    id: int
    render_artifact_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int | None = Field(default=None, foreign_key="story.id")
    story_part_id: int | None = Field(default=None, foreign_key="storypart.id")
    compilation_id: int | None = Field(default=None, foreign_key="compilation.id")
    script_version_id: int | None = Field(default=None, foreign_key="scriptversion.id")
    asset_bundle_id: int | None = Field(default=None, foreign_key="assetbundle.id")
    render_preset_id: int | None = Field(default=None, foreign_key="renderpreset.id")
    kind: str
    variant: str = Field(default=RenderVariant.SHORT.value)
    status: str = Field(default=JobStatus.QUEUED.value)
    correlation_id: str | None = None
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
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


class JobRead(SQLModel):
    id: int
    story_id: int | None = None
    story_part_id: int | None = None
    compilation_id: int | None = None
    script_version_id: int | None = None
    asset_bundle_id: int | None = None
    render_preset_id: int | None = None
    kind: str
    variant: str
    status: str
    correlation_id: str | None = None
    payload: dict | None = None
    result: dict | None = None
    error_class: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class JobUpdate(SQLModel):
    status: str | None = None
    result: dict | None = None


class RenderArtifactBase(SQLModel):
    job_id: int | None = Field(default=None, foreign_key="jobs.id")
    story_id: int = Field(foreign_key="story.id")
    story_part_id: int | None = Field(default=None, foreign_key="storypart.id")
    compilation_id: int | None = Field(default=None, foreign_key="compilation.id")
    variant: str = Field(default=RenderVariant.SHORT.value)
    video_path: str
    subtitle_path: str | None = None
    waveform_path: str | None = None
    bytes: int | None = None
    duration_ms: int | None = None
    details: dict | None = Field(default=None, sa_column=Column("metadata", JSON))


class RenderArtifact(RenderArtifactBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class RenderArtifactRead(RenderArtifactBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReleaseBase(SQLModel):
    story_id: int = Field(foreign_key="story.id")
    story_part_id: int | None = Field(default=None, foreign_key="storypart.id")
    compilation_id: int | None = Field(default=None, foreign_key="compilation.id")
    render_artifact_id: int | None = Field(default=None, foreign_key="renderartifact.id")
    platform: str
    variant: str = Field(default=RenderVariant.SHORT.value)
    title: str
    description: str = ""
    hashtags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default=ReleaseStatus.DRAFT.value)


class Release(ReleaseBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    published_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    __table_args__ = (
        UniqueConstraint("story_id", "story_part_id", "compilation_id", "platform", "variant"),
    )


class ReleaseRead(ReleaseBase):
    id: int
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Upload(SQLModel, table=True):
    """Legacy upload record retained for compatibility with existing tooling."""

    id: Optional[int] = Field(default=None, primary_key=True)
    story_id: int = Field(foreign_key="story.id")
    part_index: int
    platform: str
    platform_video_id: str
    uploaded_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    __table_args__ = (UniqueConstraint("story_id", "part_index", "platform"),)


__all__ = [
    "Asset",
    "AssetBundle",
    "AssetBundleRead",
    "AssetRead",
    "AssetUpdate",
    "Compilation",
    "CompilationRead",
    "Job",
    "JobRead",
    "JobUpdate",
    "Release",
    "ReleaseRead",
    "RenderArtifact",
    "RenderArtifactRead",
    "RenderPreset",
    "RenderPresetRead",
    "ScriptVersion",
    "ScriptVersionRead",
    "Story",
    "StoryCreate",
    "StoryPart",
    "StoryPartRead",
    "StoryRead",
    "StoryUpdate",
    "Upload",
]
