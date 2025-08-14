import asyncio
import json
import logging
from pathlib import Path

import pytest

from shared.config import settings
from video_renderer import render_job_runner as runner


def test_poll_logs_queue_depth_and_paths(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    # Stub HTTP client
    jobs = [{"id": "j1", "story_id": "s1", "part_id": "p1", "lease_seconds": 10}]

    class DummyResp:
        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

        def raise_for_status(self):
            return None

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params):
            return DummyResp(jobs)

        async def post(self, url, json=None):
            # claim and status posts
            return DummyResp({"lease_expires_at": "2020-01-01T00:00:00Z"})

    monkeypatch.setattr(runner.httpx, "AsyncClient", lambda *a, **k: DummyClient())

    # Avoid running actual job processing
    async def fake_run_job(client, job, sem, lease_expires_at=None):
        return None

    monkeypatch.setattr(runner, "_run_job", fake_run_job)

    # Force default paths
    monkeypatch.setattr(settings, "CONTENT_DIR", Path("/content"))
    monkeypatch.setattr(settings, "MUSIC_DIR", Path("/content/audio/music"))
    monkeypatch.setattr(settings, "OUTPUT_DIR", Path("/output"))
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "t")
    monkeypatch.setattr(settings, "POLL_INTERVAL_MS", 10)
    monkeypatch.setattr(settings, "MAX_CLAIM", 1)

    # Stop after first sleep
    async def cancel_sleep(_):
        raise asyncio.CancelledError

    monkeypatch.setattr(runner.asyncio, "sleep", cancel_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(runner._poll_loop())

    # Extract logs
    start_log = json.loads(caplog.records[0].message)
    poll_log = json.loads(caplog.records[1].message)
    claim_log = json.loads(caplog.records[2].message)

    # Default paths
    assert start_log["content_dir"] == "/content"
    assert start_log["music_dir"] == "/content/audio/music"
    assert start_log["output_dir"] == "/output"

    # queue depth
    assert poll_log["event"] == "poll"
    assert poll_log["queue_depth"] == 1
    assert poll_log["service"] == "renderer"

    # claim log required fields
    assert claim_log["event"] == "claim"
    assert claim_log["job_id"] == "j1"
    assert claim_log["story_id"] == "s1"
    assert claim_log["part_id"] == "p1"
    assert claim_log["service"] == "renderer"
