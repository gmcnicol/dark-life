import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from apps.api.db import get_session
import apps.api.main as main
import apps.api.stories as stories_api
from apps.api.models import Release, Story
from apps.api.pipeline import ensure_default_presets
from shared.workflow import PublishApprovalStatus, PublishDeliveryMode, ReleaseStatus, RenderVariant


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

    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "engine", engine)
    main.app.dependency_overrides[get_session] = get_test_session
    monkeypatch.setenv("API_AUTH_TOKEN", "local-admin")
    with TestClient(main.app) as client:
        with Session(engine) as session:
            ensure_default_presets(session)
        yield client, engine
    main.app.dependency_overrides.clear()


def test_generate_script_and_parts(client):
    client, engine = client
    story = client.post("/stories", json={"title": "My Story", "body_md": "I heard a noise. Then I opened the door. It was empty."}).json()

    res = client.post(f"/stories/{story['id']}/script")
    assert res.status_code == 200
    script = res.json()
    assert script["narration_text"]

    parts = client.get(f"/stories/{story['id']}/parts")
    assert parts.status_code == 200
    assert len(parts.json()) >= 1


def test_extract_image_keywords_biases_search_to_eerie_feel():
    story = Story(
        title="The Woman At My Window",
        body_md="Every night the house felt empty and silent, like something was watching me from outside.",
    )

    keywords = stories_api._extract_image_keywords(story).split()

    assert keywords[:3] == ["eerie", "dark", "moody"]
    assert "window" not in keywords
    assert "woman" not in keywords
    assert "house" not in keywords
    assert "shadows" in keywords or "silhouette" in keywords


def test_story_asset_index_uses_mood_first_pixabay_query(client, monkeypatch: pytest.MonkeyPatch):
    client, _engine = client
    captured: dict[str, str] = {}

    def fake_fetch(keywords: str):
        captured["keywords"] = keywords
        return [
            {
                "remote_url": "https://example.com/eerie.jpg",
                "provider": "pixabay",
                "provider_id": "asset-1",
                "type": "image",
                "orientation": "portrait",
                "tags": ["eerie", "mist"],
                "width": 1080,
                "height": 1920,
                "attribution": "tester",
            }
        ]

    monkeypatch.setattr(stories_api, "_fetch_pixabay_assets", fake_fetch)

    story = client.post(
        "/stories",
        json={
            "title": "The Knife In The Kitchen",
            "body_md": "I saw a knife on the floor, but what stayed with me was the silent, empty feeling in the room all night.",
        },
    ).json()

    res = client.post(f"/stories/{story['id']}/assets/index")

    assert res.status_code == 200
    keywords = captured["keywords"].split()
    assert keywords[:3] == ["eerie", "dark", "moody"]
    assert "knife" not in keywords
    assert "kitchen" not in keywords
    assert "silent" not in keywords


def test_create_bundle_and_release_jobs(client, tmp_path, monkeypatch: pytest.MonkeyPatch):
    client, engine = client
    monkeypatch.setattr(
        stories_api,
        "_fetch_pixabay_assets",
        lambda keywords: [
            {
                "remote_url": "https://example.com/fog.jpg",
                "provider": "pixabay",
                "provider_id": "asset-1",
                "type": "image",
                "orientation": "portrait",
                "tags": ["fog", "night"],
                "width": 1080,
                "height": 1920,
                "attribution": "tester",
            }
        ],
    )

    story = client.post(
        "/stories",
        json={
            "title": "Pipeline",
            "body_md": "I walked home. I saw something in the fog. I kept moving.",
            "author": "nightwriter",
            "subreddit": "nosleep",
            "source_url": "https://reddit.com/r/nosleep/comments/example",
        },
    ).json()
    client.post(f"/stories/{story['id']}/script")

    assets = client.post(f"/stories/{story['id']}/assets/index").json()
    assert len(assets) >= 1

    bundle = client.post(
        f"/stories/{story['id']}/asset-bundles",
        json={"name": "Primary", "asset_ids": [assets[0]["id"]]},
    )
    assert bundle.status_code == 200
    assert bundle.json()["part_asset_map"]

    releases = client.post(
        f"/stories/{story['id']}/releases",
        json={
            "platforms": ["youtube"],
            "preset_slug": "short-form",
            "asset_bundle_id": bundle.json()["id"],
        },
    )
    assert releases.status_code == 200
    assert len(releases.json()) >= 1
    assert "Part" in releases.json()[0]["title"]
    assert "#darklifestories" in releases.json()[0]["description"].lower()
    assert "darklifestories" in releases.json()[0]["hashtags"]
    assert "Original post:" in releases.json()[0]["description"]
    assert "u/nightwriter" in releases.json()[0]["description"]
    assert "reddit.com/r/nosleep/comments/example" in releases.json()[0]["description"]
    assert releases.json()[0]["publish_at"] is not None
    assert releases.json()[0]["approval_status"] == "approved"

    jobs = client.get("/jobs", params={"story_id": story["id"]})
    assert jobs.status_code == 200
    assert len(jobs.json()) >= 1
    assert jobs.json()[0]["kind"] == "render_part"


def test_create_weekly_compilation(client):
    client, _engine = client
    story = client.post("/stories", json={"title": "Weekly", "body_md": "I ran. I hid. I survived."}).json()
    client.post(f"/stories/{story['id']}/script")
    res = client.post(
        f"/stories/{story['id']}/compilations",
        json={"preset_slug": "weekly-full", "platforms": ["youtube"]},
    )
    assert res.status_code == 200
    compilation = res.json()
    assert compilation["title"].startswith("Weekly")

    releases = client.get(f"/stories/{story['id']}/releases").json()
    assert any("Full Story" in release["title"] for release in releases)
    assert any("darklifestories" in (release["hashtags"] or []) for release in releases)

    jobs = client.get("/jobs", params={"story_id": story["id"]}).json()
    assert any(job["kind"] == "render_compilation" for job in jobs)


def test_weekly_compilation_rejects_non_youtube_platform(client):
    client, _engine = client
    story = client.post("/stories", json={"title": "Weekly", "body_md": "I ran. I hid. I survived."}).json()
    client.post(f"/stories/{story['id']}/script")
    res = client.post(
        f"/stories/{story['id']}/compilations",
        json={"preset_slug": "weekly-full", "platforms": ["instagram"]},
    )
    assert res.status_code == 400


def test_short_release_rejects_inactive_platform(client, monkeypatch: pytest.MonkeyPatch):
    client, _engine = client
    monkeypatch.setattr(stories_api.settings, "ACTIVE_PUBLISH_PLATFORMS", "youtube")
    story = client.post("/stories", json={"title": "Inactive Platform", "body_md": "One. Two. Three."}).json()
    client.post(f"/stories/{story['id']}/script")
    monkeypatch.setattr(
        stories_api,
        "_fetch_pixabay_assets",
        lambda keywords: [
            {
                "remote_url": "https://example.com/fog.jpg",
                "provider": "pixabay",
                "provider_id": "asset-1",
                "type": "image",
                "orientation": "portrait",
                "tags": ["fog"],
                "width": 1080,
                "height": 1920,
                "attribution": "tester",
            }
        ],
    )
    assets = client.post(f"/stories/{story['id']}/assets/index").json()
    bundle = client.post(
        f"/stories/{story['id']}/asset-bundles",
        json={"name": "Primary", "asset_ids": [assets[0]["id"]]},
    ).json()
    res = client.post(
        f"/stories/{story['id']}/releases",
        json={
            "platforms": ["instagram"],
            "preset_slug": "short-form",
            "asset_bundle_id": bundle["id"],
        },
    )
    assert res.status_code == 400


def test_short_release_schedule_follows_existing_queue(client, monkeypatch: pytest.MonkeyPatch):
    client, engine = client
    monkeypatch.setattr(stories_api.settings, "ACTIVE_PUBLISH_PLATFORMS", "youtube")
    monkeypatch.setattr(
        stories_api,
        "_fetch_pixabay_assets",
        lambda keywords: [
            {
                "remote_url": "https://example.com/fog.jpg",
                "provider": "pixabay",
                "provider_id": "asset-1",
                "type": "image",
                "orientation": "portrait",
                "tags": ["fog", "night"],
                "width": 1080,
                "height": 1920,
                "attribution": "tester",
            }
        ],
    )
    with Session(engine) as session:
        prior_story = Story(title="Previous Story", status="publish_ready")
        session.add(prior_story)
        session.flush()
        session.add(
            Release(
                story_id=prior_story.id,
                platform="youtube",
                variant=RenderVariant.SHORT.value,
                title="Previous",
                description="Previous",
                status=ReleaseStatus.SCHEDULED.value,
                publish_status=ReleaseStatus.SCHEDULED.value,
                approval_status=PublishApprovalStatus.APPROVED.value,
                delivery_mode=PublishDeliveryMode.AUTOMATED.value,
                publish_at=datetime(2030, 1, 3, 12, 0, tzinfo=timezone.utc),
            )
        )
        session.commit()

    story = client.post(
        "/stories",
        json={"title": "Cadence", "body_md": "One. Two. Three. Four."},
    ).json()
    client.post(f"/stories/{story['id']}/script")
    client.put(
        f"/stories/{story['id']}/parts",
        json=[
            {"body_md": "One. Two.", "approved": True},
            {"body_md": "Three. Four.", "approved": True},
        ],
    )
    assets = client.post(f"/stories/{story['id']}/assets/index").json()
    bundle = client.post(
        f"/stories/{story['id']}/asset-bundles",
        json={"name": "Primary", "asset_ids": [assets[0]["id"]]},
    ).json()
    releases = client.post(
        f"/stories/{story['id']}/releases",
        json={
            "platforms": ["youtube"],
            "preset_slug": "short-form",
            "asset_bundle_id": bundle["id"],
        },
    )
    assert releases.status_code == 200
    publish_times = [item["publish_at"] for item in releases.json()]
    assert publish_times == ["2030-01-04T12:00:00", "2030-01-05T12:00:00"]


def test_bundle_rejects_incomplete_part_asset_map(client, monkeypatch: pytest.MonkeyPatch):
    client, _engine = client
    monkeypatch.setattr(
        stories_api,
        "_fetch_pixabay_assets",
        lambda keywords: [
            {
                "remote_url": "https://example.com/fog.jpg",
                "provider": "pixabay",
                "provider_id": "asset-1",
                "type": "image",
                "orientation": "portrait",
                "tags": ["fog"],
                "width": 1080,
                "height": 1920,
                "attribution": "tester",
            }
        ],
    )
    story = client.post(
        "/stories",
        json={"title": "Mapping", "body_md": "One. Two. Three."},
    ).json()
    client.post(f"/stories/{story['id']}/script")
    parts = client.put(
        f"/stories/{story['id']}/parts",
        json=[
            {"body_md": "One.", "approved": True},
            {"body_md": "Two. Three.", "approved": True},
        ],
    ).json()
    assets = client.post(f"/stories/{story['id']}/assets/index").json()
    res = client.post(
        f"/stories/{story['id']}/asset-bundles",
        json={
            "name": "Primary",
            "asset_ids": [assets[0]["id"]],
            "part_asset_map": [{"story_part_id": parts[0]["id"], "asset_id": assets[0]["id"]}],
        },
    )
    assert res.status_code == 400
