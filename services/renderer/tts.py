"""ElevenLabs Text-to-Speech client with caching and retry logic."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
from pathlib import Path
from typing import Iterable

import requests

from shared.config import settings
from shared.logging import log_error, log_info


def _rate_limit() -> None:
    """Respect the configured requests-per-second rate limit."""
    rps = max(settings.TTS_RATE_LIMIT_RPS, 1)
    interval = 1.0 / rps
    now = time.monotonic()
    last = getattr(_rate_limit, "last_call", 0.0)
    wait = interval - (now - last)
    if wait > 0:
        time.sleep(wait)
    _rate_limit.last_call = time.monotonic()


def _backoff_delays() -> Iterable[float]:
    """Yield exponential backoff delays in seconds."""
    delay = 1.0
    while True:
        yield delay
        delay *= 2


def cache_key(
    story_id: str | int,
    part_id: str | int,
    voice_id: str,
    model_id: str,
    text: str,
) -> str:
    """Return deterministic cache key for a TTS request."""
    raw = f"{story_id}|{part_id}|{voice_id}|{model_id}|{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _probe_duration_ms(path: Path) -> int:
    """Return media duration in milliseconds using ffprobe."""
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
    except Exception as exc:  # pragma: no cover - ffprobe missing
        log_error("ffprobe", path=str(path), error=str(exc))
        return 0


def _ensure_pcm(src: Path, dst: Path) -> None:
    """Convert ``src`` to 44.1 kHz PCM WAV at ``dst``."""
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(src),
                "-ac",
                "1",
                "-ar",
                "44100",
                "-acodec",
                "pcm_s16le",
                str(dst),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except Exception as exc:  # pragma: no cover - ffmpeg missing
        log_error("ffmpeg", src=str(src), error=str(exc))
        shutil.copyfile(src, dst)


def synthesize(
    text: str,
    *,
    story_id: str | int,
    part_id: str | int,
    out_path: Path,
    voice_id: str | None = None,
    model_id: str | None = None,
    session: requests.sessions.Session | None = None,
) -> Path:
    """Generate speech for ``text`` writing ``out_path`` and returning it."""

    voice = voice_id or settings.ELEVENLABS_VOICE_ID
    model = model_id or settings.ELEVENLABS_MODEL_ID
    if not (settings.ELEVENLABS_API_KEY and voice):
        raise ValueError("ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required")

    cache_dir = Path(settings.TTS_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = cache_key(story_id, part_id, voice, model, text)
    cache_path = cache_dir / f"{key}.wav"

    if cache_path.exists():
        log_info("tts_cache_hit", story_id=story_id, part_id=part_id, path=str(cache_path))
    else:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
        headers = {
            "xi-api-key": settings.ELEVENLABS_API_KEY,
            "Accept": "audio/mpeg",
        }
        payload = {
            "model_id": model,
            "text": text,
            "voice_settings": {
                "style": settings.TTS_SPEAKING_STYLE,
                "speed": settings.TTS_SPEAKING_SPEED,
            },
        }
        sess = session or requests
        for attempt, delay in enumerate(_backoff_delays(), start=1):
            _rate_limit()
            try:
                resp = sess.post(url, json=payload, headers=headers, timeout=60)
                resp.raise_for_status()
                tmp = cache_path.with_suffix(".tmp")
                tmp.write_bytes(resp.content)
                _ensure_pcm(tmp, cache_path)
                tmp.unlink(missing_ok=True)
                log_info("tts_cache_store", story_id=story_id, part_id=part_id, path=str(cache_path))
                break
            except Exception as exc:
                log_error("tts_error", attempt=attempt, error=str(exc), api_key="REDACTED")
                time.sleep(delay)
        else:  # pragma: no cover - loop exhaustion
            raise RuntimeError("TTS request failed")

    shutil.copyfile(cache_path, out_path)
    duration_ms = _probe_duration_ms(out_path)
    log_info(
        "tts",
        story_id=story_id,
        part_id=part_id,
        duration_ms=duration_ms,
        path=str(out_path),
    )
    return out_path


__all__ = ["cache_key", "synthesize"]

