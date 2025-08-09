import json
import sqlite3
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from apps.api.models import Asset, Job
from shared.config import settings
from services.renderer import poller


def test_poller_processes_job(tmp_path, monkeypatch):
    visuals = tmp_path / "visuals"
    visuals.mkdir()
    monkeypatch.setattr(settings, "VISUALS_DIR", visuals)
    monkeypatch.setattr(settings, "STORIES_DIR", tmp_path)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        asset = Asset(story_id=1, remote_url="http://example.com/img.jpg")
        session.add(asset)
        session.commit()
        session.refresh(asset)
        job = Job(
            story_id=1,
            kind="render_part",
            status="queued",
            payload={"story_id": 1, "part_index": 1, "asset_ids": [asset.id]},
        )
        session.add(job)
        session.commit()
        job_id = job.id

    class DummyResponse:
        content = b"img"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(poller.requests, "get", lambda url, timeout: DummyResponse())
    monkeypatch.setattr(poller.render_job_runner, "_process_job", lambda job: True)

    with Session(engine) as session:
        processed = poller.process_once(session)

    assert processed
    with Session(engine) as session:
        job = session.get(Job, job_id)
        assert job.status == "success"
