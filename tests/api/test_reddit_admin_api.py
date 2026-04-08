import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from apps.api.db import get_session
from apps.api.main import app
from apps.api.models import Job
import apps.api.db as db
import apps.api.main as main
import apps.api.reddit_admin as reddit_admin


@pytest.fixture(name="client_and_engine")
def client_and_engine_fixture(monkeypatch: pytest.MonkeyPatch):
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
    monkeypatch.setattr(main, "ensure_default_presets", lambda _session: None)
    monkeypatch.setattr(main, "ensure_default_prompt_versions", lambda _session: None)
    monkeypatch.setattr(reddit_admin, "ADMIN_TOKEN", "token")

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()


def test_incremental_runs_fetch_immediately(client_and_engine, monkeypatch: pytest.MonkeyPatch):
    client, engine = client_and_engine
    calls: list[str] = []

    def fake_fetch_incremental(subreddit: str) -> int:
        calls.append(subreddit)
        return 3 if subreddit == "nosleep" else 1

    monkeypatch.setattr(reddit_admin, "run_incremental_fetch", fake_fetch_incremental)

    response = client.post(
        "/admin/reddit/incremental",
        json={"subreddits": ["nosleep", "Odd_directions"]},
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {"subreddit": "nosleep", "inserted": 3},
            {"subreddit": "Odd_directions", "inserted": 1},
        ],
        "total_inserted": 4,
    }
    assert calls == ["nosleep", "Odd_directions"]

    with Session(engine) as session:
        assert session.exec(select(Job)).all() == []
