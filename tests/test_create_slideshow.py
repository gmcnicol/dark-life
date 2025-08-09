import pytest
from pathlib import Path

from video_renderer.create_slideshow import (
    build_video_filters,
    IMAGE_DURATION,
    TRANSITION_DURATION,
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
