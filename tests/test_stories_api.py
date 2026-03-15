from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine
import pytest

from apps.api.db import get_session
from apps.api.main import app


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


def create_story(client: TestClient, title: str, status: str = "ingested"):
    res = client.post("/stories", json={"title": title, "status": status})
    assert res.status_code == 201
    return res.json()


def test_filter_by_status_and_query(client: TestClient):
    create_story(client, "First story", "ingested")
    create_story(client, "Second story", "approved")
    create_story(client, "Another draft", "ingested")

    res = client.get("/stories", params={"status": "approved"})
    assert res.status_code == 200
    assert [story["title"] for story in res.json()] == ["Second story"]

    res = client.get("/stories", params={"q": "Another"})
    assert res.status_code == 200
    assert [story["title"] for story in res.json()] == ["Another draft"]


def test_pagination(client: TestClient):
    for index in range(5):
        create_story(client, f"Story {index}")

    res = client.get("/stories", params={"page": 2, "limit": 2})
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
