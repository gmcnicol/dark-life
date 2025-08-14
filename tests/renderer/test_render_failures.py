import types
from pathlib import Path

import pytest

from shared.config import settings
from video_renderer import create_slideshow as cs


def test_ffmpeg_failure_posts_snippet(monkeypatch, tmp_path):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    (frames_dir / "f1.png").write_bytes(b"x")

    music_dir = tmp_path / "music"
    music_dir.mkdir()
    (music_dir / "track.mp3").write_bytes(b"x")

    monkeypatch.setattr(settings, "MUSIC_DIR", music_dir)
    monkeypatch.setattr(settings, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(settings, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")

    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"] = url
        sent["json"] = json
        return types.SimpleNamespace()

    monkeypatch.setattr(cs.httpx, "post", fake_post)

    class FakeProc:
        returncode = 1
        stderr = b"missing frames or audio"
        stdout = b""

    monkeypatch.setattr(cs.subprocess, "run", lambda *a, **k: FakeProc())

    with pytest.raises(cs.RenderError):
        cs.render("job1", "s1", "p1", frames_dir)

    assert sent["json"]["status"] == "errored"
    assert "missing frames" in sent["json"]["stderr_snippet"]
