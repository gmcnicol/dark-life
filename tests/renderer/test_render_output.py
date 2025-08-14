import shutil
import subprocess
from pathlib import Path

import pytest

from shared.config import settings
from video_renderer import create_slideshow as cs


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_render_writes_atomic_output_with_audio(tmp_path, monkeypatch):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    # generate two simple png frames
    subprocess.run([
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=160x120:d=1",
        "-frames:v",
        "1",
        str(frames_dir / "f1.png"),
    ], check=True)
    subprocess.run([
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=160x120:d=1",
        "-frames:v",
        "1",
        str(frames_dir / "f2.png"),
    ], check=True)

    music_dir = tmp_path / "music"
    music_dir.mkdir()
    subprocess.run([
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:duration=1",
        "-q:a",
        "9",
        "-acodec",
        "libmp3lame",
        str(music_dir / "track.mp3"),
    ], check=True)

    out_dir = tmp_path / "out"
    tmp_dir = tmp_path / "tmp"
    out_dir.mkdir()

    monkeypatch.setattr(settings, "MUSIC_DIR", music_dir)
    monkeypatch.setattr(settings, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(settings, "TMP_DIR", tmp_dir)

    meta = cs.render("job1", "story", "p1", frames_dir)
    out_path = Path(meta["path"])
    assert out_path.exists()
    assert out_path.stat().st_size > 0
    # temp file removed
    assert not (tmp_dir / "job1" / "story_p1.mp4").exists()

    # audio stream check
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(out_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    assert "audio" in probe.stdout
