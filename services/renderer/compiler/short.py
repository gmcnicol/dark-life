"""Short-form FFmpeg command compilation."""

from __future__ import annotations

from pathlib import Path

from shared.config import settings

from .models import ArtifactSpec, CommandSpec, RenderInput, RenderPlan


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _scale_filter(preset: dict) -> str:
    width = int(preset["width"])
    height = int(preset["height"])
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
    )


def compile_short_render(render_input: RenderInput) -> RenderPlan:
    output_root = render_input.output_root
    background_path = render_input.job_dir / "background.mp4"
    mixed_audio_path = render_input.job_dir / "mix.wav"
    muxed_path = render_input.job_dir / "muxed.mp4"
    final_video_path = output_root / "video.mp4"
    final_subtitle_path = output_root / f"subtitles.{render_input.subtitle_format}"
    duration_sec = max(render_input.duration_ms / 1000.0, 1.0)
    vf = _scale_filter(render_input.preset)
    fps = str(int(render_input.preset["fps"]))
    commands: list[CommandSpec] = []

    if render_input.music_path:
        music_gain_db = float(render_input.preset.get("music_gain_db", settings.MUSIC_GAIN_DB))
        ducking_db = abs(float(render_input.preset.get("ducking_db", settings.DUCKING_DB)))
        threshold = 0.000976563
        filter_complex = (
            "[0:a]pan=stereo|c0=c0|c1=c0[vo];"
            f"[1:a]aformat=channel_layouts=stereo,volume={music_gain_db}dB[m];"
            f"[m][vo]sidechaincompress=threshold={threshold}:ratio=20:attack=5:release=50:makeup={ducking_db}[d];"
            "[vo][d]amix=inputs=2:duration=first:dropout_transition=2,volume=-1dB,"
            "aformat=channel_layouts=stereo[out]"
        )
        commands.append(
            CommandSpec(
                label="mix_audio",
                binary="ffmpeg",
                args=[
                    "-y",
                    "-i",
                    str(render_input.voice_path),
                    "-i",
                    str(render_input.music_path),
                    "-filter_complex",
                    filter_complex,
                    "-map",
                    "[out]",
                    "-c:a",
                    "pcm_s16le",
                    str(mixed_audio_path),
                ],
                expected_outputs=[str(mixed_audio_path)],
            )
        )

    if render_input.visual_path.suffix.lower() in IMAGE_EXTENSIONS:
        background_args = [
            "-y",
            "-loop",
            "1",
            "-i",
            str(render_input.visual_path),
            "-vf",
            vf,
            "-t",
            f"{duration_sec:.3f}",
            "-r",
            fps,
            "-pix_fmt",
            "yuv420p",
            str(background_path),
        ]
    else:
        background_args = [
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(render_input.visual_path),
            "-vf",
            vf,
            "-t",
            f"{duration_sec:.3f}",
            "-r",
            fps,
            "-an",
            "-pix_fmt",
            "yuv420p",
            str(background_path),
        ]
    commands.append(
        CommandSpec(
            label="render_background",
            binary="ffmpeg",
            args=background_args,
            expected_outputs=[str(background_path)],
        )
    )

    audio_path = mixed_audio_path if render_input.music_path else render_input.voice_path
    mux_output = muxed_path if render_input.burn_subtitles else final_video_path
    commands.append(
        CommandSpec(
            label="mux_av",
            binary="ffmpeg",
            args=[
                "-y",
                "-i",
                str(background_path),
                "-i",
                str(audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-ac",
                "2",
                "-shortest",
                str(mux_output),
            ],
            expected_outputs=[str(mux_output)],
        )
    )

    if render_input.burn_subtitles:
        commands.append(
            CommandSpec(
                label="burn_subtitles",
                binary="ffmpeg",
                args=[
                    "-y",
                    "-i",
                    str(muxed_path),
                    "-vf",
                    f"subtitles={render_input.subtitle_path}",
                    "-c:a",
                    "copy",
                    str(final_video_path),
                ],
                expected_outputs=[str(final_video_path)],
            )
        )

    return RenderPlan(
        commands=commands,
        artifacts=ArtifactSpec(
            video_path=final_video_path,
            subtitle_path=final_subtitle_path,
            mixed_audio_path=mixed_audio_path if render_input.music_path else None,
            staged_visual_path=background_path,
        ),
        metadata={
            "compiler": "renderer.short.v1",
            "command_labels": [command.label for command in commands],
            "burn_subtitles": render_input.burn_subtitles,
            "selected_asset_id": render_input.asset.get("key") or render_input.asset.get("id"),
        },
    )


__all__ = ["compile_short_render"]
