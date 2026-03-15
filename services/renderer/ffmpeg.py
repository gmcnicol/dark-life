"""FFmpeg-based render helpers with atomic output and error handling."""

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


def probe_duration_ms(path: Path) -> int:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(float(result.stdout.strip()) * 1000)


def render_background(asset: Path, duration_ms: int, out_path: Path, *, preset: dict[str, int | bool]) -> Path:
    """Render a visual bed from an image or video asset."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    width = int(preset["width"])
    height = int(preset["height"])
    fps = int(preset["fps"])
    duration = max(duration_ms / 1000.0, 1.0)
    ext = asset.suffix.lower()
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
    )
    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(asset),
            "-vf",
            vf,
            "-t",
            str(duration),
            "-r",
            str(fps),
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(asset),
            "-vf",
            vf,
            "-t",
            str(duration),
            "-r",
            str(fps),
            "-an",
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ]
    log_debug("ffmpeg_cmd", argv=cmd)
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out_path


def burn_subtitles(video: Path, subtitle: Path, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video),
        "-vf",
        f"subtitles={subtitle}",
        "-c:a",
        "copy",
        str(out_path),
    ]
    log_debug("ffmpeg_cmd", argv=cmd)
    subprocess.run(cmd, capture_output=True, text=True, check=True)
    return out_path


def concat_videos(inputs: list[Path], out_path: Path) -> Path:
    if not inputs:
        raise FileNotFoundError("No inputs to concatenate")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = out_path.with_suffix(".txt")
    manifest.write_text(
        "\n".join(f"file '{path.resolve().as_posix()}'" for path in inputs) + "\n",
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest),
        "-c",
        "copy",
        str(out_path),
    ]
    log_debug("ffmpeg_cmd", argv=cmd)
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    finally:
        manifest.unlink(missing_ok=True)
    return out_path


__all__ = ["burn_subtitles", "concat_videos", "mux", "probe_duration_ms", "render_background"]
