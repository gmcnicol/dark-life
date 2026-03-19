import time

import pytest

from services.renderer import poller
from shared.config import settings


class Resp:
    def __init__(self, data=None, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_process_job_happy_path(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 1)
    monkeypatch.setattr(settings, "HEARTBEAT_INTERVAL_SEC", 0.01)

    calls = []

    def fake_get(url, params=None, timeout=0, headers=None):
        if url.endswith("/render-jobs"):
            return Resp(data=[{"id": 1, "kind": "render_part", "variant": "short"}])
        if url.endswith("/context"):
            return Resp(
                data={
                    "job": {"id": 1, "kind": "render_part"},
                    "story": {"id": 10},
                    "story_part": {"id": 20},
                    "selected_asset": {"key": "pixabay:30"},
                }
            )
        raise AssertionError(url)

    def fake_post(url, json=None, timeout=0, headers=None):
        calls.append((url, json))
        return Resp()

    monkeypatch.setattr(poller.requests, "get", fake_get)
    monkeypatch.setattr(poller.requests, "post", fake_post)
    monkeypatch.setattr(
        poller,
        "render_pipeline_job",
        lambda context, session=None: (time.sleep(0.05), {"artifact_path": "/output/video.mp4"})[1],
    )

    job = poller.poll_jobs()[0]
    poller.process_job(job)

    assert any(url.endswith("/claim") for url, _json in calls)
    assert any(url.endswith("/heartbeat") for url, _json in calls)
    assert any((json or {}).get("status") == "rendered" for _url, json in calls)


def test_abort_on_lease_loss(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 1)
    monkeypatch.setattr(settings, "HEARTBEAT_INTERVAL_SEC", 0.01)

    calls = []

    def fake_get(url, params=None, timeout=0, headers=None):
        if url.endswith("/render-jobs"):
            return Resp(data=[{"id": 2, "kind": "render_part", "variant": "short"}])
        if url.endswith("/context"):
            return Resp(
                data={
                    "job": {"id": 2, "kind": "render_part"},
                    "story": {"id": 10},
                    "story_part": {"id": 20},
                    "selected_asset": {"key": "pixabay:30"},
                }
            )
        raise AssertionError(url)

    def fake_post(url, json=None, timeout=0, headers=None):
        calls.append((url, json))
        if url.endswith("/heartbeat"):
            return Resp(status_code=410)
        return Resp()

    monkeypatch.setattr(poller.requests, "get", fake_get)
    monkeypatch.setattr(poller.requests, "post", fake_post)
    monkeypatch.setattr(
        poller,
        "render_pipeline_job",
        lambda context, session=None: (time.sleep(0.05), {})[1],
    )

    job = poller.poll_jobs()[0]
    poller.process_job(job)

    assert any("lease_lost" in (json or {}).get("error_message", "") for _url, json in calls if _url.endswith("/status"))


def test_process_job_records_stderr_snippet(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "HEARTBEAT_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 1)

    calls = []

    def fake_get(url, params=None, timeout=0, headers=None):
        if url.endswith("/render-jobs"):
            return Resp(data=[{"id": 3, "kind": "render_part", "variant": "short"}])
        if url.endswith("/context"):
            return Resp(
                data={
                    "job": {"id": 3, "kind": "render_part"},
                    "story": {"id": 10},
                    "story_part": {"id": 20},
                    "selected_asset": {"key": "pixabay:30"},
                }
            )
        raise AssertionError(url)

    def fake_post(url, json=None, timeout=0, headers=None):
        calls.append((url, json))
        return Resp()

    monkeypatch.setattr(poller.requests, "get", fake_get)
    monkeypatch.setattr(poller.requests, "post", fake_post)

    from services.renderer.executor import CommandExecutionError

    monkeypatch.setattr(
        poller,
        "render_pipeline_job",
        lambda context, session=None: (_ for _ in ()).throw(CommandExecutionError("mux_av", 1, "boom stderr")),
    )

    job = poller.poll_jobs()[0]
    poller.process_job(job)

    assert any((json or {}).get("stderr_snippet") == "boom stderr" for _url, json in calls if _url.endswith("/status"))
