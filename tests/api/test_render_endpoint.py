import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from apps.api.db import get_session
import apps.api.main as main
from apps.api.models import ScriptVersion, Story, StoryPart


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

    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "engine", engine)
    main.app.dependency_overrides[get_session] = get_test_session
    with TestClient(main.app) as client:
        yield client, engine
    main.app.dependency_overrides.clear()


def test_story_overview_returns_script_and_parts(client):
    client, engine = client
    with Session(engine) as session:
        story = Story(title="Story", body_md="I heard a noise.", status="approved")
        session.add(story)
        session.flush()
        script = ScriptVersion(
            story_id=story.id,
            source_text=story.body_md or "",
            hook="Hook",
            narration_text="Narration",
            outro="Outro",
        )
        session.add(script)
        session.flush()
        story.active_script_version_id = script.id
        session.add(story)
        session.add(
            StoryPart(
                story_id=story.id,
                script_version_id=script.id,
                index=1,
                body_md="Narration",
                source_text="Narration",
                script_text="Narration",
                est_seconds=3,
                approved=True,
            )
        )
        session.commit()
        story_id = story.id

    res = client.get(f"/stories/{story_id}/overview")
    assert res.status_code == 200
    payload = res.json()
    assert payload["story"]["id"] == story_id
    assert payload["active_script"]["hook"] == "Hook"
    assert len(payload["parts"]) == 1
