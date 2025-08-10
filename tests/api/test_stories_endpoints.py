import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from apps.api.db import get_session
import apps.api.stories as stories


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_create_and_update_story(client: TestClient):
    res = client.post("/stories", json={"title": "My Story"})
    assert res.status_code == 201
    story = res.json()

    res = client.patch(
        f"/stories/{story['id']}",
        json={"body_md": "Hello world", "status": "approved"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["body_md"] == "Hello world"
    assert data["status"] == "approved"


def test_fetch_images_creates_assets(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    story = client.post(
        "/stories",
        json={"title": "Forest Story", "body_md": "a forest at night"},
    ).json()

    monkeypatch.setattr(
        stories,
        "_fetch_pexels",
        lambda keywords: [
            {"remote_url": "http://img/1.jpg", "provider": "pexels", "provider_id": "1"}
        ],
    )
    monkeypatch.setattr(
        stories,
        "_fetch_pixabay",
        lambda keywords: [
            {"remote_url": "http://img/2.jpg", "provider": "pixabay", "provider_id": "2"}
        ],
    )

    res = client.post(f"/stories/{story['id']}/fetch-images")
    assert res.status_code == 200
    assets = res.json()
    assert len(assets) == 2
    urls = {a["remote_url"] for a in assets}
    assert urls == {"http://img/1.jpg", "http://img/2.jpg"}
    assert all(a["selected"] is False and a["rank"] is None for a in assets)
    assert all(a["selected"] is False and a["rank"] is None for a in assets)

def test_get_images_unranked_last(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    story = client.post("/stories", json={"title": "Ranked"}).json()

    monkeypatch.setattr(
        stories,
        "_fetch_pexels",
        lambda keywords: [
            {"remote_url": "http://img/1.jpg", "provider": "pexels", "provider_id": "1"},
            {"remote_url": "http://img/2.jpg", "provider": "pexels", "provider_id": "2"},
            {"remote_url": "http://img/3.jpg", "provider": "pexels", "provider_id": "3"},
        ],
    )
    monkeypatch.setattr(stories, "_fetch_pixabay", lambda keywords: [])

    assets = client.post(f"/stories/{story['id']}/fetch-images").json()

    client.patch(f"/stories/{story['id']}/images/{assets[0]['id']}", json={"rank": 0})
    client.patch(f"/stories/{story['id']}/images/{assets[1]['id']}", json={"rank": 1})

    res = client.get(f"/stories/{story['id']}/images")
    assert res.status_code == 200
    ids = [a["id"] for a in res.json()]
    assert ids == [assets[0]["id"], assets[1]["id"], assets[2]["id"]]



def test_split_endpoint_creates_parts(client: TestClient):
    body = " ".join([f"Sentence {i}." for i in range(20)])
    story = client.post(
        "/stories", json={"title": "Split", "body_md": body}
    ).json()

    res = client.post(f"/stories/{story['id']}/split", params={"target_seconds": 5})
    assert res.status_code == 200
    parts = res.json()
    assert len(parts) >= 2
    assert [p["index"] for p in parts] == list(range(1, len(parts) + 1))


def test_enqueue_series_creates_jobs(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    body = "Sentence one. Sentence two. Sentence three."
    story = client.post(
        "/stories", json={"title": "Full", "body_md": body}
    ).json()

    monkeypatch.setattr(
        stories,
        "_fetch_pexels",
        lambda keywords: [
            {"remote_url": "http://img/1.jpg", "provider": "pexels", "provider_id": "1"}
        ],
    )
    monkeypatch.setattr(stories, "_fetch_pixabay", lambda keywords: [])

    res = client.post(f"/stories/{story['id']}/fetch-images")
    assert res.status_code == 200
    asset_id = res.json()[0]["id"]

    res = client.patch(
        f"/stories/{story['id']}/images/{asset_id}", json={"selected": True}
    )
    assert res.status_code == 200

    parts = client.post(
        f"/stories/{story['id']}/split", params={"target_seconds": 10}
    ).json()

    res = client.post(f"/stories/{story['id']}/enqueue-series")
    assert res.status_code == 202
    data = res.json()
    assert len(data["jobs"]) == len(parts)

    jobs_res = client.get("/jobs", params={"story_id": story["id"]})
    assert jobs_res.status_code == 200
    jobs = jobs_res.json()
    assert len(jobs) == len(parts)
    assert all(job["status"] == "queued" for job in jobs)


def test_list_images_returns_in_rank_order(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Test that GET /stories/{id}/images returns images in rank order."""
    story = client.post(
        "/stories", json={"title": "Test Story", "body_md": "forest cabin night"}
    ).json()

    # Mock image fetch to return multiple images
    monkeypatch.setattr(
        stories,
        "_fetch_pexels",
        lambda keywords: [
            {"remote_url": "http://img/1.jpg", "provider": "pexels", "provider_id": "1"},
            {"remote_url": "http://img/2.jpg", "provider": "pexels", "provider_id": "2"},
            {"remote_url": "http://img/3.jpg", "provider": "pexels", "provider_id": "3"},
        ],
    )
    monkeypatch.setattr(stories, "_fetch_pixabay", lambda keywords: [])

    # Fetch images
    res = client.post(f"/stories/{story['id']}/fetch-images")
    assert res.status_code == 200
    assets = res.json()
    assert len(assets) == 3

    # Set ranks in non-sequential order to test sorting
    client.patch(f"/stories/{story['id']}/images/{assets[0]['id']}", json={"rank": 3})
    client.patch(f"/stories/{story['id']}/images/{assets[1]['id']}", json={"rank": 1})
    client.patch(f"/stories/{story['id']}/images/{assets[2]['id']}", json={"rank": 2})

    # Get images and verify they are returned in rank order
    images_res = client.get(f"/stories/{story['id']}/images")
    assert images_res.status_code == 200
    images = images_res.json()
    assert len(images) == 3

    # Verify order by rank (and then by id for consistent ordering)
    ranks = [img["rank"] for img in images if img["rank"] is not None]
    assert ranks == [1, 2, 3]
