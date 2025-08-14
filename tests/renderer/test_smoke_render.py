import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shared.config import settings
from video_renderer import create_slideshow as cs


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe required",
)
def test_renderer_smoke(sample_story, tmp_path, monkeypatch, capfd):
    text, frames_dir = sample_story  # text currently unused but provided by fixture

    music_dir = tmp_path / "music"
    music_dir.mkdir()
    subprocess.run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(music_dir / "track.mp3"),
        ],
        check=True,
    )

    out_dir = tmp_path / "out"
    tmp_dir = tmp_path / "tmp"
    out_dir.mkdir()

    monkeypatch.setattr(settings, "MUSIC_DIR", music_dir)
    monkeypatch.setattr(settings, "OUTPUT_DIR", out_dir)
    monkeypatch.setattr(settings, "TMP_DIR", tmp_dir)

    try:
        meta = cs.render("job1", "story", "p1", frames_dir)
    except cs.RenderError:
        out, err = capfd.readouterr()
        pytest.fail(f"render failed:\n{out}\n{err}")

    out_path = Path(meta["path"])
    assert out_path.exists() and out_path.stat().st_size > 0

    job_tmp = tmp_dir / "job1"
    assert job_tmp.exists()
    assert list(job_tmp.iterdir()) == []

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-print_format",
            "json",
            str(out_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    data = json.loads(probe.stdout)
    video = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    assert len(video) == 1 and video[0].get("codec_name") == "h264"
    assert len(audio) == 1 and audio[0].get("codec_name") == "aac"
    assert float(data["format"]["duration"]) > 0
