import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def sample_story(tmp_path: Path) -> tuple[str, Path]:
    """Return short text and directory of five generated PNG frames."""
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    colors = ["red", "green", "blue", "yellow", "purple"]
    for idx, color in enumerate(colors):
        subprocess.run(
            [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s=160x120:d=1",
                "-frames:v",
                "1",
                str(frames_dir / f"f{idx}.png"),
            ],
            check=True,
        )
    text = "hello world"
    return text, frames_dir
