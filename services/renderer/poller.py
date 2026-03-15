"""Renderer job poller interacting with the Dark Life API."""

from __future__ import annotations

import shutil
import threading
import time
import uuid
import random
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from shared.config import settings
from shared.logging import log_error, log_info
from shared.workflow import JobStatus

from . import ffmpeg, music, subtitles, tts


HEARTBEAT_INTERVAL = 10  # seconds
DISK_MIN_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
HEARTBEAT_FILE = Path(settings.TMP_DIR) / "worker_heartbeat"


def backoff_schedule(
    base_ms: int, factor: float = 1.0, rand: Callable[[], float] = random.random
) -> Iterable[float]:
    """Yield successive delays in seconds using jitter and optional backoff."""
    delay_ms = base_ms
    while True:
        jitter_ms = rand() * delay_ms
        yield (delay_ms + jitter_ms) / 1000.0
        delay_ms = max(base_ms, int(delay_ms * factor))


def _headers() -> dict[str, str]:
    if settings.API_AUTH_TOKEN:
        return {"Authorization": f"Bearer {settings.API_AUTH_TOKEN}"}
    return {}


def _check_disk(job_id: int | str, cid: str) -> bool:
    tmp = Path(settings.TMP_DIR)
    tmp.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(tmp)
    if usage.free < DISK_MIN_BYTES:
        log_error("disk_low", cid=cid, job_id=job_id, free_bytes=usage.free)
        return False
    return True


def _validate_runtime() -> None:
    missing = [binary for binary in ("ffmpeg", "ffprobe") if shutil.which(binary) is None]
    if missing:
        raise RuntimeError(f"Missing required binaries: {', '.join(missing)}")
    if not settings.API_BASE_URL:
        raise RuntimeError("API_BASE_URL is required")
    if not settings.ELEVENLABS_VOICE_ID:
        log_info("config_warning", field="ELEVENLABS_VOICE_ID", message="TTS voice is unset")
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.TMP_DIR).mkdir(parents=True, exist_ok=True)


def poll_jobs(session: requests.sessions.Session | None = None) -> list[dict]:
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    resp = sess.get(
        f"{base}/render-jobs",
        params={"status": JobStatus.QUEUED.value, "limit": settings.MAX_CLAIM},
        timeout=30,
        headers=_headers(),
    )
    resp.raise_for_status()
    jobs = resp.json() or []
    log_info("poll", cid="poll", count=len(jobs))
    return jobs


def _get_json(path: str, *, session: requests.sessions.Session | None = None) -> dict | list:
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    resp = sess.get(f"{base}{path}", timeout=30, headers=_headers())
    resp.raise_for_status()
    return resp.json()


def _fetch_story_context(job: dict, session: requests.sessions.Session | None = None) -> tuple[dict, dict]:
    story_id = job.get("story_id")
    if not story_id:
        raise ValueError("Job missing story_id")
    overview = _get_json(f"/stories/{story_id}/overview", session=session)
    presets = _get_json("/render-presets", session=session)
    context = {
        "overview": overview,
        "presets": {preset["id"]: preset for preset in presets},
    }
    return overview, context["presets"]


def _asset_path(overview: dict, bundle_id: int | None) -> Path:
    bundles = {bundle["id"]: bundle for bundle in overview.get("asset_bundles", [])}
    bundle = bundles.get(bundle_id or 0)
    if not bundle or not bundle.get("asset_ids"):
        raise FileNotFoundError("Asset bundle has no assets")
    library = {
        asset["id"]: asset
        for asset in _get_json("/assets/library")  # type: ignore[arg-type]
    }
    asset = library.get(bundle["asset_ids"][0])
    if not asset:
        raise FileNotFoundError("Selected asset not found in library")
    if not asset.get("local_path"):
        raise FileNotFoundError("Selected asset missing local path")
    return Path(asset["local_path"])


def _render_short_job(job: dict, session: requests.sessions.Session | None = None) -> dict[str, object]:
    overview, presets = _fetch_story_context(job, session=session)
    parts = {part["id"]: part for part in overview.get("parts", [])}
    part = parts.get(job.get("story_part_id"))
    if not part:
        raise FileNotFoundError("Story part not found")
    preset = presets.get(job.get("payload", {}).get("render_preset_id") or job.get("render_preset_id"))
    if not preset:
        raise FileNotFoundError("Render preset not found")
    job_id = str(job["id"])
    job_dir = Path(settings.TMP_DIR) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    voice_path = job_dir / "vo.wav"
    tts.synthesize(
        part["script_text"] or part["body_md"],
        story_id=job["story_id"],
        part_id=part["id"],
        out_path=voice_path,
        session=session,
    )

    subtitle_path = subtitles.generate(job_id=job_id, part_id=part["id"])
    track = music.select_track(
        overview.get("story", {}).get("music_track") or None,
        required=False,
    )
    mix_path = job_dir / "mix.wav"
    music.mix(voice_path, track, mix_path)

    bg_asset = _asset_path(overview, job.get("asset_bundle_id") or job.get("payload", {}).get("asset_bundle_id"))
    bg_video = job_dir / "bg.mp4"
    ffmpeg.render_background(
        bg_asset,
        ffmpeg.probe_duration_ms(mix_path),
        bg_video,
        preset=preset,
    )
    output_name = (
        f"story-{job['story_id']}-part-{part['index']}-"
        f"script-{job.get('script_version_id')}-bundle-{job.get('asset_bundle_id')}-preset-{preset['slug']}"
    )
    video_path = ffmpeg.mux(bg_video, mix_path, output_name)
    if preset.get("burn_subtitles"):
        subtitled = video_path.with_name(video_path.stem + "-subtitled.mp4")
        ffmpeg.burn_subtitles(video_path, subtitle_path, subtitled)
        video_path = subtitled
    final_subtitle = video_path.with_suffix(f".{settings.SUBTITLES_FORMAT.lower()}")
    shutil.copyfile(subtitle_path, final_subtitle)
    return {
        "artifact_path": str(video_path),
        "subtitle_path": str(final_subtitle),
        "bytes": video_path.stat().st_size,
        "duration_ms": ffmpeg.probe_duration_ms(video_path),
        "metadata": {
            "variant": job["variant"],
            "preset_slug": preset["slug"],
            "music_track": track.name if track else None,
            "part_index": part["index"],
        },
    }


def _render_weekly_job(job: dict, session: requests.sessions.Session | None = None) -> dict[str, object]:
    overview, presets = _fetch_story_context(job, session=session)
    preset = presets.get(job.get("payload", {}).get("render_preset_id") or job.get("render_preset_id"))
    if not preset:
        raise FileNotFoundError("Render preset not found")
    artifacts = [
        Path(artifact["video_path"])
        for artifact in overview.get("artifacts", [])
        if artifact.get("variant") == "short" and artifact.get("video_path")
    ]
    if not artifacts:
        raise FileNotFoundError("Weekly compilation requires rendered short artifacts")
    output_name = f"story-{job['story_id']}-weekly-{job.get('compilation_id')}"
    out_path = Path(settings.OUTPUT_DIR) / f"{output_name}.mp4"
    ffmpeg.concat_videos(artifacts, out_path)
    return {
        "artifact_path": str(out_path),
        "bytes": out_path.stat().st_size,
        "duration_ms": ffmpeg.probe_duration_ms(out_path),
        "metadata": {
            "variant": job["variant"],
            "preset_slug": preset["slug"],
            "part_count": len(artifacts),
        },
    }


def render_job(job: dict, session: requests.sessions.Session | None = None) -> dict[str, object]:
    if job["kind"] == "render_compilation":
        return _render_weekly_job(job, session=session)
    return _render_short_job(job, session=session)


def _heartbeat_loop(
    job_id: int,
    cid: str,
    stop: threading.Event,
    lost: list[bool],
    session: requests.sessions.Session | None = None,
) -> None:
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    while not stop.wait(HEARTBEAT_INTERVAL):
        try:
            resp = sess.post(
                f"{base}/render-jobs/{job_id}/heartbeat",
                timeout=30,
                headers=_headers(),
            )
            if resp.status_code in (409, 410):
                lost[0] = True
                stop.set()
                log_error("heartbeat", cid=cid, job_id=job_id, status=resp.status_code)
                return
            resp.raise_for_status()
            log_info("heartbeat", cid=cid, job_id=job_id)
        except Exception as exc:
            log_error("heartbeat", cid=cid, job_id=job_id, error=str(exc))


def process_job(job: dict, session: requests.sessions.Session | None = None) -> None:
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    job_id = job.get("id")
    cid = str(uuid.uuid4())
    if not _check_disk(job_id, cid):
        return
    job_dir = Path(settings.TMP_DIR) / str(job_id)
    try:
        resp = sess.post(
            f"{base}/render-jobs/{job_id}/claim",
            json={"lease_seconds": settings.LEASE_SECONDS},
            timeout=30,
            headers=_headers(),
        )
        if resp.status_code in (409, 410):
            log_error("claim", cid=cid, job_id=job_id, status=resp.status_code)
            return
        resp.raise_for_status()
        log_info("claim", cid=cid, job_id=job_id)
        sess.post(
            f"{base}/render-jobs/{job_id}/status",
            json={"status": JobStatus.RENDERING.value},
            timeout=30,
            headers=_headers(),
        )

        job_dir.mkdir(parents=True, exist_ok=True)
        stop = threading.Event()
        lost = [False]
        hb_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(job_id, cid, stop, lost, session),
            daemon=True,
        )
        hb_thread.start()

        result_holder: dict[str, object] = {}
        error_holder: list[Exception] = []

        def _run_render() -> None:
            try:
                result_holder.update(render_job(job, session=session))
            except Exception as exc:  # pragma: no cover - surfaced below
                error_holder.append(exc)

        worker = threading.Thread(target=_run_render)
        worker.start()
        worker.join(timeout=settings.JOB_TIMEOUT_SEC)
        stop.set()
        hb_thread.join()

        if worker.is_alive():
            log_error("error", cid=cid, job_id=job_id, error="timeout")
            sess.post(
                f"{base}/render-jobs/{job_id}/status",
                json={"status": JobStatus.ERRORED.value, "error_message": "timeout"},
                timeout=30,
                headers=_headers(),
            )
            return
        if lost[0]:
            log_error("error", cid=cid, job_id=job_id, error="lease_lost")
            sess.post(
                f"{base}/render-jobs/{job_id}/status",
                json={"status": JobStatus.ERRORED.value, "error_message": "lease_lost"},
                timeout=30,
                headers=_headers(),
            )
            return
        if error_holder:
            exc = error_holder[0]
            log_error("error", cid=cid, job_id=job_id, error=str(exc))
            sess.post(
                f"{base}/render-jobs/{job_id}/status",
                json={
                    "status": JobStatus.ERRORED.value,
                    "error_class": exc.__class__.__name__,
                    "error_message": str(exc),
                },
                timeout=30,
                headers=_headers(),
            )
            return

        sess.post(
            f"{base}/render-jobs/{job_id}/status",
            json={"status": JobStatus.RENDERED.value, **result_holder},
            timeout=30,
            headers=_headers(),
        )
        log_info("done", cid=cid, job_id=job_id)
    except Exception as exc:
        log_error("error", cid=cid, job_id=job_id, error=str(exc))
        try:
            sess.post(
                f"{base}/render-jobs/{job_id}/status",
                json={"status": JobStatus.ERRORED.value, "error_message": str(exc)},
                timeout=30,
                headers=_headers(),
            )
        finally:
            pass
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


def run() -> None:  # pragma: no cover - continuous loop
    _validate_runtime()
    log_info("start", cid="poller")
    HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_FILE.touch()
    backoff = backoff_schedule(settings.POLL_INTERVAL_MS, factor=1.0)
    with ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT) as pool:
        running: dict[int, object] = {}
        while True:
            HEARTBEAT_FILE.touch()
            jobs = poll_jobs()
            for job in jobs:
                job_id = job.get("id")
                if job_id in running or len(running) >= settings.MAX_CONCURRENT:
                    continue
                future = pool.submit(process_job, job)
                running[job_id] = future
                future.add_done_callback(lambda _f, jid=job_id: running.pop(jid, None))
            time.sleep(next(backoff))


__all__ = ["backoff_schedule", "poll_jobs", "process_job", "render_job", "run"]
