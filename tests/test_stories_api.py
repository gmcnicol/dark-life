from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool
import pytest

from apps.api.main import app
from apps.api.db import get_session


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
