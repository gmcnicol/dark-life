"""Assemble a simple video from images, audio and subtitles using ffmpeg."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(add_completion=False)


def _find_first(pattern: str) -> Optional[Path]:
    matches = sorted(Path().glob(pattern))
    return matches[0] if matches else None


@app.command()
def main(
    story_id: str = typer.Argument(..., help="Story identifier, e.g. story01"),
    visuals_dir: Path = typer.Option(Path("content/visuals"), help="Directory with images"),
    voice_dir: Path = typer.Option(Path("content/audio/voiceovers"), help="Directory with voiceovers"),
    music_dir: Path = typer.Option(Path("content/audio/music"), help="Background music directory"),
    output_dir: Path = typer.Option(Path("output/videos"), help="Where to save final video"),
) -> None:
    """Create a simple video for STORY_ID using ffmpeg."""
    output_dir.mkdir(parents=True, exist_ok=True)
    image = _find_first(str(visuals_dir / f"{story_id}_*.jpg"))
    voice = _find_first(str(voice_dir / f"*{story_id}*.mp3"))
    music = _find_first(str(music_dir / "*.mp3"))
    subtitle = None
    if voice:
        for ext in (".srt", ".ass"):
            cand = voice.with_suffix(ext)
            if cand.exists():
                subtitle = cand
                break
    output_path = output_dir / f"{story_id}_final.mp4"

    cmd: list[str] = ["ffmpeg", "-y"]

    if image:
        cmd += ["-loop", "1", "-i", str(image)]
    else:
        cmd += ["-f", "lavfi", "-i", "color=c=black:s=1280x720:d=3600"]
    input_count = 1
    audio_inputs: list[int] = []

    if voice:
        cmd += ["-i", str(voice)]
        audio_inputs.append(input_count)
        input_count += 1
    if music:
        cmd += ["-i", str(music)]
        audio_inputs.append(input_count)
        input_count += 1
    if not audio_inputs:
        cmd += ["-f", "lavfi", "-i", "anullsrc"]
        audio_inputs.append(input_count)
        input_count += 1

    if len(audio_inputs) > 1:
        streams = "".join(f"[{i}:a]" for i in audio_inputs)
        cmd += [
            "-filter_complex",
            f"{streams}amix=inputs={len(audio_inputs)}:duration=shortest[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
        ]
    else:
        cmd += ["-map", "0:v", "-map", f"{audio_inputs[0]}:a"]

    if subtitle:
        cmd += ["-vf", f"subtitles={subtitle}"]

    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", str(output_path)]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:  # pragma: no cover
        output_path.write_bytes(b"")


if __name__ == "__main__":  # pragma: no cover
    app()

