import pytest
from pathlib import Path
import types

import pytest
from pathlib import Path

import video_renderer.create_slideshow as cs
from video_renderer.create_slideshow import (
    build_video_filters,
    IMAGE_DURATION,
    TRANSITION_DURATION,
    preflight,
)


def expected_filters(subtitle_path: Path | None, dark_overlay: bool, zoom: bool):
    base_filters = []
    if zoom:
        zoom_part = f"zoompan=z='min(zoom+0.0005,1.1)':d={IMAGE_DURATION * 25}:s=1280x720"
        base_filters.append(f"[0:v]{zoom_part}[v0]")
        base_filters.append(f"[1:v]{zoom_part}[v1]")
    else:
        base_filters.append("[0:v]scale=1280:720,setsar=1[v0]")
        base_filters.append("[1:v]scale=1280:720,setsar=1[v1]")

    base_filters.append(
        f"[v0][v1]xfade=transition=fade:duration={TRANSITION_DURATION}:offset={IMAGE_DURATION - TRANSITION_DURATION}[vx1]"
    )

    last = "[vx1]"
    if dark_overlay:
        base_filters.append("[vx1]drawbox=t=fill:color=black@0.4[v_dark]")
        last = "[v_dark]"
    if subtitle_path:
        base_filters.append(
            f"{last}subtitles='{subtitle_path.as_posix()}'[v_final]"
        )
        last = "[v_final]"
    return base_filters, last


@pytest.mark.parametrize(
    "dark_overlay, zoom, subtitle",
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, True),
    ],
)
def test_build_video_filters(dark_overlay, zoom, subtitle, tmp_path):
    subtitle_path = tmp_path / "sub.srt" if subtitle else None
    if subtitle_path:
        subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nTest")

    filters, label = build_video_filters(2, subtitle_path, dark_overlay, zoom)
    expected, expected_label = expected_filters(subtitle_path, dark_overlay, zoom)
    assert filters == expected
    assert label == expected_label


def test_preflight_selects_first_track(tmp_path, monkeypatch):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    (frames_dir / "f1.png").write_bytes(b"x")

    music_dir = tmp_path / "music"
    music_dir.mkdir()
    (music_dir / "b.mp3").write_bytes(b"x")
    (music_dir / "a.mp3").write_bytes(b"x")

    dummy = types.SimpleNamespace(MUSIC_DIR=music_dir, CONTENT_DIR=tmp_path)
    monkeypatch.setattr(cs, "settings", dummy)

    frames, track = preflight("job1", frames_dir)
    assert len(frames) == 1
    assert track.name == "a.mp3"


def test_preflight_missing_frames(tmp_path, monkeypatch):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    (music_dir / "a.mp3").write_bytes(b"x")
    dummy = types.SimpleNamespace(MUSIC_DIR=music_dir, CONTENT_DIR=tmp_path)
    monkeypatch.setattr(cs, "settings", dummy)

    with pytest.raises(FileNotFoundError):
        preflight("job1", frames_dir)
