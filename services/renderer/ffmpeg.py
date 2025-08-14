"""FFmpeg-based muxing with atomic output and error handling."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from shared.config import settings
from shared.logging import log_debug, log_error, log_info


def mux(video: Path, audio: Path, name: str) -> Path:
    """Mux ``video`` and ``audio`` into ``OUTPUT_DIR/<name>.mp4``.

    Writes to ``{OUTPUT_DIR}/.tmp`` first, fsyncs, then atomically renames.
    Raises ``FileNotFoundError`` if inputs are missing and ``RuntimeError`` on
    ffmpeg failures with stderr snippet logged.
    """

    if not video.exists():
        raise FileNotFoundError(video)
    if not audio.exists():
        raise FileNotFoundError(audio)

    out_dir = settings.OUTPUT_DIR
    tmp_dir = out_dir / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{name}.mp4"
    out_path = out_dir / f"{name}.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video),
        "-i",
        str(audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        str(tmp_path),
    ]

    env = os.environ.copy()
    if os.getenv("DEBUG", "false").lower() == "true":
        ffreport = settings.TMP_DIR / f"ffreport-{name}.log"
        ffreport.parent.mkdir(parents=True, exist_ok=True)
        env["FFREPORT"] = f"file={ffreport}:level=32"
        log_info("ffreport", path=str(ffreport))

    log_debug("ffmpeg_cmd", argv=cmd)

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        with open(tmp_path, "rb") as fh:
            os.fsync(fh.fileno())
        os.replace(tmp_path, out_path)
        return out_path
    except subprocess.CalledProcessError as exc:
        snippet = (exc.stderr or "")[:200]
        log_error("ffmpeg_fail", exit_code=exc.returncode, stderr=snippet)
        tmp_path.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg failed") from exc


__all__ = ["mux"]
