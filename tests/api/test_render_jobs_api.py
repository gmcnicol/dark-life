import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from apps.api.main import app
from apps.api.db import get_session
from apps.api.models import Job


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


def _create_job(session: Session) -> int:
    job = Job(kind="render_part", status="queued")
    session.add(job)
    session.commit()
    session.refresh(job)
    return job.id


def test_claim_concurrency(client):
    client, engine = client
    with Session(engine) as session:
        job_id = _create_job(session)

    res1 = client.post(f"/render-jobs/{job_id}/claim")
    assert res1.status_code == 200
    res2 = client.post(f"/render-jobs/{job_id}/claim")
    assert res2.status_code == 409


def test_heartbeat_extends_lease(client):
    client, engine = client
    with Session(engine) as session:
        job_id = _create_job(session)

    res = client.post(f"/render-jobs/{job_id}/claim")
    lease1 = dt.datetime.fromisoformat(res.json()["lease_expires_at"])
    res = client.post(f"/render-jobs/{job_id}/heartbeat")
    lease2 = dt.datetime.fromisoformat(res.json()["lease_expires_at"])
    assert lease2 > lease1


def test_state_machine_transitions(client):
    client, engine = client
    with Session(engine) as session:
        job_id = _create_job(session)

    # Heartbeat before claim should fail
    res = client.post(f"/render-jobs/{job_id}/heartbeat")
    assert res.status_code == 409

    # Claim
    res = client.post(f"/render-jobs/{job_id}/claim")
    assert res.status_code == 200

    # Directly finishing without rendering should fail
    res = client.post(f"/render-jobs/{job_id}/status", json={"status": "rendered"})
    assert res.status_code == 409

    # Move to rendering then rendered
    res = client.post(f"/render-jobs/{job_id}/status", json={"status": "rendering"})
    assert res.status_code == 200
    res = client.post(f"/render-jobs/{job_id}/status", json={"status": "rendered"})
    assert res.status_code == 200

    # Claiming again should fail
    res = client.post(f"/render-jobs/{job_id}/claim")
    assert res.status_code == 409
