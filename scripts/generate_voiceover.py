"""Generate simple voiceovers from story markdown files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

try:  # Optional dependency
    import pyttsx3  # type: ignore
except Exception:  # pragma: no cover
    pyttsx3 = None  # type: ignore

try:  # Used to create placeholder audio
    from pydub.generators import Sine
except Exception:  # pragma: no cover
    Sine = None  # type: ignore


engine: Any | None = None
if pyttsx3:
    try:
        engine = pyttsx3.init()
    except Exception:
        engine = None

app = typer.Typer(add_completion=False)


def _read_story(path: Path) -> str:
    """Return story text without front matter."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, _, body = text.partition("---\n\n")
        return body.strip()
    return text.strip()


def _synth_with_pyttsx3(engine: Any | None, text: str, dest: Path) -> bool:
    if not pyttsx3 or not engine:
        return False
    try:
        engine.save_to_file(text, str(dest))
        engine.runAndWait()
        return True
    except Exception:
        return False


def _placeholder_audio(text: str, dest: Path) -> None:
    duration_ms = max(1000, len(text.split()) * 50)
    if Sine:
        tone = Sine(440).to_audio_segment(duration=duration_ms)
        tone.export(dest, format="mp3")
    else:  # pragma: no cover - extremely unlikely
        dest.write_bytes(b"")


@app.command()
def main(
    input_dir: Path = typer.Option(Path("content/stories"), help="Directory with story markdown"),
    output_dir: Path = typer.Option(
        Path("content/audio/voiceovers"), help="Where to place generated mp3s"
    ),
) -> None:
    """Generate voiceovers for all stories."""
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        for story_path in sorted(input_dir.glob("*.md")):
            dest = output_dir / f"{story_path.stem}.mp3"
            if dest.exists():
                continue
            text = _read_story(story_path)
            if not _synth_with_pyttsx3(engine, text, dest):
                _placeholder_audio(text, dest)
    finally:
        if engine:
            engine.stop()


if __name__ == "__main__":  # pragma: no cover
    app()

