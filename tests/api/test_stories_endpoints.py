import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from apps.api.db import get_session
import apps.api.main as main
import apps.api.stories as stories_api
from apps.api.models import PublishJob, Release, Story
from apps.api.pipeline import ensure_default_presets, upsert_script
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
    monkeypatch.setattr(
        stories_api,
        "_download_bundle_asset",
        lambda story_id, asset: (
            asset.get("local_path") or str(tmp_path / f"{asset.get('provider_id') or 'asset'}.jpg"),
            asset.get("remote_url"),
        ),
    )
    with TestClient(main.app) as client:
        with Session(engine) as session:
            ensure_default_presets(session)
        yield client, engine
    main.app.dependency_overrides.clear()


def generate_script_sync(client: TestClient, engine, story_id: int):
    res = client.post(f"/stories/{story_id}/script")
    assert res.status_code == 202
    payload = res.json()
    assert payload["batch_id"]

    with Session(engine) as session:
        story = session.get(Story, story_id)
        assert story is not None
        script = upsert_script(session, story)
        session.commit()
        session.refresh(script)
        return script


def test_generate_script_and_parts(client):
    client, engine = client
    story = client.post("/stories", json={"title": "My Story", "body_md": "I heard a noise. Then I opened the door. It was empty."}).json()

    script = generate_script_sync(client, engine, story["id"])
    assert script.narration_text

    parts = client.get(f"/stories/{story['id']}/parts")
    assert parts.status_code == 200
    assert len(parts.json()) >= 1


def test_create_story_rejects_same_title_author_and_content(client):
    client, _engine = client

    first = client.post(
        "/stories",
        json={
            "title": "  My Story ",
            "author": "Alice",
            "body_md": "I heard a noise.\n\nThen I opened the door.",
        },
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/stories",
        json={
            "title": "my story",
            "author": "alice",
            "body_md": "I heard a noise. Then I opened the door.",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["detail"] == "duplicate"

    different_author = client.post(
        "/stories",
        json={
            "title": "My Story",
            "author": "Bob",
            "body_md": "I heard a noise. Then I opened the door.",
        },
    )
    assert different_author.status_code == 201


def test_extract_image_keywords_biases_search_to_story_mood():
    story = Story(
        title="The Woman At My Window",
        body_md="Every night the house felt empty and silent, like something was watching me from outside.",
    )

    keywords = stories_api._extract_image_keywords(story).split()

    assert keywords[:3] == ["vacant", "stillness", "silhouette"]
    assert "uncanny" in keywords
    assert "window" not in keywords
    assert "woman" not in keywords
    assert "house" not in keywords
    assert "silhouette" in keywords


def test_story_asset_index_uses_mood_first_pixabay_query(client, monkeypatch: pytest.MonkeyPatch):
    client, _engine = client
    captured: dict[str, str] = {}

    def fake_fetch(keywords: str, *, page: int = 1):
        captured["keywords"] = keywords
        captured["page"] = str(page)
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
    assert captured["page"] == "1"
    assert keywords[:3] == ["vacant", "stillness", "silhouette"]
    assert "uncanny" in keywords
    assert "knife" not in keywords
    assert "kitchen" not in keywords
    assert "silent" not in keywords


def test_fetch_pixabay_assets_uses_broad_search_and_ranks_best_images(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "hits": [
                    {
                        "id": 11,
                        "webformatURL": "https://example.com/weak-portrait.jpg",
                        "imageWidth": 900,
                        "imageHeight": 1600,
                        "likes": 2,
                        "comments": 0,
                        "downloads": 20,
                        "views": 200,
                        "tags": "mist, portrait",
                        "user": "weak",
                    },
                    {
                        "id": 12,
                        "webformatURL": "https://example.com/strong-landscape.jpg",
                        "imageWidth": 2560,
                        "imageHeight": 1440,
                        "likes": 150,
                        "comments": 18,
                        "downloads": 5000,
                        "views": 120000,
                        "tags": "forest, fog",
                        "user": "strong",
                    },
                ]
            }

    def fake_get(url: str, *, params: dict[str, object], timeout: tuple[float, int], headers: dict[str, str]):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(stories_api.settings, "PIXABAY_API_KEY", "pixa-key")
    monkeypatch.setattr(stories_api.requests, "get", fake_get)

    assets = stories_api._fetch_pixabay_assets("fog hallway", page=3)

    params = captured["params"]
    assert isinstance(params, dict)
    assert params["q"] == "fog hallway"
    assert params["page"] == 3
    assert params["per_page"] == stories_api.PIXABAY_RESULT_LIMIT
    assert "orientation" not in params
    assert captured["timeout"] == (3.05, 8)
    assert captured["headers"] == {"User-Agent": "dark-life-api/1.0"}
    assert assets[0]["remote_url"] == "https://example.com/strong-landscape.jpg"
    assert assets[0]["orientation"] == "landscape"
    assert assets[1]["orientation"] == "portrait"


def test_story_asset_index_moves_latest_fetch_results_to_top(client, monkeypatch: pytest.MonkeyPatch):
    client, _engine = client
    fetch_round = {"count": 0}

    def fake_fetch(_keywords: str, *, page: int = 1):
        fetch_round["count"] += 1
        if fetch_round["count"] == 1:
            return [
                {
                    "remote_url": "https://example.com/old-1.jpg",
                    "provider": "pixabay",
                    "provider_id": "asset-1",
                    "type": "image",
                    "orientation": "portrait",
                    "tags": ["vacant"],
                    "width": 1080,
                    "height": 1920,
                    "attribution": "tester",
                },
                {
                    "remote_url": "https://example.com/old-2.jpg",
                    "provider": "pixabay",
                    "provider_id": "asset-2",
                    "type": "image",
                    "orientation": "portrait",
                    "tags": ["hallway"],
                    "width": 1080,
                    "height": 1920,
                    "attribution": "tester",
                },
            ]
        return [
            {
                "remote_url": "https://example.com/new-top.jpg",
                "provider": "pixabay",
                "provider_id": "asset-3",
                "type": "image",
                "orientation": "portrait",
                "tags": ["stillness"],
                "width": 1080,
                "height": 1920,
                "attribution": "tester",
            },
            {
                "remote_url": "https://example.com/old-1.jpg",
                "provider": "pixabay",
                "provider_id": "asset-1",
                "type": "image",
                "orientation": "portrait",
                "tags": ["vacant"],
                "width": 1080,
                "height": 1920,
                "attribution": "tester",
            },
        ]

    monkeypatch.setattr(stories_api, "_fetch_pixabay_assets", fake_fetch)

    story = client.post(
        "/stories",
        json={
            "title": "Latest assets",
            "body_md": "A hallway felt empty and too quiet at night.",
        },
    ).json()

    first = client.post(f"/stories/{story['id']}/assets/index")
    assert first.status_code == 200
    assert [asset["remote_url"] for asset in first.json()] == [
        "https://example.com/old-1.jpg",
        "https://example.com/old-2.jpg",
    ]

    second = client.post(f"/stories/{story['id']}/assets/index")
    assert second.status_code == 200
    assert [asset["remote_url"] for asset in second.json()] == [
        "https://example.com/new-top.jpg",
        "https://example.com/old-1.jpg",
    ]


def test_story_asset_list_returns_latest_fetch_set(client, monkeypatch: pytest.MonkeyPatch):
    client, _engine = client
    fetch_round = {"count": 0}

    def fake_fetch(_keywords: str, *, page: int = 1):
        fetch_round["count"] += 1
        if fetch_round["count"] == 1:
            return [
                {
                    "remote_url": "https://example.com/old-1.jpg",
                    "provider": "pixabay",
                    "provider_id": "asset-1",
                    "type": "image",
                    "orientation": "portrait",
                    "tags": ["vacant"],
                    "width": 1080,
                    "height": 1920,
                    "attribution": "tester",
                }
            ]
        return [
            {
                "remote_url": "https://example.com/new-1.jpg",
                "provider": "pixabay",
                "provider_id": "asset-2",
                "type": "image",
                "orientation": "portrait",
                "tags": ["liminal"],
                "width": 1080,
                "height": 1920,
                "attribution": "tester",
            }
        ]

    monkeypatch.setattr(stories_api, "_fetch_pixabay_assets", fake_fetch)

    story = client.post(
        "/stories",
        json={
            "title": "Current mood",
            "body_md": "The room felt vacant and too quiet to trust.",
        },
    ).json()

    first = client.post(f"/stories/{story['id']}/assets/index")
    assert first.status_code == 200
    assert [asset["remote_url"] for asset in first.json()] == ["https://example.com/old-1.jpg"]

    listed = client.get(f"/stories/{story['id']}/assets")
    assert listed.status_code == 200
    assert [asset["remote_url"] for asset in listed.json()] == ["https://example.com/new-1.jpg"]


def test_create_bundle_and_release_jobs(client, tmp_path, monkeypatch: pytest.MonkeyPatch):
    client, engine = client
    monkeypatch.setattr(
        stories_api,
        "_fetch_pixabay_assets",
        lambda keywords, page=1: [
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
    generate_script_sync(client, engine, story["id"])

    assets = client.post(f"/stories/{story['id']}/assets/index").json()
    assert len(assets) >= 1

    bundle = client.post(
        f"/stories/{story['id']}/asset-bundles",
        json={"name": "Primary", "asset_refs": [assets[0]]},
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


def test_clear_release_marks_it_done_and_updates_publish_job(client, monkeypatch: pytest.MonkeyPatch):
    client, engine = client
    monkeypatch.setattr(
        stories_api,
        "_fetch_pixabay_assets",
        lambda keywords, page=1: [
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
            "title": "Clear queue",
            "body_md": "One. Two. Three.",
        },
    ).json()
    generate_script_sync(client, engine, story["id"])
    assets = client.post(f"/stories/{story['id']}/assets/index").json()
    bundle = client.post(
        f"/stories/{story['id']}/asset-bundles",
        json={"name": "Primary", "asset_refs": [assets[0]]},
    ).json()
    release = client.post(
        f"/stories/{story['id']}/releases",
        json={
            "platforms": ["youtube"],
            "preset_slug": "short-form",
            "asset_bundle_id": bundle["id"],
        },
    ).json()[0]

    with Session(engine) as session:
        publish_job = PublishJob(release_id=release["id"], platform="youtube", status="errored")
        session.add(publish_job)
        session.commit()

    cleared = client.post(f"/releases/{release['id']}/clear")
    assert cleared.status_code == 200
    payload = cleared.json()
    assert payload["status"] == "published"
    assert payload["publish_status"] == "published"
    assert payload["published_at"] is not None

    with Session(engine) as session:
        publish_job = session.exec(select(PublishJob).where(PublishJob.release_id == release["id"])).first()
        assert publish_job is not None
        assert publish_job.status == "published"


def test_create_releases_uses_active_script_parts_only(client, monkeypatch: pytest.MonkeyPatch):
    client, _engine = client
    monkeypatch.setattr(
        stories_api,
        "_fetch_pixabay_assets",
        lambda keywords, page=1: [
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
            "title": "Active script coverage",
            "body_md": "The room was quiet. Then the handle moved. I should have run.",
        },
    ).json()

    first_script = generate_script_sync(client, _engine, story["id"])

    second_script = generate_script_sync(client, _engine, story["id"])
    assert second_script.id != first_script.id

    parts = client.get(f"/stories/{story['id']}/parts")
    assert parts.status_code == 200
    active_part_ids = {part["id"] for part in parts.json()}
    assert active_part_ids

    assets = client.post(f"/stories/{story['id']}/assets/index").json()
    bundle = client.post(
        f"/stories/{story['id']}/asset-bundles",
        json={"name": "Primary", "asset_refs": [assets[0]]},
    )
    assert bundle.status_code == 200
    assert {
        row["story_part_id"] for row in bundle.json()["part_asset_map"]
    } == active_part_ids

    releases = client.post(
        f"/stories/{story['id']}/releases",
        json={
            "platforms": ["youtube"],
            "preset_slug": "short-form",
            "asset_bundle_id": bundle.json()["id"],
        },
    )
    assert releases.status_code == 200


def test_create_weekly_compilation(client):
    client, _engine = client
    story = client.post("/stories", json={"title": "Weekly", "body_md": "I ran. I hid. I survived."}).json()
    generate_script_sync(client, _engine, story["id"])
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
    generate_script_sync(client, _engine, story["id"])
    res = client.post(
        f"/stories/{story['id']}/compilations",
        json={"preset_slug": "weekly-full", "platforms": ["instagram"]},
    )
    assert res.status_code == 400


def test_short_release_rejects_inactive_platform(client, monkeypatch: pytest.MonkeyPatch):
    client, _engine = client
    monkeypatch.setattr(stories_api.settings, "ACTIVE_PUBLISH_PLATFORMS", "youtube")
    story = client.post("/stories", json={"title": "Inactive Platform", "body_md": "One. Two. Three."}).json()
    generate_script_sync(client, _engine, story["id"])
    monkeypatch.setattr(
        stories_api,
        "_fetch_pixabay_assets",
        lambda keywords, page=1: [
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
        json={"name": "Primary", "asset_refs": [assets[0]]},
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
        lambda keywords, page=1: [
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
    generate_script_sync(client, engine, story["id"])
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
        json={"name": "Primary", "asset_refs": [assets[0]]},
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
    assert publish_times == ["2030-01-03T13:00:00", "2030-01-03T18:00:00"]


def test_bundle_rejects_incomplete_part_asset_map(client, monkeypatch: pytest.MonkeyPatch):
    client, _engine = client
    monkeypatch.setattr(
        stories_api,
        "_fetch_pixabay_assets",
        lambda keywords, page=1: [
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
    generate_script_sync(client, _engine, story["id"])
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
            "asset_refs": [assets[0]],
            "part_asset_map": [{"story_part_id": parts[0]["id"], "asset": assets[0]}],
        },
    )
    assert res.status_code == 400
