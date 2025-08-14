import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from apps.api.db import get_session
from apps.api.stories import CHARS_PER_SECOND, MIN_PART_SECONDS, MAX_PART_SECONDS


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


def test_replace_parts_rejects_out_of_bounds(client: TestClient):
    min_chars = int(CHARS_PER_SECOND * MIN_PART_SECONDS) - 10
    max_chars = int(CHARS_PER_SECOND * MAX_PART_SECONDS) + 10
    short_sentence = "a" * min_chars + "."
    long_sentence = "b" * max_chars + "."
    body = short_sentence + " " + long_sentence

    story = client.post(
        "/stories", json={"title": "bad", "body_md": body}
    ).json()

    # too short
    res = client.put(
        f"/stories/{story['id']}/parts",
        json=[{"start_char": 0, "end_char": len(short_sentence)}],
    )
    assert res.status_code == 400

    # too long
    res = client.put(
        f"/stories/{story['id']}/parts",
        json=[{"start_char": len(short_sentence) + 1, "end_char": len(body)}],
    )
    assert res.status_code == 400

