from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
import pytest

from apps.api.main import app
from apps.api.db import get_session
from apps.api.stories import _extract_keywords
from apps.api.models import Story


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


def create_story(client: TestClient, title: str, status: str = "draft"):
    res = client.post("/stories", json={"title": title, "status": status})
    assert res.status_code == 201
    return res.json()


def test_filter_by_status_and_query(client: TestClient):
    create_story(client, "First story", "draft")
    create_story(client, "Second story", "approved")
    create_story(client, "Another draft", "draft")

    res = client.get("/stories", params={"status": "approved"})
    assert res.status_code == 200
    assert [s["title"] for s in res.json()] == ["Second story"]

    res = client.get("/stories", params={"q": "Another"})
    assert res.status_code == 200
    assert [s["title"] for s in res.json()] == ["Another draft"]


def test_pagination(client: TestClient):
    for i in range(5):
        create_story(client, f"Story {i}")

    res = client.get("/stories", params={"page": 2, "limit": 2})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    assert data[0]["title"] == "Story 2"
    assert data[1]["title"] == "Story 3"


def test_split_story_parts_order(client: TestClient):
    body = " ".join([
        ("word " * 10 + f"sentence {i}.").strip() for i in range(5)
    ])
    story = create_story(client, "Split me", "approved")
    res = client.patch(
        f"/stories/{story['id']}", json={"body_md": body}
    )
    assert res.status_code == 200

    res = client.post(
        f"/stories/{story['id']}/split", params={"target_seconds": 15}
    )
    assert res.status_code == 200
    parts = res.json()
    assert len(parts) == 2
    assert [p["index"] for p in parts] == [1, 2]
    # ensure ordering of sentences
    first_part_text = parts[0]["body_md"]
    second_part_text = parts[1]["body_md"]
    assert "sentence 0" in first_part_text
    assert "sentence 4" in second_part_text


def test_extract_keywords_matches_domain_list():
    story = Story(
        title="Lonely Cabin",
        body_md="A forest shadow hides in the attic at night.",
    )
    keywords = _extract_keywords(story)
    assert keywords.split() == ["cabin", "forest", "shadow", "attic", "night"]
