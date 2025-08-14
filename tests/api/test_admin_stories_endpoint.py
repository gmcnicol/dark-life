import logging
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from apps.api.db import get_session
import apps.api.db as db
import apps.api.main as main
import apps.api.admin_stories as admin_stories


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

    monkeypatch.setattr(db, "init_db", lambda: None)
    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(admin_stories, "ADMIN_TOKEN", "token")

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_upsert_story_logs_request(client: TestClient, caplog: pytest.LogCaptureFixture):
    payload = {
        "external_id": "abc123",
        "source": "reddit",
        "title": "Test",
        "author": "me",
        "created_utc": 0,
        "text": "hello",
    }

    headers = {"Authorization": "Bearer token"}
    with caplog.at_level(logging.INFO):
        res = client.post("/admin/stories", json=payload, headers=headers)
    assert res.status_code == 201
    assert res.json()["external_id"] == "abc123"

    # ensure request was logged
    assert any(
        getattr(r, "path", None) == "/admin/stories/" and getattr(r, "status", None) == 201
        for r in caplog.records
    )

    # duplicate should return 409
    res2 = client.post("/admin/stories", json=payload, headers=headers)
    assert res2.status_code == 409


def test_upsert_story_updates(client: TestClient):
    payload = {
        "external_id": "abc123",
        "source": "reddit",
        "title": "Test",
        "author": "me",
        "created_utc": 0,
        "text": "hello",
    }
    headers = {"Authorization": "Bearer token"}
    res = client.post("/admin/stories", json=payload, headers=headers)
    assert res.status_code == 201

    payload["title"] = "New Title"
    res2 = client.post("/admin/stories", json=payload, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["title"] == "New Title"
