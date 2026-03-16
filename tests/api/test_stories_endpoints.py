import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from apps.api.db import get_session
import apps.api.main as main
import apps.api.stories as stories_api
from apps.api.pipeline import ensure_default_presets


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

    story = client.post("/stories", json={"title": "Pipeline", "body_md": "I walked home. I saw something in the fog. I kept moving."}).json()
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

    jobs = client.get("/jobs", params={"story_id": story["id"]}).json()
    assert any(job["kind"] == "render_compilation" for job in jobs)


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
