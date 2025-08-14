"""Create a video slideshow with crossfades, audio mix and subtitles using ffmpeg.

The script searches for assets based on a story identifier and assembles a
simple video containing:

* Still images displayed as a slideshow with 5s per image and 1s crossfades.
* Optional dark overlay and gentle zoom.
* Mixed voiceover and background music.
* Burned-in subtitles.

Only built-in Python modules are used and ``ffmpeg`` is invoked through
:func:`subprocess.run`.
"""

from __future__ import annotations

import argparse
import logging
import shlex
import subprocess
from pathlib import Path

import httpx

from shared.config import settings
from shared.logging import log_debug, log_error, log_info

IMAGE_DURATION = 5
TRANSITION_DURATION = 1


class RenderError(RuntimeError):
    """Rendering failed after posting status to the API."""


def _post_status(job_id: str, payload: dict[str, object]) -> None:
    """Best-effort POST of status updates to the API."""

    if not settings.API_BASE_URL:
        return
    headers = {}
    if settings.API_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {settings.API_AUTH_TOKEN}"
    try:
        httpx.post(
            f"{settings.API_BASE_URL}/api/render-jobs/{job_id}/status",
            json=payload,
            headers=headers,
            timeout=10.0,
        )
    except Exception as exc:  # pragma: no cover - best effort
        log_error(
            "error",
            job_id=job_id,
            error_class=exc.__class__.__name__,
            error_message=str(exc),
        )


def build_video_filters(
    image_count: int,
    subtitle: Path | None,
    dark_overlay: bool,
    zoom: bool,
) -> tuple[list[str], str]:
    """Return filter graph parts and final video label.

    ``image_count`` specifies number of image inputs already provided to
    ffmpeg. ``subtitle`` is an optional subtitle file. If ``dark_overlay`` is
    True, a translucent black layer is drawn over the video for a spooky
    aesthetic. ``zoom`` enables a subtle zoom effect on each slide.
    """

    filters: list[str] = []
    # Prepare each image stream
    for idx in range(image_count):
        label = f"v{idx}"
        src = f"[{idx}:v]"
        if zoom:
            # zoompan generates frames from a still image with slight zoom
            zoom_filter = (
                "zoompan=z='min(zoom+0.0005,1.1)':" f"d={IMAGE_DURATION * 25}:s=1280x720"
            )
            filters.append(f"{src}{zoom_filter}[{label}]")
        else:
            filters.append(f"{src}scale=1280:720,setsar=1[{label}]")

    last = "[v0]"
    step = IMAGE_DURATION - TRANSITION_DURATION
    for i in range(1, image_count):
        offset = step * i
        out_label = f"vx{i}"
        filters.append(
            f"{last}[v{i}]xfade=transition=fade:duration={TRANSITION_DURATION}:offset={offset}[{out_label}]"
        )
        last = f"[{out_label}]"

    if dark_overlay:
        filters.append(f"{last}drawbox=t=fill:color=black@0.4[v_dark]")
        last = "[v_dark]"

    if subtitle:
        # Quote the subtitle path to allow for spaces in directories
        filters.append(f"{last}subtitles='{subtitle.as_posix()}'[v_final]")
        last = "[v_final]"

    return filters, last


def _settings_path(name: str, fallback: Path) -> Path:
    return Path(getattr(settings, name, fallback))


def preflight(
    job_id: str,
    frames_dir: Path,
    story_id: str | None = None,
    part_id: str | None = None,
) -> tuple[list[Path], Path]:
    """Validate inputs and choose a music track."""

    if not frames_dir.is_dir():
        raise FileNotFoundError(f"frames directory not found: {frames_dir}")
    frames = sorted(frames_dir.glob("*.png"))
    if not frames:
        raise FileNotFoundError(f"no frame images found in {frames_dir}")

    music_dir = _settings_path("MUSIC_DIR", settings.CONTENT_DIR / "audio" / "music")
    if not music_dir.is_dir():
        raise FileNotFoundError(f"music directory not found: {music_dir}")
    tracks = sorted(music_dir.glob("*.mp3"))
    if not tracks:
        raise FileNotFoundError(f"no .mp3 tracks in {music_dir}")
    chosen = tracks[0]

    log_info(
        "preflight",
        job_id=job_id,
        story_id=story_id,
        part_id=part_id,
        frames_dir=str(frames_dir),
        frame_count=len(frames),
        music_dir=str(music_dir),
        chosen_track=chosen.name,
    )
    return frames, chosen


def build_ffmpeg_cmd(
    frames_dir: Path,
    audio_track: Path,
    out_path: Path,
    fps: int = 30,
    audio_bitrate: str = "192k",
) -> list[str]:
    """Return the ffmpeg command for rendering."""

    pattern = str(frames_dir / "*.png")
    return [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-pattern_type",
        "glob",
        "-i",
        pattern,
        "-i",
        str(audio_track),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        audio_bitrate,
        "-shortest",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        str(out_path),
    ]


def _probe_duration_ms(path: Path) -> int:
    """Return media duration in milliseconds using ffprobe."""

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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return int(float(result.stdout.strip()) * 1000)


def render(
    job_id: str,
    story_id: str,
    part_id: str,
    frames_dir: Path,
    fps: int = 30,
    audio_bitrate: str = "192k",
    debug: bool = False,
) -> dict[str, object]:
    """Render the slideshow and return artifact metadata."""
    try:
        frames, track = preflight(job_id, frames_dir, story_id, part_id)
    except FileNotFoundError as exc:
        _post_status(
            job_id,
            {
                "status": "errored",
                "error_class": "PreflightError",
                "error_message": str(exc),
            },
        )
        log_error(
            "error",
            job_id=job_id,
            story_id=story_id,
            part_id=part_id,
            error_class="PreflightError",
            error_message=str(exc),
        )
        raise RenderError(str(exc)) from exc

    tmp_root = _settings_path("TMP_DIR", settings.TMP_DIR)
    out_dir = _settings_path("OUTPUT_DIR", settings.OUTPUT_DIR)
    job_tmp = tmp_root / job_id
    job_tmp.mkdir(parents=True, exist_ok=True)
    tmp_path = job_tmp / f"{story_id}_{part_id}.mp4"

    cmd = build_ffmpeg_cmd(frames_dir, track, tmp_path, fps=fps, audio_bitrate=audio_bitrate)
    log_debug("ffmpeg_cmd", job_id=job_id, argv=cmd)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        snippet = proc.stderr.decode(errors="ignore")[-400:]
        _post_status(
            job_id,
            {
                "status": "errored",
                "error_class": "FFmpegError",
                "exit_code": proc.returncode,
                "stderr_snippet": snippet,
            },
        )
        log_error(
            "error",
            job_id=job_id,
            story_id=story_id,
            part_id=part_id,
            exit_code=proc.returncode,
            error_class="FFmpegError",
            stderr_snippet=snippet,
        )
        raise RenderError("ffmpeg failed")

    final_path = out_dir / f"{story_id}_{part_id}.mp4"
    tmp_path.replace(final_path)

    duration_ms = _probe_duration_ms(final_path)
    size = final_path.stat().st_size
    metadata = {
        "bytes": size,
        "duration_ms": duration_ms,
        "audio_track": track.name,
        "path": str(final_path),
    }
    log_info("done", job_id=job_id, story_id=story_id, part_id=part_id, **metadata)
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a video slideshow")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--story-id", required=True)
    parser.add_argument("--part-id", required=True)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--audio-bitrate", default="192k")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--json-logs", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    level = getattr(logging, args.log_level.upper(), logging.INFO)
    if args.debug:
        level = logging.DEBUG
    log_format = "%(message)s" if args.json_logs else None
    logging.basicConfig(level=level, format=log_format)

    try:
        render(
            args.job_id,
            args.story_id,
            args.part_id,
            args.frames_dir,
            fps=args.fps,
            audio_bitrate=args.audio_bitrate,
            debug=args.debug,
        )
    except RenderError:
        return 1
    except Exception as exc:  # pragma: no cover - error path
        _post_status(
            args.job_id,
            {
                "status": "errored",
                "error_class": exc.__class__.__name__,
                "error_message": str(exc),
            },
        )
        log_error(
            "error",
            job_id=args.job_id,
            story_id=args.story_id,
            part_id=args.part_id,
            error_class=exc.__class__.__name__,
            error_message=str(exc),
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
