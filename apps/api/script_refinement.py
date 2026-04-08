"""Experiment-driven script refinement routes and worker contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlmodel import SQLModel, Session, select

from shared.config import settings
from shared.workflow import JobStatus, can_transition_job

from .db import get_session
from .models import (
    AnalysisReport,
    AnalysisReportRead,
    AssetBundle,
    Job,
    JobRead,
    MetricsSnapshot,
    MetricsSnapshotRead,
    PromptVersion,
    PromptVersionRead,
    Release,
    ReleaseRead,
    RenderPreset,
    ScriptBatch,
    ScriptBatchRead,
    ScriptVersion,
    ScriptVersionRead,
    Story,
    StoryConcept,
    StoryConceptRead,
    StoryPart,
    StoryPartRead,
)
from .pipeline import create_short_releases, ensure_default_presets
from .publishing import active_publish_platforms, release_read, validate_release_platform
from .refinement import (
    activate_script_version,
    build_analysis,
    compute_derived_metrics,
    ensure_default_prompt_versions,
    extract_concept_payload,
    generate_candidate_payloads,
    metric_windows_due,
    persist_candidates,
    release_metrics_payload,
    score_script_versions,
    upsert_story_concept,
)

router = APIRouter(tags=["refinement"])

DEFAULT_LEASE_SECONDS = 180
REFINEMENT_KIND_PREFIX = "refine_"
EXTRACT_JOB = "refine_extract_concept"
GENERATE_JOB = "refine_generate_batch"
CRITIC_JOB = "refine_critic_batch"
METRICS_JOB = "refine_collect_metrics"
ANALYZE_JOB = "refine_analyze_batch"


class ClaimRequest(SQLModel):
    lease_seconds: int = DEFAULT_LEASE_SECONDS


class ScriptBatchCreate(SQLModel):
    candidate_count: int = settings.REFINEMENT_DEFAULT_BATCH_SIZE
    shortlisted_count: int = settings.REFINEMENT_DEFAULT_SHORTLIST_SIZE
    temperature: float = 1.0


class ScriptSelectionUpdate(SQLModel):
    state: str = "shortlisted"


class ScriptVersionReleaseCreate(SQLModel):
    platforms: list[str] = ["youtube"]
    preset_slug: str = "short-form"
    asset_bundle_id: int | None = None


class PromptVersionCreate(SQLModel):
    kind: str
    version_label: str
    body: str
    config: dict[str, Any] | None = None
    notes: str | None = None
    status: str = "draft"


class RefinementJobStatusUpdate(BaseModel):
    status: str
    error_class: str | None = None
    error_message: str | None = None
    stderr_snippet: str | None = None
    metadata: dict[str, Any] | None = None


def require_worker_token(authorization: str | None = Header(default=None)) -> None:
    expected = settings.API_AUTH_TOKEN
    if not expected or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    if token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _get_story(session: Session, story_id: int) -> Story:
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


def _batch_scripts(session: Session, batch_id: int) -> list[ScriptVersion]:
    return session.exec(
        select(ScriptVersion)
        .where(ScriptVersion.batch_id == batch_id)
        .order_by(ScriptVersion.critic_rank.is_(None), ScriptVersion.critic_rank, ScriptVersion.id)
    ).all()


def _script_parts(session: Session, script_version_id: int) -> list[StoryPart]:
    return session.exec(
        select(StoryPart)
        .where(StoryPart.script_version_id == script_version_id)
        .order_by(StoryPart.index)
    ).all()


def _serialize_script(session: Session, script: ScriptVersion) -> dict[str, Any]:
    return {
        **ScriptVersionRead.model_validate(script).model_dump(),
        "parts": [StoryPartRead.model_validate(part).model_dump() for part in _script_parts(session, script.id or 0)],
    }


def _serialize_batch_detail(session: Session, batch: ScriptBatch) -> dict[str, Any]:
    concept = session.get(StoryConcept, batch.concept_id) if batch.concept_id else None
    report = session.exec(
        select(AnalysisReport).where(AnalysisReport.batch_id == batch.id).order_by(AnalysisReport.id.desc())
    ).first()
    return {
        "batch": ScriptBatchRead.model_validate(batch).model_dump(),
        "concept": StoryConceptRead.model_validate(concept).model_dump() if concept else None,
        "candidates": [_serialize_script(session, script) for script in _batch_scripts(session, batch.id or 0)],
        "report": AnalysisReportRead.model_validate(report).model_dump() if report else None,
    }


def _existing_refinement_jobs(session: Session, batch_id: int, kind: str) -> list[Job]:
    jobs = session.exec(select(Job).where(Job.kind == kind)).all()
    return [job for job in jobs if (job.payload or {}).get("batch_id") == batch_id]


def _enqueue_refinement_job(
    session: Session,
    *,
    batch: ScriptBatch,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> Job:
    for existing in _existing_refinement_jobs(session, batch.id or 0, kind):
        if existing.status in {JobStatus.QUEUED.value, JobStatus.CLAIMED.value, JobStatus.RENDERING.value}:
            return existing
    job = Job(
        story_id=batch.story_id,
        script_version_id=None,
        kind=kind,
        status=JobStatus.QUEUED.value,
        variant="short",
        correlation_id=f"batch-{batch.id}-{kind}",
        payload={"batch_id": batch.id, **(payload or {})},
    )
    session.add(job)
    session.flush()
    return job


def _apply_metrics_for_window(session: Session, batch: ScriptBatch, window_hours: int) -> None:
    scripts = _batch_scripts(session, batch.id or 0)
    policy_prompt = session.exec(
        select(PromptVersion)
        .where(PromptVersion.kind == "selection_policy", PromptVersion.status == "active")
        .order_by(PromptVersion.id.desc())
    ).first()
    weights = ((policy_prompt.config or {}).get("weights") if policy_prompt and policy_prompt.config else None) or {}
    for script in scripts:
        parts = _script_parts(session, script.id or 0)
        release_rows = session.exec(
            select(Release)
            .where(Release.script_version_id == script.id, Release.platform == "youtube", Release.published_at.is_not(None))
            .order_by(Release.story_part_id)
        ).all()
        part_metrics: list[dict[str, float]] = []
        metrics_by_index: dict[int, dict[str, float]] = {}
        for release in release_rows:
            metrics = release_metrics_payload(release)
            derived = compute_derived_metrics(metrics, policy_weights=weights)
            snapshot = session.exec(
                select(MetricsSnapshot)
                .where(
                    MetricsSnapshot.release_id == release.id,
                    MetricsSnapshot.window_hours == window_hours,
                )
            ).first()
            if not snapshot:
                snapshot = MetricsSnapshot(
                    release_id=release.id,
                    story_id=release.story_id,
                    script_version_id=release.script_version_id or script.id or 0,
                    story_part_id=release.story_part_id,
                    window_hours=window_hours,
                    metrics=metrics,
                    derived_metrics=derived,
                )
            else:
                snapshot.metrics = metrics
                snapshot.derived_metrics = derived
                snapshot.captured_at = datetime.now(timezone.utc)
            session.add(snapshot)
            part = session.get(StoryPart, release.story_part_id) if release.story_part_id else None
            if part:
                part.performance_metrics = metrics
                part.derived_metrics = derived
                session.add(part)
                metrics_by_index[part.index] = metrics
            part_metrics.append(metrics)
        if part_metrics:
            aggregate = {
                "impressions": sum(item.get("impressions", 0.0) for item in part_metrics),
                "views": sum(item.get("views", 0.0) for item in part_metrics),
                "avg_view_duration": sum(item.get("avg_view_duration", 0.0) for item in part_metrics) / len(part_metrics),
                "percent_viewed": sum(item.get("percent_viewed", 0.0) for item in part_metrics) / len(part_metrics),
                "completion_rate": sum(item.get("completion_rate", 0.0) for item in part_metrics) / len(part_metrics),
                "likes": sum(item.get("likes", 0.0) for item in part_metrics),
                "comments": sum(item.get("comments", 0.0) for item in part_metrics),
                "shares": sum(item.get("shares", 0.0) for item in part_metrics),
                "subs_gained": sum(item.get("subs_gained", 0.0) for item in part_metrics),
            }
            derived = compute_derived_metrics(aggregate, policy_weights=weights)
            for index in sorted(metrics_by_index):
                if index == 1 or not aggregate.get("views"):
                    continue
                derived[f"part_{index}_views_ratio"] = round(
                    float(metrics_by_index[index].get("views") or 0.0) / max(float(metrics_by_index.get(1, {}).get("views") or 1.0), 1.0),
                    4,
                )
            script.performance_metrics = aggregate
            script.derived_metrics = derived
            session.add(script)
    ranked = sorted(
        [script for script in scripts if script.derived_metrics],
        key=lambda item: float((item.derived_metrics or {}).get("performance_score") or 0.0),
        reverse=True,
    )
    for index, script in enumerate(ranked, start=1):
        script.performance_rank = index
        session.add(script)
    batch.status = "metrics_ready" if window_hours >= 72 else "metrics_pending"
    session.add(batch)
    session.flush()


def _ensure_analysis_job(session: Session, batch: ScriptBatch) -> None:
    existing_report = session.exec(select(AnalysisReport).where(AnalysisReport.batch_id == batch.id)).first()
    if existing_report:
        return
    _enqueue_refinement_job(session, batch=batch, kind=ANALYZE_JOB)


def run_compat_script_generation(session: Session, story: Story) -> ScriptVersion:
    ensure_default_prompt_versions(session)
    batch = ScriptBatch(
        story_id=story.id,
        status="processing",
        candidate_count=1,
        shortlisted_count=1,
        prompt_version="gen_prompt_v1",
        critic_version="critic_v1",
        analyst_version="analyst_v1",
        selection_policy_version="selection_policy_v1",
        template_version="template_v1",
        model_name=settings.OPENAI_SCRIPT_MODEL,
        temperature=1.0,
        config={"compat": True},
    )
    session.add(batch)
    session.flush()
    concept = upsert_story_concept(session, story, extract_concept_payload(story, session=session))
    batch.concept_id = concept.id
    candidates = generate_candidate_payloads(story, concept=concept, candidate_count=1, session=session)
    scripts = persist_candidates(session, story=story, batch=batch, concept=concept, candidates=candidates[:1])
    ranked = score_script_versions(session, scripts, shortlist_size=1)
    script = activate_script_version(session, ranked[0])
    script.selection_state = "selected"
    batch.status = "ready_for_review"
    batch.result = {"script_version_id": script.id}
    session.add(script)
    session.add(batch)
    story.status = "scripted"
    session.add(story)
    session.flush()
    return script


@router.post("/stories/{story_id}/script-batches")
def create_script_batch(
    story_id: int,
    payload: ScriptBatchCreate,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    story = _get_story(session, story_id)
    ensure_default_prompt_versions(session)
    candidate_count = max(1, min(payload.candidate_count, 30))
    batch = ScriptBatch(
        story_id=story.id,
        status="queued",
        candidate_count=candidate_count,
        shortlisted_count=max(1, min(payload.shortlisted_count, candidate_count)),
        prompt_version="gen_prompt_v1",
        critic_version="critic_v1",
        analyst_version="analyst_v1",
        selection_policy_version="selection_policy_v1",
        template_version="template_v1",
        model_name=settings.OPENAI_SCRIPT_MODEL,
        temperature=payload.temperature,
    )
    session.add(batch)
    session.flush()
    _enqueue_refinement_job(session, batch=batch, kind=EXTRACT_JOB)
    session.commit()
    return _serialize_batch_detail(session, batch)


@router.get("/stories/{story_id}/script-batches", response_model=list[ScriptBatchRead])
def list_story_batches(story_id: int, session: Session = Depends(get_session)) -> list[ScriptBatch]:
    _get_story(session, story_id)
    return session.exec(
        select(ScriptBatch).where(ScriptBatch.story_id == story_id).order_by(ScriptBatch.id.desc())
    ).all()


@router.get("/script-batches/{batch_id}")
def get_script_batch(batch_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    batch = session.get(ScriptBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Script batch not found")
    return _serialize_batch_detail(session, batch)


@router.post("/script-versions/{script_version_id}/select", response_model=ScriptVersionRead)
def select_script_version(
    script_version_id: int,
    payload: ScriptSelectionUpdate,
    session: Session = Depends(get_session),
) -> ScriptVersion:
    script = session.get(ScriptVersion, script_version_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script version not found")
    script.selection_state = payload.state
    session.add(script)
    session.commit()
    session.refresh(script)
    return script


@router.post("/script-versions/{script_version_id}/activate", response_model=ScriptVersionRead)
def activate_script(
    script_version_id: int,
    session: Session = Depends(get_session),
) -> ScriptVersion:
    script = session.get(ScriptVersion, script_version_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script version not found")
    activate_script_version(session, script)
    session.commit()
    session.refresh(script)
    return script


@router.get("/script-versions/{script_version_id}/parts", response_model=list[StoryPartRead])
def script_version_parts(script_version_id: int, session: Session = Depends(get_session)) -> list[StoryPart]:
    script = session.get(ScriptVersion, script_version_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script version not found")
    return _script_parts(session, script_version_id)


@router.get("/script-versions/{script_version_id}/metrics")
def script_version_metrics(script_version_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    script = session.get(ScriptVersion, script_version_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script version not found")
    snapshots = session.exec(
        select(MetricsSnapshot)
        .where(MetricsSnapshot.script_version_id == script_version_id)
        .order_by(MetricsSnapshot.window_hours, MetricsSnapshot.story_part_id)
    ).all()
    return {
        "script": ScriptVersionRead.model_validate(script).model_dump(),
        "snapshots": [MetricsSnapshotRead.model_validate(snapshot).model_dump() for snapshot in snapshots],
    }


@router.post("/script-versions/{script_version_id}/releases", response_model=list[ReleaseRead])
def create_script_version_releases(
    script_version_id: int,
    payload: ScriptVersionReleaseCreate,
    session: Session = Depends(get_session),
) -> list[ReleaseRead]:
    script = session.get(ScriptVersion, script_version_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script version not found")
    story = _get_story(session, script.story_id)
    ensure_default_presets(session)
    preset = session.exec(select(RenderPreset).where(RenderPreset.slug == payload.preset_slug)).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Render preset not found")
    platforms = payload.platforms or active_publish_platforms(session)
    for platform in platforms:
        validate_release_platform(platform, preset.variant, session)
    bundle_id = payload.asset_bundle_id or story.active_asset_bundle_id
    if not bundle_id:
        raise HTTPException(status_code=400, detail="Active asset bundle required")
    bundle = session.get(AssetBundle, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Asset bundle not found")
    parts = _script_parts(session, script_version_id)
    if not parts:
        raise HTTPException(status_code=400, detail="Script version does not have parts")
    if not (bundle.asset_refs or []):
        raise HTTPException(status_code=400, detail="Asset bundle must include asset_refs")
    releases, _jobs = create_short_releases(
        session,
        story,
        platforms=platforms,
        preset=preset,
        asset_bundle=bundle,
        script_version=script,
    )
    for created in releases:
        created.script_version_id = script.id
        session.add(created)
    session.commit()
    return [release_read(session, release) for release in releases]


@router.get("/analysis-reports", response_model=list[AnalysisReportRead])
def list_analysis_reports(
    story_id: int | None = None,
    batch_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[AnalysisReport]:
    query = select(AnalysisReport)
    if story_id is not None:
        query = query.where(AnalysisReport.story_id == story_id)
    if batch_id is not None:
        query = query.where(AnalysisReport.batch_id == batch_id)
    return session.exec(query.order_by(AnalysisReport.id.desc())).all()


@router.get("/prompt-versions", response_model=list[PromptVersionRead])
def list_prompt_versions(
    kind: str | None = None,
    session: Session = Depends(get_session),
) -> list[PromptVersion]:
    ensure_default_prompt_versions(session)
    query = select(PromptVersion)
    if kind:
        query = query.where(PromptVersion.kind == kind)
    return session.exec(query.order_by(PromptVersion.kind, PromptVersion.id.desc())).all()


@router.post("/prompt-versions", response_model=PromptVersionRead)
def create_prompt_version(
    payload: PromptVersionCreate,
    session: Session = Depends(get_session),
) -> PromptVersion:
    prompt = PromptVersion(
        kind=payload.kind,
        version_label=payload.version_label,
        body=payload.body,
        config=payload.config,
        notes=payload.notes,
        status=payload.status,
    )
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return prompt


@router.post("/prompt-versions/{prompt_version_id}/activate", response_model=PromptVersionRead)
def activate_prompt_version(
    prompt_version_id: int,
    session: Session = Depends(get_session),
) -> PromptVersion:
    prompt = session.get(PromptVersion, prompt_version_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    for sibling in session.exec(select(PromptVersion).where(PromptVersion.kind == prompt.kind)).all():
        sibling.status = "active" if sibling.id == prompt.id else "archived"
        session.add(sibling)
    session.commit()
    session.refresh(prompt)
    return prompt


@router.post("/prompt-versions/{prompt_version_id}/archive", response_model=PromptVersionRead)
def archive_prompt_version(
    prompt_version_id: int,
    session: Session = Depends(get_session),
) -> PromptVersion:
    prompt = session.get(PromptVersion, prompt_version_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt version not found")
    prompt.status = "archived"
    session.add(prompt)
    session.commit()
    session.refresh(prompt)
    return prompt


@router.post("/refinement-jobs/maintenance")
def enqueue_due_refinement_jobs(
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict[str, int]:
    enqueued = 0
    due_windows = metric_windows_due(session)
    for batch, window in due_windows:
        _enqueue_refinement_job(session, batch=batch, kind=METRICS_JOB, payload={"window_hours": window})
        enqueued += 1
    batches = session.exec(select(ScriptBatch).where(ScriptBatch.status.in_(["metrics_ready", "published"]))).all()
    for batch in batches:
        snapshots = session.exec(
            select(MetricsSnapshot).where(
                MetricsSnapshot.script_version_id.in_([script.id for script in _batch_scripts(session, batch.id or 0) if script.id is not None]),
                MetricsSnapshot.window_hours == 72,
            )
        ).all()
        if snapshots:
            _ensure_analysis_job(session, batch)
    session.commit()
    return {"enqueued": enqueued}


@router.get("/refinement-jobs", response_model=list[JobRead])
def list_refinement_jobs(
    status: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> list[Job]:
    query = select(Job).where(Job.kind.ilike(f"{REFINEMENT_KIND_PREFIX}%"))
    if status:
        query = query.where(Job.status == status)
    return session.exec(query.order_by(Job.id).limit(limit)).all()


@router.post("/refinement-jobs/{job_id}/claim")
def claim_refinement_job(
    job_id: int,
    request: ClaimRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if not job or not job.kind.startswith(REFINEMENT_KIND_PREFIX):
        raise HTTPException(status_code=404, detail="Refinement job not found")
    if job.status != JobStatus.QUEUED.value:
        raise HTTPException(status_code=409, detail="Invalid state")
    job.status = JobStatus.CLAIMED.value
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.lease_seconds)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


@router.post("/refinement-jobs/{job_id}/heartbeat")
def heartbeat_refinement_job(
    job_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if not job or not job.kind.startswith(REFINEMENT_KIND_PREFIX):
        raise HTTPException(status_code=404, detail="Refinement job not found")
    if job.status not in {JobStatus.CLAIMED.value, JobStatus.RENDERING.value}:
        raise HTTPException(status_code=409, detail="Invalid state")
    if job.lease_expires_at and job.lease_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Lease expired")
    job.lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=DEFAULT_LEASE_SECONDS)
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"lease_expires_at": job.lease_expires_at}


@router.get("/refinement-jobs/{job_id}/context")
def refinement_job_context(
    job_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if not job or not job.kind.startswith(REFINEMENT_KIND_PREFIX):
        raise HTTPException(status_code=404, detail="Refinement job not found")
    batch_id = (job.payload or {}).get("batch_id")
    batch = session.get(ScriptBatch, batch_id) if batch_id else None
    if not batch:
        raise HTTPException(status_code=404, detail="Script batch not found")
    story = _get_story(session, batch.story_id)
    concept = session.get(StoryConcept, batch.concept_id) if batch.concept_id else None
    scripts = _batch_scripts(session, batch.id or 0)
    return {
        "job": job.model_dump(),
        "batch": ScriptBatchRead.model_validate(batch).model_dump(),
        "story": story.model_dump(),
        "concept": StoryConceptRead.model_validate(concept).model_dump() if concept else None,
        "prompts": {prompt.kind: PromptVersionRead.model_validate(prompt).model_dump() for prompt in session.exec(select(PromptVersion)).all()},
        "scripts": [_serialize_script(session, script) for script in scripts],
        "releases": [release_read(session, release).model_dump() for release in session.exec(select(Release).where(Release.script_version_id.in_([script.id for script in scripts if script.id is not None]))).all()] if scripts else [],
    }


@router.post("/refinement-jobs/{job_id}/status")
def update_refinement_job_status(
    job_id: int,
    update: RefinementJobStatusUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_worker_token),
) -> Job:
    job = session.get(Job, job_id)
    if not job or not job.kind.startswith(REFINEMENT_KIND_PREFIX):
        raise HTTPException(status_code=404, detail="Refinement job not found")
    if update.status != job.status and not can_transition_job(job.status, update.status):
        raise HTTPException(status_code=409, detail="Invalid state transition")
    batch_id = (job.payload or {}).get("batch_id")
    batch = session.get(ScriptBatch, batch_id) if batch_id else None
    if not batch:
        raise HTTPException(status_code=404, detail="Script batch not found")
    story = _get_story(session, batch.story_id)

    job.status = update.status
    job.error_class = update.error_class
    job.error_message = update.error_message
    job.stderr_snippet = update.stderr_snippet
    if update.metadata:
        job.result = {**(job.result or {}), **update.metadata}

    if update.status == JobStatus.RENDERING.value:
        batch.status = "processing"
    elif update.status == JobStatus.ERRORED.value:
        batch.status = "errored"
        batch.error_message = update.error_message
    elif update.status == JobStatus.RENDERED.value:
        if job.kind == EXTRACT_JOB:
            concept_payload = (update.metadata or {}).get("concept") or extract_concept_payload(story, session=session)
            concept = upsert_story_concept(session, story, concept_payload)
            batch.concept_id = concept.id
            batch.status = "concept_ready"
            _enqueue_refinement_job(session, batch=batch, kind=GENERATE_JOB)
        elif job.kind == GENERATE_JOB:
            concept = session.get(StoryConcept, batch.concept_id) if batch.concept_id else None
            candidates = (update.metadata or {}).get("candidates") or generate_candidate_payloads(
                story,
                concept=concept,
                candidate_count=batch.candidate_count,
                session=session,
            )
            for script in _batch_scripts(session, batch.id or 0):
                for part in _script_parts(session, script.id or 0):
                    session.delete(part)
                session.delete(script)
            persist_candidates(session, story=story, batch=batch, concept=concept, candidates=candidates[: batch.candidate_count])
            batch.status = "generated"
            batch.result = {"candidate_count": min(len(candidates), batch.candidate_count)}
            _enqueue_refinement_job(session, batch=batch, kind=CRITIC_JOB)
        elif job.kind == CRITIC_JOB:
            ranked = score_script_versions(session, _batch_scripts(session, batch.id or 0), batch.shortlisted_count)
            batch.status = "ready_for_review"
            batch.result = {
                **(batch.result or {}),
                "shortlist_ids": [script.id for script in ranked[: batch.shortlisted_count]],
            }
        elif job.kind == METRICS_JOB:
            window_hours = int((job.payload or {}).get("window_hours") or 24)
            _apply_metrics_for_window(session, batch, window_hours)
            if window_hours >= 72:
                _ensure_analysis_job(session, batch)
        elif job.kind == ANALYZE_JOB:
            report = build_analysis(session, batch, metrics_window_hours=72)
            batch.status = "analysis_ready"
            batch.result = {**(batch.result or {}), "analysis_report_id": report.id}

    session.add(batch)
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


__all__ = ["router", "run_compat_script_generation"]
