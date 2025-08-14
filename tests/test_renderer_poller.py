import time

from shared.config import settings
from services.renderer import poller


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
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 1)
    monkeypatch.setattr(poller, "HEARTBEAT_INTERVAL", 0.01)

    calls = []

    def fake_get(url, params=None, timeout=0, headers=None):
        assert url.endswith("/api/render-jobs")
        return Resp(data=[{"id": 1}])

    def fake_post(url, json=None, timeout=0, headers=None):
        calls.append(url)
        return Resp()

    monkeypatch.setattr(poller.requests, "get", fake_get)
    monkeypatch.setattr(poller.requests, "post", fake_post)
    monkeypatch.setattr(poller, "render_job", lambda job: time.sleep(0.05))

    job = poller.poll_jobs()[0]
    poller.process_job(job)

    assert any(url.endswith("/claim") for url in calls)
    assert any(url.endswith("/heartbeat") for url in calls)
    assert any(url.endswith("/status") for url in calls)


def test_abort_on_lease_loss(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 1)
    monkeypatch.setattr(poller, "HEARTBEAT_INTERVAL", 0.01)

    calls = []

    def fake_get(url, params=None, timeout=0, headers=None):
        return Resp(data=[{"id": 2}])

    def fake_post(url, json=None, timeout=0, headers=None):
        calls.append((url, json))
        if url.endswith("/heartbeat"):
            return Resp(status_code=410)
        return Resp()

    monkeypatch.setattr(poller.requests, "get", fake_get)
    monkeypatch.setattr(poller.requests, "post", fake_post)
    monkeypatch.setattr(poller, "render_job", lambda job: time.sleep(0.05))

    job = poller.poll_jobs()[0]
    poller.process_job(job)

    assert any("lease_lost" in (json or {}).get("error_message", "") for url, json in calls if url.endswith("/status"))
