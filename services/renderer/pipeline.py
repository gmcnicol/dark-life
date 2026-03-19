"""Renderer pipeline orchestration built around compiled FFmpeg plans."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.logging import log_info

from . import ffmpeg, music, subtitles, tts
from .asset_cache import materialize_asset
from .compiler import RenderInput, compile_short_render
from .executor import run_commands


def _part_text(context: dict[str, Any]) -> str:
    part = context["story_part"]
    return part.get("script_text") or part.get("body_md") or ""


def render_short_job(
    context: dict[str, Any],
    *,
    session=None,
) -> dict[str, object]:
    job = context["job"]
    story = context["story"]
    part = context["story_part"]
    preset = context["render_preset"]
    bundle = context["asset_bundle"] or {}
    asset = context["selected_asset"]
    if not part:
        raise FileNotFoundError("Story part not found")
    if not preset:
        raise FileNotFoundError("Render preset not found")
    if not asset:
        raise FileNotFoundError("Selected asset not found")

    job_id = int(job["id"])
    job_dir = Path(settings.TMP_DIR) / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    output_root = Path(settings.OUTPUT_DIR) / "stories" / str(story["id"]) / "jobs" / str(job_id)
    output_root.mkdir(parents=True, exist_ok=True)

    voice_result = tts.synthesize_result(
        _part_text(context),
        story_id=story["id"],
        part_id=part["id"],
        out_path=job_dir / "vo.wav",
        session=session,
    )
    subtitle_result = subtitles.generate_result(job_id=job_id, part_id=part["id"])

    selected_music = None
    if preset.get("music_enabled", True):
        policy = bundle.get("music_policy") or "first"
        if bundle.get("music_track"):
            policy = f"named:{bundle['music_track']}"
        selected_music = music.select_track(policy, required=False)

    materialized = materialize_asset(asset, output_dir=job_dir, session=session)
    render_input = RenderInput(
        job_id=job_id,
        story_id=story["id"],
        part_id=part["id"],
        correlation_id=job.get("correlation_id"),
        voice_path=voice_result.path,
        subtitle_path=subtitle_result.path,
        visual_path=materialized.path,
        music_path=selected_music,
        output_root=output_root,
        job_dir=job_dir,
        duration_ms=voice_result.duration_ms,
        subtitle_format=settings.SUBTITLES_FORMAT.lower(),
        asset=asset,
        preset=preset,
        burn_subtitles=bool(settings.SUBTITLES_BURN_IN or preset.get("burn_subtitles")),
        music_policy=bundle.get("music_policy"),
    )
    plan = compile_short_render(render_input)
    log_info(
        "plan_compiled",
        job_id=job_id,
        story_id=story["id"],
        part_id=part["id"],
        command_count=len(plan.commands),
        command_labels=plan.metadata.get("command_labels"),
    )
    run_commands(plan.commands, timeout_sec=settings.JOB_TIMEOUT_SEC)

    shutil.copyfile(subtitle_result.path, plan.artifacts.subtitle_path)
    duration_ms = ffmpeg.probe_duration_ms(plan.artifacts.video_path)
    metadata = {
        **plan.metadata,
        "preset_slug": preset["slug"],
        "part_index": part["index"],
        "selected_asset_id": asset.get("key") or asset.get("provider_id") or asset.get("remote_url"),
        "selected_asset_provider": asset.get("provider"),
        "selected_music_track": selected_music.name if selected_music else None,
        "tts_cache_hit": voice_result.cache_hit,
        "subtitle_provider": subtitle_result.provider,
        "asset_cache_hit": materialized.cache_hit,
    }
    return {
        "artifact_path": str(plan.artifacts.video_path),
        "subtitle_path": str(plan.artifacts.subtitle_path),
        "bytes": plan.artifacts.video_path.stat().st_size,
        "duration_ms": duration_ms,
        "metadata": metadata,
    }


def render_compilation_job(context: dict[str, Any]) -> dict[str, object]:
    job = context["job"]
    story = context["story"]
    compilation = context["compilation"]
    if not compilation:
        raise FileNotFoundError("Compilation not found")
    part_index_by_id = {
        part["id"]: part["index"]
        for part in context.get("parts", [])
        if part.get("id") is not None
    }
    artifact_rows = [
        artifact
        for artifact in context.get("artifacts", [])
        if artifact.get("variant") == "short"
        and artifact.get("story_part_id") in part_index_by_id
        and artifact.get("video_path")
    ]
    if not artifact_rows:
        raise FileNotFoundError("Weekly compilation requires rendered short artifacts")
    artifact_rows.sort(key=lambda artifact: part_index_by_id[artifact["story_part_id"]])
    if len(artifact_rows) != len(part_index_by_id):
        raise FileNotFoundError("Weekly compilation requires all short parts to be rendered")
    artifacts = [Path(artifact["video_path"]) for artifact in artifact_rows]
    output_root = Path(settings.OUTPUT_DIR) / "stories" / str(story["id"]) / "jobs" / str(job["id"])
    output_root.mkdir(parents=True, exist_ok=True)
    video_path = output_root / "video.mp4"
    ffmpeg.concat_videos(artifacts, video_path)
    return {
        "artifact_path": str(video_path),
        "bytes": video_path.stat().st_size,
        "duration_ms": ffmpeg.probe_duration_ms(video_path),
        "metadata": {
            "compiler": "renderer.compilation.v1",
            "part_count": len(artifacts),
            "selected_asset_id": None,
            "selected_music_track": None,
            "tts_cache_hit": False,
            "subtitle_provider": None,
            "asset_cache_hit": True,
        },
    }


def render_job(context: dict[str, Any], *, session=None) -> dict[str, object]:
    job = context["job"]
    if job["kind"] == "render_compilation":
        return render_compilation_job(context)
    return render_short_job(context, session=session)


__all__ = ["render_compilation_job", "render_job", "render_short_job"]
