import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from apps.api.main import app
from apps.api.db import get_session
from apps.api.models import Asset, Job, Story, StoryPart


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
        yield client, engine
    app.dependency_overrides.clear()


def test_next_series_marks_running(client):
    client, engine = client
    with Session(engine) as session:
        story = Story(title="Story")
        session.add(story)
        session.commit()
        session.refresh(story)
        story_id = story.id
        session.add(StoryPart(story_id=story.id, index=1, body_md="Hello", est_seconds=5))
        asset = Asset(story_id=story.id, remote_url="http://img")
        session.add(asset)
        session.commit()
        session.refresh(asset)
        session.add(
            Job(
                story_id=story.id,
                kind="render_part",
                status="queued",
                payload={
                    "story_id": story.id,
                    "part_index": 1,
                    "asset_ids": [asset.id],
                },
            )
        )
        session.commit()

    res = client.get("/render/next-series")
    assert res.status_code == 200
    data = res.json()
    assert data["story"]["id"] == story_id
    assert data["parts"][0]["index"] == 1

    with Session(engine) as session:
        job = session.exec(select(Job)).first()
        assert job.status == "running"
