"""Whisper-based subtitle generation and optional burn-in."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

try:  # Optional dependency; tests may patch
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover - faster-whisper not installed
    WhisperModel = None  # type: ignore

from shared.config import settings
from shared.logging import SERVICE_NAME, log_info


def _log_warn(event: str, **fields: object) -> None:
    """Emit a warning-level JSON log line."""
    logging.warning(json.dumps({"service": SERVICE_NAME, "event": event, **fields}))


@dataclass
class Segment:
    start: float
    end: float
    text: str


def _probe_duration_ms(path: Path) -> int:
    """Return media duration in milliseconds using ffprobe or wave fallback."""
    if shutil.which("ffprobe"):
        try:
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
        except Exception as exc:  # pragma: no cover - ffprobe failure
            logging.error(
                json.dumps(
                    {
                        "service": SERVICE_NAME,
                        "event": "ffprobe",
                        "path": str(path),
                        "error": str(exc),
                    }
                )
            )
    # Fallback using the wave module
    try:
        import wave

        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return int(frames / float(rate) * 1000)
    except Exception as exc:  # pragma: no cover - invalid wav
        logging.error(
            json.dumps(
                {
                    "service": SERVICE_NAME,
                    "event": "wav_probe",
                    "path": str(path),
                    "error": str(exc),
                }
            )
        )
        return 0


def _normalize(text: str) -> str:
    """Normalize whitespace and punctuation in ``text``."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,?!.:])", r"\1", text)
    return text


def _merge_short_segments(segments: Iterable[Segment], threshold: float = 0.3) -> List[Segment]:
    """Merge consecutive segments shorter than ``threshold`` seconds."""
    merged: List[Segment] = []
    for seg in segments:
        if merged and (seg.end - seg.start) < threshold:
            merged[-1].end = seg.end
            merged[-1].text += " " + seg.text
        else:
            merged.append(Segment(seg.start, seg.end, seg.text))
    return merged


def _format_ts(seconds: float, kind: str) -> str:
    ms = int(round(seconds * 1000))
    h = ms // 3_600_000
    m = (ms % 3_600_000) // 60_000
    s = (ms % 60_000) // 1000
    millis = ms % 1000
    if kind == "srt":
        return f"{h:02}:{m:02}:{s:02},{millis:03}"
    return f"{h:02}:{m:02}:{s:02}.{millis:03}"


def _write_srt(segments: Iterable[Segment], dest: Path) -> None:
    lines: List[str] = []
    for idx, seg in enumerate(segments, 1):
        start = _format_ts(seg.start, "srt")
        end = _format_ts(seg.end, "srt")
        text = _normalize(seg.text)
        lines.append(f"{idx}\n{start} --> {end}\n{text}")
    dest.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def _write_vtt(segments: Iterable[Segment], dest: Path) -> None:
    lines = ["WEBVTT\n"]
    for seg in segments:
        start = _format_ts(seg.start, "vtt")
        end = _format_ts(seg.end, "vtt")
        text = _normalize(seg.text)
        lines.append(f"{start} --> {end}\n{text}\n")
    dest.write_text("\n".join(lines), encoding="utf-8")


def generate(*, job_id: str | int, part_id: str | int, video_path: Path | None = None) -> Path:
    """Transcribe ``vo.wav`` for ``job_id`` and produce subtitles.

    Returns the path to the subtitles file. If ``settings.SUBTITLES_BURN_IN`` is
    true and ``video_path`` is provided, the subtitles are burned into the video
    and the path to the new video file is returned instead.
    """

    if WhisperModel is None:  # pragma: no cover - dependency missing
        raise RuntimeError("faster-whisper is required to generate subtitles")

    job_dir = Path(settings.TMP_DIR) / str(job_id)
    vo_path = job_dir / "vo.wav"
    fmt = settings.SUBTITLES_FORMAT.lower()
    sub_path = job_dir / f"{part_id}.{fmt}"

    model = WhisperModel(settings.WHISPER_MODEL, device=settings.WHISPER_DEVICE)
    raw_segments, _info = model.transcribe(str(vo_path))
    segments = _merge_short_segments(
        Segment(seg.start, seg.end, seg.text) for seg in raw_segments
    )

    if fmt == "srt":
        _write_srt(segments, sub_path)
    else:
        _write_vtt(segments, sub_path)

    total_dur = segments[-1].end if segments else 0.0
    audio_dur = _probe_duration_ms(vo_path) / 1000.0
    drift = audio_dur - total_dur

    log_info(
        "subs",
        job_id=job_id,
        part_id=part_id,
        segments=len(segments),
        duration_ms=int(total_dur * 1000),
    )
    if abs(drift) > 1.0:
        _log_warn(
            "subs_drift",
            job_id=job_id,
            part_id=part_id,
            drift_ms=int(drift * 1000),
        )

    if settings.SUBTITLES_BURN_IN and video_path:
        burned = video_path.with_name(video_path.stem + "_subtitled" + video_path.suffix)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(video_path),
                    "-vf",
                    f"subtitles={sub_path}",
                    "-c:a",
                    "copy",
                    str(burned),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            return burned
        except Exception as exc:  # pragma: no cover - ffmpeg missing
            _log_warn(
                "subs_burn_fail",
                job_id=job_id,
                part_id=part_id,
                video=str(video_path),
                error=str(exc),
            )
    return sub_path


__all__ = ["generate", "Segment", "_write_srt", "_write_vtt"]
