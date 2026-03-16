import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from apps.api.db import get_session
import apps.api.main as main
import apps.api.publish_jobs as publish_jobs_api
import apps.api.public_artifacts as public_artifacts
from apps.api.models import PublishJob, Release, RenderArtifact, Story
from apps.api.publishing import build_signature
from shared.config import settings
from shared.workflow import PublishApprovalStatus, PublishDeliveryMode, ReleaseStatus, RenderVariant


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer local-admin"}


@pytest.fixture(name="client")
def client_fixture(tmp_path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(public_artifacts, "engine", engine)
    monkeypatch.setattr(publish_jobs_api.settings, "API_AUTH_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://testserver")
    monkeypatch.setattr(settings, "ARTIFACT_SIGNING_SECRET", "signing-secret")
    monkeypatch.setattr(settings, "OUTPUT_DIR", output_dir)
    main.app.dependency_overrides[get_session] = get_test_session
    with TestClient(main.app) as client:
        yield client, engine, output_dir
    main.app.dependency_overrides.clear()
    shutil.rmtree(output_dir, ignore_errors=True)


def _create_ready_release(session: Session, output_dir: Path, *, platform: str = "youtube", variant: str = RenderVariant.SHORT.value) -> Release:
    story = Story(title="Publish Story", status="publish_ready")
    session.add(story)
    session.flush()
    video_path = output_dir / f"story-{story.id}-{platform}.mp4"
    video_path.write_bytes(b"video")
    artifact = RenderArtifact(
        story_id=story.id,
        variant=variant,
        video_path=str(video_path),
        bytes=5,
    )
    session.add(artifact)
    session.flush()
    release = Release(
        story_id=story.id,
        render_artifact_id=artifact.id,
        platform=platform,
        variant=variant,
        title=f"{story.title} {platform}",
        description="desc",
        hashtags=["scarystories"],
        status=ReleaseStatus.READY.value,
        publish_status=ReleaseStatus.READY.value,
        approval_status=PublishApprovalStatus.PENDING.value,
        delivery_mode=PublishDeliveryMode.MANUAL.value if platform == "tiktok" else PublishDeliveryMode.AUTOMATED.value,
    )
    session.add(release)
    session.commit()
    session.refresh(release)
    return release


def test_approve_release_creates_immediate_and_scheduled_publish_jobs(client, monkeypatch: pytest.MonkeyPatch):
    client, engine, output_dir = client
    with Session(engine) as session:
        release = _create_ready_release(session, output_dir)

    res = client.post(
        f"/releases/{release.id}/approve",
        json={"title": "Approved title", "hashtags": ["one", "two"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "approved"
    assert body["title"] == "Approved title"

    with Session(engine) as session:
        publish_job = session.exec(select(PublishJob).where(PublishJob.release_id == release.id)).first()
        assert publish_job is not None
        assert publish_job.status == "queued"
        assert publish_job.not_before is None

    scheduled_release = None
    with Session(engine) as session:
        scheduled_release = _create_ready_release(session, output_dir, platform="instagram")
    monkeypatch.setattr(publish_jobs_api.settings, "ACTIVE_PUBLISH_PLATFORMS", "youtube,instagram")
    res = client.post(
        f"/releases/{scheduled_release.id}/approve",
        json={"publish_at": "2030-01-01T10:00:00Z"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "scheduled"


def test_publish_job_worker_routes_require_auth(client):
    client, engine, output_dir = client
    with Session(engine) as session:
        release = _create_ready_release(session, output_dir)
        publish_job = PublishJob(release_id=release.id, platform=release.platform, status="queued")
        session.add(publish_job)
        session.commit()
        session.refresh(publish_job)

    assert client.get("/publish-jobs", params={"status": "queued"}).status_code == 401
    assert client.get(f"/publish-jobs/{publish_job.id}/context").status_code == 401
    assert client.get("/publish-jobs", params={"status": "queued"}, headers=_auth_headers()).status_code == 200


def test_public_release_asset_signature_validation(client):
    client, engine, output_dir = client
    with Session(engine) as session:
        release = _create_ready_release(session, output_dir)

    exp = 4_102_444_800
    sig = build_signature("release", release.id, exp)
    res = client.get(f"/public/releases/{release.id}/asset?exp={exp}&sig={sig}")
    assert res.status_code == 200
    assert res.content == b"video"

    bad = client.get(f"/public/releases/{release.id}/asset?exp={exp}&sig=nope")
    assert bad.status_code == 403


def test_complete_manual_publish_only_allows_manual_releases(client):
    client, engine, output_dir = client
    release_id = None
    with Session(engine) as session:
        release = _create_ready_release(session, output_dir, platform="tiktok")
        release.status = ReleaseStatus.MANUAL_HANDOFF.value
        release.publish_status = ReleaseStatus.MANUAL_HANDOFF.value
        release.approval_status = PublishApprovalStatus.APPROVED.value
        publish_job = PublishJob(release_id=release.id, platform=release.platform, status="published")
        session.add(release)
        session.add(publish_job)
        session.commit()
        release_id = release.id

    res = client.post(
        f"/releases/{release_id}/complete-manual-publish",
        json={"platform_video_id": "tt-123", "notes": "posted"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "published"
    assert res.json()["platform_video_id"] == "tt-123"

    with Session(engine) as session:
        youtube_release = _create_ready_release(session, output_dir, platform="youtube")
    bad = client.post(
        f"/releases/{youtube_release.id}/complete-manual-publish",
        json={"platform_video_id": "yt-123"},
    )
    assert bad.status_code == 409
