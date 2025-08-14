import shutil
import subprocess
from pathlib import Path

import pytest

from services.renderer import ffmpeg
from shared.config import settings


def test_missing_inputs(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(settings, "OUTPUT_DIR", out_dir)

    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.wav"
    with pytest.raises(FileNotFoundError):
        ffmpeg.mux(video, audio, "clip")

    tmp_dir = out_dir / ".tmp"
    assert not tmp_dir.exists() or list(tmp_dir.iterdir()) == []


def test_error_propagation_logs_and_cleans(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(settings, "OUTPUT_DIR", out_dir)

    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.wav"
    video.write_text("v")
    audio.write_text("a")

    logs: dict[str, object] = {}

    def fake_log_error(event: str, **fields: object) -> None:
        logs.update({"event": event, **fields})

    monkeypatch.setattr(ffmpeg, "log_error", fake_log_error)

    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError):
        ffmpeg.mux(video, audio, "clip")

    assert logs["exit_code"] == 1
    assert "boom" in str(logs["stderr"])
    tmp_dir = out_dir / ".tmp"
    assert tmp_dir.exists()
    assert list(tmp_dir.iterdir()) == []


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_no_orphan_tmp_files(tmp_path, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    monkeypatch.setattr(settings, "OUTPUT_DIR", out_dir)

    video = tmp_path / "v.mp4"
    audio = tmp_path / "a.wav"

    subprocess.run([
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        "color=c=black:s=16x16:d=1",
        str(video),
    ], check=True)
    subprocess.run([
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-acodec",
        "pcm_s16le",
        str(audio),
    ], check=True)

    out = ffmpeg.mux(video, audio, "clip")
    assert out.exists()

    tmp_dir = out_dir / ".tmp"
    assert tmp_dir.exists()
    assert list(tmp_dir.iterdir()) == []
