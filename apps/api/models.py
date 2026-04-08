"""Database and API models for the canonical Dark Life workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, JSON, String, Text, UniqueConstraint, func
from sqlmodel import Field, SQLModel

from shared.workflow import (
    AssetKind,
    JobStatus,
    PublishApprovalStatus,
    PublishDeliveryMode,
    PublishJobStatus,
    ReleaseStatus,
    RenderVariant,
    StoryStatus,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampedModel(SQLModel):
    created_at: datetime | None = Field(
        default_factory=utc_now,
    )
    updated_at: datetime | None = Field(
        default_factory=utc_now,
    )


class StudioSettingBase(SQLModel):
    key: str = Field(sa_column=Column(String, unique=True, nullable=False, index=True))
    value: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class StudioSetting(StudioSettingBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


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
    batch_id: int | None = Field(default=None, foreign_key="scriptbatch.id")
    concept_id: int | None = Field(default=None, foreign_key="storyconcept.id")
    source_text: str
    hook: str = ""
    narration_text: str
    outro: str = ""
    model_name: str = "rule_based"
    prompt_version: str = "v1"
    template_version: str = "template_v1"
    critic_version: str = "critic_v1"
    selection_policy_version: str = "selection_policy_v1"
    temperature: float = 1.0
    selection_state: str = "draft"
    critic_scores: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    performance_metrics: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    derived_metrics: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    generation_metadata: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    critic_rank: int | None = None
    performance_rank: int | None = None
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
    episode_type: str = "entry"
    hook: str = ""
    lines: list[str] | None = Field(default=None, sa_column=Column(JSON))
    loop_line: str = ""
    features: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    critic_scores: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    performance_metrics: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    derived_metrics: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    critic_rank: int | None = None
    performance_rank: int | None = None
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


class MediaReference(SQLModel):
    key: str
    type: str = Field(default=AssetKind.VIDEO.value)
    remote_url: str | None = None
    local_path: str | None = None
    provider: Optional[str] = None
    provider_id: Optional[str] = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    orientation: str | None = None
    attribution: str | None = None
    tags: list[str] | None = None


class PartMediaSelection(SQLModel):
    story_part_id: int
    asset: MediaReference


class AssetUpdate(SQLModel):
    selected: Optional[bool] = None
    rank: Optional[int] = None
    rating: Optional[int] = None
    tags: list[str] | None = None


class AssetBundleBase(SQLModel):
    story_id: int = Field(foreign_key="story.id")
    name: str
    variant: str = Field(default=RenderVariant.SHORT.value)
    asset_refs: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column("asset_ids", JSON))
    part_asset_map: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
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
    script_version_id: int | None = Field(default=None, foreign_key="scriptversion.id")
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
    script_version_id: int | None = Field(default=None, foreign_key="scriptversion.id")
    compilation_id: int | None = Field(default=None, foreign_key="compilation.id")
    render_artifact_id: int | None = Field(default=None, foreign_key="renderartifact.id")
    platform: str
    variant: str = Field(default=RenderVariant.SHORT.value)
    title: str
    description: str = ""
    hashtags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default=ReleaseStatus.DRAFT.value)
    publish_status: str = Field(default=ReleaseStatus.DRAFT.value)
    approval_status: str = Field(default=PublishApprovalStatus.PENDING.value)
    delivery_mode: str = Field(default=PublishDeliveryMode.AUTOMATED.value)
    platform_video_id: str | None = None
    publish_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    approved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    last_error: str | None = Field(default=None, sa_column=Column(Text))
    attempt_count: int = 0
    provider_metadata: dict | None = Field(default=None, sa_column=Column(JSON))


class Release(ReleaseBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    published_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))

    __table_args__ = (
        UniqueConstraint("story_id", "story_part_id", "compilation_id", "platform", "variant"),
    )


class ReleaseEarlySignalRead(SQLModel):
    window_hours: int
    state: str
    score: float
    recommended_action: str
    summary: str
    evaluated_at: datetime | None = None
    metrics: dict[str, float] = Field(default_factory=dict)


class ReleaseRead(ReleaseBase):
    id: int
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    artifact_path: str | None = None
    signed_asset_url: str | None = None
    publish_job_id: int | None = None
    early_signal: ReleaseEarlySignalRead | None = None


class PublishJobBase(SQLModel):
    release_id: int = Field(foreign_key="release.id")
    platform: str
    status: str = Field(default=PublishJobStatus.QUEUED.value)
    lease_expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    attempts: int = 0
    not_before: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    correlation_id: str | None = None
    payload: dict | None = Field(default=None, sa_column=Column(JSON))
    result: dict | None = Field(default=None, sa_column=Column(JSON))
    error_class: str | None = None
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    stderr_snippet: str | None = None


class PublishJob(PublishJobBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    __table_args__ = (UniqueConstraint("release_id"),)


class PublishJobRead(PublishJobBase):
    id: int
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


class StoryConceptBase(SQLModel):
    story_id: int = Field(foreign_key="story.id")
    concept_key: str
    concept_label: str
    anomaly_type: str = "unknown"
    object_focus: str | None = None
    specificity: str = "mixed"
    extraction_metadata: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    is_active: bool = True


class StoryConcept(StoryConceptBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class StoryConceptRead(StoryConceptBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScriptBatchBase(SQLModel):
    story_id: int = Field(foreign_key="story.id")
    concept_id: int | None = Field(default=None, foreign_key="storyconcept.id")
    status: str = "queued"
    candidate_count: int = 20
    shortlisted_count: int = 3
    template_version: str = "template_v1"
    prompt_version: str = "gen_prompt_v1"
    critic_version: str = "critic_v1"
    selection_policy_version: str = "selection_policy_v1"
    analyst_version: str = "analyst_v1"
    model_name: str = "gpt-4.1-mini"
    temperature: float = 1.0
    config: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    result: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error_message: str | None = None


class ScriptBatch(ScriptBatchBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class ScriptBatchRead(ScriptBatchBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PromptVersionBase(SQLModel):
    kind: str
    version_label: str
    status: str = "draft"
    body: str
    config: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    notes: str | None = None


class PromptVersion(PromptVersionBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    __table_args__ = (UniqueConstraint("kind", "version_label"),)


class PromptVersionRead(PromptVersionBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MetricsSnapshotBase(SQLModel):
    release_id: int | None = Field(default=None, foreign_key="release.id")
    story_id: int = Field(foreign_key="story.id")
    script_version_id: int = Field(foreign_key="scriptversion.id")
    story_part_id: int | None = Field(default=None, foreign_key="storypart.id")
    window_hours: int
    source: str = "youtube"
    metrics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    derived_metrics: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    captured_at: datetime | None = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True)))


class MetricsSnapshot(MetricsSnapshotBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class MetricsSnapshotRead(MetricsSnapshotBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AnalysisReportBase(SQLModel):
    batch_id: int | None = Field(default=None, foreign_key="scriptbatch.id")
    story_id: int = Field(foreign_key="story.id")
    concept_id: int | None = Field(default=None, foreign_key="storyconcept.id")
    analyst_version: str = "analyst_v1"
    status: str = "draft"
    summary: str = ""
    insights: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    recommendations: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    prompt_proposals: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    metrics_window_hours: int = 72


class AnalysisReport(AnalysisReportBase, TimestampedModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)


class AnalysisReportRead(AnalysisReportBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


__all__ = [
    "Asset",
    "AssetBundle",
    "AssetBundleRead",
    "AssetRead",
    "AssetUpdate",
    "MediaReference",
    "PartMediaSelection",
    "Compilation",
    "CompilationRead",
    "Job",
    "JobRead",
    "JobUpdate",
    "PublishJob",
    "PublishJobRead",
    "Release",
    "ReleaseEarlySignalRead",
    "ReleaseRead",
    "RenderArtifact",
    "RenderArtifactRead",
    "RenderPreset",
    "RenderPresetRead",
    "ScriptBatch",
    "ScriptBatchRead",
    "StoryConcept",
    "StoryConceptRead",
    "PromptVersion",
    "PromptVersionRead",
    "MetricsSnapshot",
    "MetricsSnapshotRead",
    "AnalysisReport",
    "AnalysisReportRead",
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
