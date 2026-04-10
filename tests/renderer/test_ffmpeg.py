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


def test_render_background_uses_centered_crop_and_horizontal_pan(tmp_path, monkeypatch):
    asset = tmp_path / "visual.jpg"
    asset.write_bytes(b"img")
    out_path = tmp_path / "background.mp4"
    captured: dict[str, object] = {}

    def fake_run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    ffmpeg.render_background(
        asset,
        42_000,
        out_path,
        preset={"width": 1080, "height": 1920, "fps": 30},
    )

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    vf = cmd[cmd.index("-vf") + 1]
    assert "crop=1080:1920" in vf
    assert "sin(2*PI*t/42.000)" in vf
    assert "x='if(gt(iw,ow),(iw-ow)/2+((iw-ow)/2)*0.35*sin(2*PI*t/42.000),0)'" in vf
    assert "y='if(gt(ih,oh),(ih-oh)/2,0)'" in vf


def test_reframe_video_to_landscape_adds_blurred_16_9_canvas(tmp_path, monkeypatch):
    asset = tmp_path / "segment.mp4"
    asset.write_bytes(b"video")
    out_path = tmp_path / "segment-landscape.mp4"
    captured: dict[str, object] = {}

    def fake_run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    ffmpeg.reframe_video_to_landscape(
        asset,
        out_path,
        preset={"width": 1920, "height": 1080, "fps": 30},
    )

    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "scale=1920:1080:force_original_aspect_ratio=increase" in fc
    assert "crop=1920:1080" in fc
    assert "boxblur=20:10" in fc
    assert "overlay=(W-w)/2:(H-h)/2" in fc
    assert cmd[cmd.index("-map") + 1] == "[v]"


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
