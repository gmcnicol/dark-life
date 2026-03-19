from pathlib import Path

from services.renderer.compiler import RenderInput, compile_short_render


def _render_input(tmp_path, *, visual_suffix: str = ".jpg", music: bool = True, burn: bool = False):
    voice = tmp_path / "vo.wav"
    voice.write_bytes(b"voice")
    subtitle = tmp_path / "part.srt"
    subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    visual = tmp_path / f"visual{visual_suffix}"
    visual.write_bytes(b"visual")
    music_path = tmp_path / "music.mp3" if music else None
    if music_path:
        music_path.write_bytes(b"music")
    return RenderInput(
        job_id=7,
        story_id=3,
        part_id=9,
        correlation_id="story-3-part-1",
        voice_path=voice,
        subtitle_path=subtitle,
        visual_path=visual,
        music_path=music_path,
        output_root=tmp_path / "output",
        job_dir=tmp_path / "job",
        duration_ms=42000,
        subtitle_format="srt",
        asset={"id": 42, "type": "image"},
        preset={
            "width": 1080,
            "height": 1920,
            "fps": 30,
            "music_gain_db": -3.0,
            "ducking_db": -12.0,
        },
        burn_subtitles=burn,
        music_policy="first",
    )


def test_compile_short_render_with_music_and_burn(tmp_path):
    plan = compile_short_render(_render_input(tmp_path, music=True, burn=True))
    labels = [command.label for command in plan.commands]
    assert labels == ["mix_audio", "render_background", "mux_av", "burn_subtitles"]
    mix_audio = plan.commands[0]
    mux_av = plan.commands[2]
    assert "sidechaincompress" in " ".join(mix_audio.args)
    assert "pan=stereo|c0=c0|c1=c0" in " ".join(mix_audio.args)
    assert mux_av.args[mux_av.args.index("-ac") + 1] == "2"
    assert plan.artifacts.video_path == tmp_path / "output" / "video.mp4"


def test_compile_short_render_video_without_music(tmp_path):
    plan = compile_short_render(_render_input(tmp_path, visual_suffix=".mp4", music=False, burn=False))
    labels = [command.label for command in plan.commands]
    assert labels == ["render_background", "mux_av"]
    render_background = plan.commands[0]
    mux_av = plan.commands[1]
    assert "-stream_loop" in render_background.args
    assert mux_av.args[mux_av.args.index("-ac") + 1] == "2"
    assert plan.metadata["selected_asset_id"] == 42
