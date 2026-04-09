"""Release-level YouTube insights endpoints and worker contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import SQLModel, Session, select

from shared.config import settings
from shared.workflow import ReleaseStatus, RenderVariant

from .db import get_session
from .models import MetricsSnapshot, MetricsSnapshotRead, Release, ReleaseRead
from .publishing import latest_release_snapshot, release_read
from .refinement import compute_derived_metrics

router = APIRouter(tags=["insights"])


class InsightSyncTarget(SQLModel):
    release_id: int
    story_id: int
    title: str
    platform_video_id: str
    published_at: datetime
    last_synced_at: datetime | None = None


class InsightSnapshotCreate(SQLModel):
    release_id: int
    source: str = "youtube_insights"
    captured_at: datetime | None = None
    metrics: dict[str, float]


class InsightsSummaryRead(SQLModel):
    tracked_releases: int
    published_today: int
    winners: int
    monitor: int
    flat: int
    awaiting_metrics: int
    stale_sync: int
    last_sync_at: datetime | None = None


class ReleaseInsightsHistoryRead(BaseModel):
    release: ReleaseRead
    snapshots: list[MetricsSnapshotRead]


def require_worker_token(authorization: str | None = Header(default=None)) -> None:
    expected = settings.API_AUTH_TOKEN
    if not expected or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _published_youtube_short_releases(session: Session, *, days: int) -> list[Release]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(days, 1))
    return session.exec(
        select(Release)
        .where(
            Release.platform == "youtube",
            Release.variant == RenderVariant.SHORT.value,
            Release.status == ReleaseStatus.PUBLISHED.value,
            Release.platform_video_id.is_not(None),
            Release.published_at.is_not(None),
            Release.published_at >= cutoff,
        )
        .order_by(Release.published_at.desc(), Release.id.desc())
    ).all()


@router.get("/insights/releases", response_model=list[ReleaseRead])
def list_insight_releases(
    days: int = Query(default=settings.INSIGHTS_LOOKBACK_DAYS, ge=1, le=90),
    session: Session = Depends(get_session),
) -> list[ReleaseRead]:
    return [release_read(session, release) for release in _published_youtube_short_releases(session, days=days)]


@router.get("/insights/summary", response_model=InsightsSummaryRead)
def get_insights_summary(
    days: int = Query(default=settings.INSIGHTS_LOOKBACK_DAYS, ge=1, le=90),
    session: Session = Depends(get_session),
) -> InsightsSummaryRead:
    now = datetime.now(timezone.utc)
    releases = [release_read(session, release) for release in _published_youtube_short_releases(session, days=days)]
    last_syncs = [release.latest_metrics_sync_at for release in releases if release.latest_metrics_sync_at]
    stale_cutoff = now - timedelta(seconds=max(settings.INSIGHTS_SYNC_INTERVAL_SEC * 2, 3600))
    return InsightsSummaryRead(
        tracked_releases=len(releases),
        published_today=sum(
            1
            for release in releases
            if release.published_at and release.published_at.astimezone(timezone.utc).date() == now.date()
        ),
        winners=sum(1 for release in releases if release.early_signal and release.early_signal.state == "winner"),
        monitor=sum(1 for release in releases if release.early_signal and release.early_signal.state == "monitor"),
        flat=sum(1 for release in releases if release.early_signal and release.early_signal.state == "flat"),
        awaiting_metrics=sum(1 for release in releases if not release.latest_metrics_sync_at),
        stale_sync=sum(1 for release in releases if release.latest_metrics_sync_at and release.latest_metrics_sync_at < stale_cutoff),
        last_sync_at=max(last_syncs) if last_syncs else None,
    )


@router.get("/insights/releases/{release_id}/history", response_model=ReleaseInsightsHistoryRead)
def get_release_insights_history(
    release_id: int,
    hours: int = Query(default=24 * 7, ge=1, le=24 * 30),
    session: Session = Depends(get_session),
) -> ReleaseInsightsHistoryRead:
    release = session.get(Release, release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    snapshots = session.exec(
        select(MetricsSnapshot)
        .where(
            MetricsSnapshot.release_id == release_id,
            MetricsSnapshot.source == "youtube_insights",
            MetricsSnapshot.captured_at >= cutoff,
        )
        .order_by(MetricsSnapshot.captured_at.asc(), MetricsSnapshot.id.asc())
    ).all()
    return ReleaseInsightsHistoryRead(
        release=release_read(session, release),
        snapshots=[MetricsSnapshotRead.model_validate(snapshot) for snapshot in snapshots],
    )


@router.get("/insights/sync-targets", response_model=list[InsightSyncTarget], dependencies=[Depends(require_worker_token)])
def list_insight_sync_targets(
    limit: int = Query(default=settings.INSIGHTS_BATCH_LIMIT, ge=1, le=200),
    session: Session = Depends(get_session),
) -> list[InsightSyncTarget]:
    now = datetime.now(timezone.utc)
    due_before = now - timedelta(seconds=max(settings.INSIGHTS_SYNC_INTERVAL_SEC - 60, 60))
    targets: list[InsightSyncTarget] = []
    for release in _published_youtube_short_releases(session, days=settings.INSIGHTS_LOOKBACK_DAYS):
        if not release.platform_video_id or not release.published_at:
            continue
        latest = latest_release_snapshot(session, release.id or 0)
        if latest and latest.captured_at and latest.captured_at > due_before:
            continue
        targets.append(
            InsightSyncTarget(
                release_id=release.id or 0,
                story_id=release.story_id,
                title=release.title,
                platform_video_id=release.platform_video_id,
                published_at=release.published_at,
                last_synced_at=latest.captured_at if latest else None,
            )
        )
        if len(targets) >= limit:
            break
    return targets


@router.post("/insights/snapshots", response_model=MetricsSnapshotRead, dependencies=[Depends(require_worker_token)])
def create_or_update_snapshot(
    payload: InsightSnapshotCreate,
    session: Session = Depends(get_session),
) -> MetricsSnapshotRead:
    release = session.get(Release, payload.release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    if release.platform != "youtube" or release.variant != RenderVariant.SHORT.value:
        raise HTTPException(status_code=400, detail="Only YouTube short releases can receive insights snapshots")
    if not release.published_at or not release.script_version_id:
        raise HTTPException(status_code=400, detail="Release is missing publish/script context")

    captured_at = (payload.captured_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    window_hours = max(
        1,
        int((captured_at - release.published_at.astimezone(timezone.utc)).total_seconds() // 3600),
    )
    metrics = {key: float(value or 0.0) for key, value in payload.metrics.items()}
    derived = compute_derived_metrics(metrics)
    snapshot = session.exec(
        select(MetricsSnapshot)
        .where(
            MetricsSnapshot.release_id == release.id,
            MetricsSnapshot.source == payload.source,
            MetricsSnapshot.window_hours == window_hours,
        )
        .order_by(MetricsSnapshot.id.desc())
    ).first()
    if snapshot is None:
        snapshot = MetricsSnapshot(
            release_id=release.id,
            story_id=release.story_id,
            script_version_id=release.script_version_id,
            story_part_id=release.story_part_id,
            window_hours=window_hours,
            source=payload.source,
            metrics=metrics,
            derived_metrics=derived,
            captured_at=captured_at,
        )
    else:
        snapshot.metrics = metrics
        snapshot.derived_metrics = derived
        snapshot.captured_at = captured_at

    release.provider_metadata = {
        **(release.provider_metadata or {}),
        "latest_youtube_metrics": metrics,
        "insights_last_synced_at": captured_at.isoformat(),
    }
    session.add(snapshot)
    session.add(release)
    session.commit()
    session.refresh(snapshot)
    return MetricsSnapshotRead.model_validate(snapshot)
