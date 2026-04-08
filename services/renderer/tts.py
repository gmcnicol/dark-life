"""Text-to-speech providers with deterministic caching."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

from shared.config import settings
from shared.logging import log_error, log_info


@dataclass(frozen=True)
class SynthesisResult:
    path: Path
    duration_ms: int
    cache_hit: bool


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
    *,
    provider: str = "elevenlabs",
) -> str:
    """Return deterministic cache key for a TTS request."""
    raw = f"{provider}|{story_id}|{part_id}|{voice_id}|{model_id}|{text}"
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


def _provider_name() -> str:
    return settings.TTS_PROVIDER.strip().lower() or "elevenlabs"


def _xtts_model_identity(xtts_paths: "XttsPaths") -> str:
    parts = [
        str(xtts_paths.model_dir),
        str(xtts_paths.checkpoint_path),
        str(xtts_paths.config_path),
        str(xtts_paths.vocab_path),
        str(xtts_paths.speaker_file_path),
    ]
    identity = "|".join(part for part in parts if part)
    return identity or "xtts_local"


@dataclass(frozen=True)
class XttsPaths:
    model_dir: Path
    run_dir: Path
    checkpoint_path: Path
    config_path: Path
    vocab_path: Path
    speaker_file_path: Path | None
    speaker_wav: Path


def _configured_path(env_name: str, value: Path | None) -> Path | None:
    raw = os.getenv(env_name)
    if raw is not None and not raw.strip():
        return None
    return value


def _checkpoint_rank(path: Path) -> tuple[int, float, str]:
    match = re.search(r"(\d+)$", path.stem)
    step = int(match.group(1)) if match else 0
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (step, mtime, path.name)


def _resolve_xtts_model_dir() -> Path:
    model_dir = _configured_path("XTTS_MODEL_DIR", settings.XTTS_MODEL_DIR)
    run_dir = _configured_path("XTTS_RUN_DIR", settings.XTTS_RUN_DIR)
    checkpoint_path = _configured_path("XTTS_CHECKPOINT_PATH", settings.XTTS_CHECKPOINT_PATH)
    config_path = _configured_path("XTTS_CONFIG_PATH", settings.XTTS_CONFIG_PATH)
    if model_dir:
        return model_dir
    if run_dir:
        return run_dir
    if checkpoint_path:
        return checkpoint_path.parent
    if config_path:
        return config_path.parent
    raise ValueError(
        "XTTS_MODEL_DIR is required when TTS_PROVIDER=xtts_local unless XTTS_RUN_DIR or explicit XTTS paths are set"
    )


def _resolve_xtts_checkpoint(model_dir: Path) -> Path:
    explicit_checkpoint = _configured_path("XTTS_CHECKPOINT_PATH", settings.XTTS_CHECKPOINT_PATH)
    if explicit_checkpoint:
        return explicit_checkpoint
    candidates = [path for path in model_dir.glob(settings.XTTS_CHECKPOINT_GLOB) if path.is_file()]
    if candidates:
        return max(candidates, key=_checkpoint_rank)
    fallback = model_dir / "best_model.pth"
    if fallback.exists():
        return fallback
    raise ValueError(
        f"XTTS checkpoint not found in {model_dir} using glob {settings.XTTS_CHECKPOINT_GLOB!r}"
    )


def resolve_xtts_paths() -> XttsPaths:
    model_dir = _resolve_xtts_model_dir()
    configured_model_dir = _configured_path("XTTS_MODEL_DIR", settings.XTTS_MODEL_DIR)
    configured_run_dir = _configured_path("XTTS_RUN_DIR", settings.XTTS_RUN_DIR)
    configured_config_path = _configured_path("XTTS_CONFIG_PATH", settings.XTTS_CONFIG_PATH)
    configured_vocab_path = _configured_path("XTTS_VOCAB_PATH", settings.XTTS_VOCAB_PATH)
    configured_speaker_file_path = _configured_path("XTTS_SPEAKER_FILE_PATH", settings.XTTS_SPEAKER_FILE_PATH)
    speaker_wav = _configured_path("XTTS_SPEAKER_WAV", settings.XTTS_SPEAKER_WAV)
    run_dir = model_dir if configured_model_dir else (configured_run_dir or model_dir)
    if not speaker_wav:
        raise ValueError("XTTS_SPEAKER_WAV is required when TTS_PROVIDER=xtts_local")

    checkpoint_path = _resolve_xtts_checkpoint(model_dir)
    config_path = configured_config_path or (model_dir / "config.json")
    vocab_path = configured_vocab_path or (model_dir / "vocab.json")
    if not vocab_path.exists():
        fallback_vocab_path = model_dir.parent / "xtts_original_model_files" / "vocab.json"
        if fallback_vocab_path.exists():
            vocab_path = fallback_vocab_path
    speaker_file_path = configured_speaker_file_path
    if speaker_file_path is None:
        default_speaker_file_path = model_dir / "speakers_xtts.pth"
        speaker_file_path = default_speaker_file_path if default_speaker_file_path.exists() else None

    for label, path in (
        ("model dir", model_dir),
        ("run dir", run_dir),
        ("checkpoint", checkpoint_path),
        ("config", config_path),
        ("vocab", vocab_path),
        ("speaker wav", speaker_wav),
    ):
        if not path.exists():
            raise ValueError(f"XTTS {label} not found: {path}")
    if configured_speaker_file_path and speaker_file_path and not speaker_file_path.exists():
        raise ValueError(f"XTTS speaker file not found: {speaker_file_path}")

    return XttsPaths(
        model_dir=model_dir,
        run_dir=run_dir,
        checkpoint_path=checkpoint_path,
        config_path=config_path,
        vocab_path=vocab_path,
        speaker_file_path=speaker_file_path,
        speaker_wav=speaker_wav,
    )


def _synthesize_elevenlabs(
    text: str,
    *,
    story_id: str | int,
    part_id: str | int,
    cache_path: Path,
    voice_id: str | None,
    model_id: str | None,
    session: requests.sessions.Session | None,
) -> None:
    voice = voice_id or settings.ELEVENLABS_VOICE_ID
    model = model_id or settings.ELEVENLABS_MODEL_ID
    if not (settings.ELEVENLABS_API_KEY and voice):
        raise ValueError("ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required")

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
            log_info("tts_cache_store", provider="elevenlabs", story_id=story_id, part_id=part_id, path=str(cache_path))
            return
        except Exception as exc:
            log_error("tts_error", provider="elevenlabs", attempt=attempt, error=str(exc), api_key="REDACTED")
            time.sleep(delay)
    raise RuntimeError("TTS request failed")


def _synthesize_xtts_local(
    text: str,
    *,
    story_id: str | int,
    part_id: str | int,
    cache_path: Path,
    xtts_paths: XttsPaths,
) -> None:
    tmp = cache_path.with_suffix(".xtts.tmp.wav")
    cmd = [
        sys.executable,
        "-m",
        "services.renderer.xtts_runner",
        "--device",
        settings.XTTS_DEVICE,
        "--run-dir",
        str(xtts_paths.run_dir),
        "--checkpoint",
        str(xtts_paths.checkpoint_path),
        "--config",
        str(xtts_paths.config_path),
        "--vocab-path",
        str(xtts_paths.vocab_path),
        "--speaker-wav",
        str(xtts_paths.speaker_wav),
        "--language",
        settings.XTTS_LANGUAGE,
        "--text",
        text,
        "--out",
        str(tmp),
    ]
    if xtts_paths.speaker_file_path:
        cmd.extend(["--speaker-file-path", str(xtts_paths.speaker_file_path)])

    env = os.environ.copy()
    env.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    log_info(
        "xtts_launch",
        story_id=story_id,
        part_id=part_id,
        checkpoint=str(xtts_paths.checkpoint_path),
        config=str(xtts_paths.config_path),
        vocab=str(xtts_paths.vocab_path),
        speaker_file=str(xtts_paths.speaker_file_path) if xtts_paths.speaker_file_path else None,
        speaker_wav=str(xtts_paths.speaker_wav),
        device=settings.XTTS_DEVICE,
    )
    try:
        subprocess.run(
            cmd,
            cwd=str(Path(settings.BASE_DIR)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            timeout=max(settings.JOB_TIMEOUT_SEC, 60),
            env=env,
        )
        _ensure_pcm(tmp, cache_path)
        tmp.unlink(missing_ok=True)
        log_info("tts_cache_store", provider="xtts_local", story_id=story_id, part_id=part_id, path=str(cache_path))
    except subprocess.CalledProcessError as exc:
        log_error("tts_error", provider="xtts_local", error=str(exc), stderr=exc.stderr[-800:] if exc.stderr else "")
        raise RuntimeError("XTTS synthesis failed") from exc
    except Exception as exc:
        log_error("tts_error", provider="xtts_local", error=str(exc))
        raise


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

    return synthesize_result(
        text,
        story_id=story_id,
        part_id=part_id,
        out_path=out_path,
        voice_id=voice_id,
        model_id=model_id,
        session=session,
    ).path


def synthesize_result(
    text: str,
    *,
    story_id: str | int,
    part_id: str | int,
    out_path: Path,
    voice_id: str | None = None,
    model_id: str | None = None,
    session: requests.sessions.Session | None = None,
) -> SynthesisResult:
    """Generate speech for ``text`` writing ``out_path`` and returning metadata."""

    provider = _provider_name()
    if provider == "elevenlabs":
        voice = voice_id or settings.ELEVENLABS_VOICE_ID
        model = model_id or settings.ELEVENLABS_MODEL_ID
    elif provider == "xtts_local":
        xtts_paths = resolve_xtts_paths()
        voice = str(xtts_paths.speaker_wav)
        model = _xtts_model_identity(xtts_paths)
    else:
        raise ValueError(f"Unsupported TTS_PROVIDER: {provider}")

    cache_dir = Path(settings.TTS_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = cache_key(story_id, part_id, voice, model, text, provider=provider)
    cache_path = cache_dir / f"{key}.wav"

    cache_hit = cache_path.exists()
    if cache_hit:
        log_info("tts_cache_hit", provider=provider, story_id=story_id, part_id=part_id, path=str(cache_path))
    else:
        if provider == "elevenlabs":
            _synthesize_elevenlabs(
                text,
                story_id=story_id,
                part_id=part_id,
                cache_path=cache_path,
                voice_id=voice_id,
                model_id=model_id,
                session=session,
            )
        else:
            _synthesize_xtts_local(
                text,
                story_id=story_id,
                part_id=part_id,
                cache_path=cache_path,
                xtts_paths=xtts_paths,
            )

    shutil.copyfile(cache_path, out_path)
    duration_ms = _probe_duration_ms(out_path)
    log_info(
        "tts",
        provider=provider,
        story_id=story_id,
        part_id=part_id,
        duration_ms=duration_ms,
        path=str(out_path),
    )
    return SynthesisResult(path=out_path, duration_ms=duration_ms, cache_hit=cache_hit)


__all__ = ["SynthesisResult", "XttsPaths", "cache_key", "resolve_xtts_paths", "synthesize", "synthesize_result"]
