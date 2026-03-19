import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from apps.api.db import get_session
import apps.api.main as main
import apps.api.render_jobs as render_jobs
from apps.api.models import AssetBundle, Job, PublishJob, Release, RenderPreset, Story, StoryPart
from apps.api.pipeline import ensure_default_presets
from shared.workflow import PublishApprovalStatus, PublishDeliveryMode, ReleaseStatus


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer local-admin"}


@pytest.fixture(name="client")
def client_fixture(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(render_jobs.settings, "API_AUTH_TOKEN", "local-admin")
    main.app.dependency_overrides[get_session] = get_test_session
    with Session(engine) as session:
        ensure_default_presets(session)
    with TestClient(main.app) as client:
        yield client, engine
    main.app.dependency_overrides.clear()


def _create_job(session: Session, *, auto_schedule_release: bool = False) -> int:
    story = Story(title="Story", status="queued")
    session.add(story)
    session.flush()
    asset = {
        "key": "pixabay:123",
        "type": "image",
        "remote_url": "https://example.com/fog.jpg",
        "provider": "pixabay",
        "provider_id": "123",
    }
    preset = session.exec(select(RenderPreset)).first()
    if preset is None:
        preset = RenderPreset(
            slug="short-form",
            name="Short",
            variant="short",
            width=1080,
            height=1920,
            fps=30,
        )
        session.add(preset)
        session.flush()
    bundle = AssetBundle(
        story_id=story.id,
        name="Primary",
        asset_refs=[asset],
        part_asset_map=[],
    )
    session.add(bundle)
    session.flush()
    part = StoryPart(
        story_id=story.id,
        script_version_id=None,
        asset_bundle_id=bundle.id,
        index=1,
        body_md="I ran.",
        source_text="I ran.",
        script_text="I ran.",
        est_seconds=2,
        approved=True,
    )
    session.add(part)
    session.flush()
    bundle.part_asset_map = [{"story_part_id": part.id, "asset": asset}]
    session.add(bundle)
    job = Job(
        story_id=story.id,
        story_part_id=part.id,
        asset_bundle_id=bundle.id,
        render_preset_id=preset.id,
        kind="render_part",
        status="queued",
        payload={"story_id": story.id, "story_part_id": part.id, "asset_bundle_id": bundle.id, "render_preset_id": preset.id},
    )
    session.add(job)
    if auto_schedule_release:
        session.add(
            Release(
                story_id=story.id,
                story_part_id=part.id,
                platform="youtube",
                variant="short",
                title="Story Part 1",
                description="desc",
                status=ReleaseStatus.DRAFT.value,
                publish_status=ReleaseStatus.DRAFT.value,
                approval_status=PublishApprovalStatus.APPROVED.value,
                delivery_mode=PublishDeliveryMode.AUTOMATED.value,
                publish_at=datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc),
                approved_at=datetime(2029, 12, 31, 12, 0, tzinfo=timezone.utc),
            )
        )
    session.commit()
    session.refresh(job)
    return job.id


def test_claim_concurrency(client):
    client, engine = client
    with Session(engine) as session:
        job_id = _create_job(session)

    res1 = client.post(f"/render-jobs/{job_id}/claim", json={"lease_seconds": 30}, headers=_auth_headers())
    assert res1.status_code == 200
    res2 = client.post(f"/render-jobs/{job_id}/claim", json={"lease_seconds": 30}, headers=_auth_headers())
    assert res2.status_code == 409


def test_state_machine_and_publish_ready(client):
    client, engine = client
    with Session(engine) as session:
        job_id = _create_job(session)

    assert client.post(f"/render-jobs/{job_id}/claim", json={"lease_seconds": 30}, headers=_auth_headers()).status_code == 200
    context = client.get(f"/render-jobs/{job_id}/context", headers=_auth_headers())
    assert context.status_code == 200
    assert context.json()["selected_asset"]["provider"] == "pixabay"
    assert client.post(f"/render-jobs/{job_id}/status", json={"status": "rendering"}, headers=_auth_headers()).status_code == 200
    res = client.post(
        f"/render-jobs/{job_id}/status",
        json={
            "status": "rendered",
            "artifact_path": "/output/story-1-part-1.mp4",
            "subtitle_path": "/output/story-1-part-1.srt",
            "bytes": 1234,
            "duration_ms": 22000,
            "metadata": {"preset_slug": "short-form"},
        },
        headers=_auth_headers(),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "publish_ready"


def test_rendered_auto_scheduled_release_creates_publish_job(client):
    client, engine = client
    with Session(engine) as session:
        job_id = _create_job(session, auto_schedule_release=True)

    assert client.post(f"/render-jobs/{job_id}/claim", json={"lease_seconds": 30}, headers=_auth_headers()).status_code == 200
    assert client.post(f"/render-jobs/{job_id}/status", json={"status": "rendering"}, headers=_auth_headers()).status_code == 200
    res = client.post(
        f"/render-jobs/{job_id}/status",
        json={
            "status": "rendered",
            "artifact_path": "/output/story-1-part-1.mp4",
            "subtitle_path": "/output/story-1-part-1.srt",
            "bytes": 1234,
            "duration_ms": 22000,
            "metadata": {"preset_slug": "short-form"},
        },
        headers=_auth_headers(),
    )
    assert res.status_code == 200

    with Session(engine) as session:
        release = session.exec(select(Release).where(Release.story_part_id.is_not(None))).first()
        assert release is not None
        assert release.status == ReleaseStatus.SCHEDULED.value
        publish_job = session.exec(select(PublishJob).where(PublishJob.release_id == release.id)).first()
        assert publish_job is not None
        assert publish_job.status == "queued"
        assert publish_job.not_before == datetime(2030, 1, 1, 12, 0)


def test_render_job_routes_require_auth(client):
    client, engine = client
    with Session(engine) as session:
        job_id = _create_job(session)

    res = client.get("/render-jobs", params={"status": "queued"})
    assert res.status_code == 401
    res = client.get(f"/render-jobs/{job_id}/context")
    assert res.status_code == 401


def test_compilation_job_hidden_until_part_jobs_ready(client):
    client, engine = client
    with Session(engine) as session:
        story = Story(title="Story", status="queued")
        session.add(story)
        session.flush()
        preset = session.exec(select(RenderPreset)).first()
        part = StoryPart(
            story_id=story.id,
            index=1,
            body_md="One.",
            source_text="One.",
            script_text="One.",
            est_seconds=2,
            approved=True,
        )
        session.add(part)
        session.flush()
        short_job = Job(
            story_id=story.id,
            story_part_id=part.id,
            kind="render_part",
            status="queued",
            variant="short",
            render_preset_id=preset.id if preset else None,
        )
        compilation_job = Job(
            story_id=story.id,
            compilation_id=1,
            kind="render_compilation",
            status="queued",
            variant="weekly",
            render_preset_id=preset.id if preset else None,
        )
        session.add(short_job)
        session.add(compilation_job)
        session.commit()
        session.refresh(compilation_job)

    res = client.get("/render-jobs", params={"status": "queued"}, headers=_auth_headers())
    assert res.status_code == 200
    ids = {job["id"] for job in res.json()}
    assert compilation_job.id not in ids
