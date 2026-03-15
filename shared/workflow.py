"""Canonical workflow enums and transitions used across services."""

from __future__ import annotations

from enum import StrEnum


class StoryStatus(StrEnum):
    INGESTED = "ingested"
    SCRIPTED = "scripted"
    APPROVED = "approved"
    MEDIA_READY = "media_ready"
    QUEUED = "queued"
    RENDERING = "rendering"
    RENDERED = "rendered"
    PUBLISH_READY = "publish_ready"
    PUBLISHED = "published"
    REJECTED = "rejected"
    ERRORED = "errored"


class JobStatus(StrEnum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    RENDERING = "rendering"
    RENDERED = "rendered"
    PUBLISH_READY = "publish_ready"
    PUBLISHED = "published"
    ERRORED = "errored"


class ReleaseStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    PUBLISHED = "published"
    FAILED = "failed"


class RenderVariant(StrEnum):
    SHORT = "short"
    WEEKLY = "weekly"


class AssetKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"


STORY_STATUS_TRANSITIONS: dict[StoryStatus, set[StoryStatus]] = {
    StoryStatus.INGESTED: {StoryStatus.SCRIPTED, StoryStatus.REJECTED, StoryStatus.ERRORED},
    StoryStatus.SCRIPTED: {StoryStatus.APPROVED, StoryStatus.REJECTED, StoryStatus.ERRORED},
    StoryStatus.APPROVED: {StoryStatus.MEDIA_READY, StoryStatus.REJECTED, StoryStatus.ERRORED},
    StoryStatus.MEDIA_READY: {StoryStatus.QUEUED, StoryStatus.REJECTED, StoryStatus.ERRORED},
    StoryStatus.QUEUED: {StoryStatus.RENDERING, StoryStatus.ERRORED},
    StoryStatus.RENDERING: {StoryStatus.RENDERED, StoryStatus.ERRORED},
    StoryStatus.RENDERED: {StoryStatus.PUBLISH_READY, StoryStatus.ERRORED},
    StoryStatus.PUBLISH_READY: {StoryStatus.PUBLISHED, StoryStatus.ERRORED},
    StoryStatus.PUBLISHED: set(),
    StoryStatus.REJECTED: set(),
    StoryStatus.ERRORED: {StoryStatus.INGESTED, StoryStatus.SCRIPTED, StoryStatus.APPROVED},
}


JOB_STATUS_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.CLAIMED, JobStatus.ERRORED},
    JobStatus.CLAIMED: {JobStatus.RENDERING, JobStatus.ERRORED},
    JobStatus.RENDERING: {JobStatus.RENDERED, JobStatus.ERRORED},
    JobStatus.RENDERED: {JobStatus.PUBLISH_READY, JobStatus.PUBLISHED},
    JobStatus.PUBLISH_READY: {JobStatus.PUBLISHED, JobStatus.ERRORED},
    JobStatus.PUBLISHED: set(),
    JobStatus.ERRORED: {JobStatus.QUEUED},
}


def can_transition_story(current: str, next_status: str) -> bool:
    """Return True when a story state transition is allowed."""
    try:
        return StoryStatus(next_status) in STORY_STATUS_TRANSITIONS[StoryStatus(current)]
    except Exception:
        return False


def can_transition_job(current: str, next_status: str) -> bool:
    """Return True when a job state transition is allowed."""
    try:
        return JobStatus(next_status) in JOB_STATUS_TRANSITIONS[JobStatus(current)]
    except Exception:
        return False


__all__ = [
    "AssetKind",
    "JobStatus",
    "ReleaseStatus",
    "RenderVariant",
    "StoryStatus",
    "can_transition_job",
    "can_transition_story",
]
