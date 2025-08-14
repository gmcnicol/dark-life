import types
import time
from pathlib import Path

import pytest

from services.renderer import poller
from shared.config import settings


class DummySession:
    def __init__(self):
        self.calls = []

    def post(self, *a, **k):
        self.calls.append((a, k))
        return types.SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {})


def _fake_hb(job_id, cid, stop, lost, session=None):
    stop.wait()


def test_low_disk_refusal(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TMP_DIR", tmp_path)
    monkeypatch.setattr(poller, "_heartbeat_loop", _fake_hb)

    du = types.SimpleNamespace(total=0, used=0, free=1)
    monkeypatch.setattr(poller.shutil, "disk_usage", lambda _: du)

    errors = []
    monkeypatch.setattr(poller, "log_error", lambda *a, **k: errors.append((a, k)))

    sess = DummySession()
    poller.process_job({"id": 1}, session=sess)
    assert not (tmp_path / "1").exists()
    assert not sess.calls
    assert any(e[0][0] == "disk_low" for e in errors)


def test_temp_dir_cleanup_success(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TMP_DIR", tmp_path)
    du = types.SimpleNamespace(total=0, used=0, free=10 * 1024 ** 3)
    monkeypatch.setattr(poller.shutil, "disk_usage", lambda _: du)
    monkeypatch.setattr(poller, "_heartbeat_loop", _fake_hb)

    def fake_render(job):
        jd = Path(settings.TMP_DIR) / str(job["id"])
        (jd / "tmp.txt").write_text("hi")

    monkeypatch.setattr(poller, "render_job", fake_render)

    sess = DummySession()
    poller.process_job({"id": 2}, session=sess)
    assert not (tmp_path / "2").exists()


def test_temp_dir_cleanup_error(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TMP_DIR", tmp_path)
    du = types.SimpleNamespace(total=0, used=0, free=10 * 1024 ** 3)
    monkeypatch.setattr(poller.shutil, "disk_usage", lambda _: du)
    monkeypatch.setattr(poller, "_heartbeat_loop", _fake_hb)
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 0, raising=False)

    def slow_render(job):
        jd = Path(settings.TMP_DIR) / str(job["id"])
        (jd / "tmp.txt").write_text("hi")
        time.sleep(0.1)

    monkeypatch.setattr(poller, "render_job", slow_render)

    sess = DummySession()
    poller.process_job({"id": 3}, session=sess)
    assert not (tmp_path / "3").exists()
    assert any(call[0][0].endswith("/status") and call[1]["json"]["status"] == "errored" for call in sess.calls)
