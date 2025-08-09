"""Generate subtitles from narration audio using faster-whisper.

This module replaces the previous placeholder implementation that simply split
story text into evenly timed subtitle segments.  Instead we now transcribe the
actual narration MP3s with the `faster-whisper` library and emit standard SRT
files.  The main entry point scans a directory of voiceover MP3 files and
writes the matching ``.srt`` files to an output directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import typer
from faster_whisper import WhisperModel

app = typer.Typer(add_completion=False)


def _format_srt_time(seconds: float) -> str:
    """Return ``HH:MM:SS,mmm`` formatted timestamp for SRT files."""

    ms = int(round(seconds * 1000))
    hours = ms // 3_600_000
    minutes = (ms % 3_600_000) // 60_000
    secs = (ms % 60_000) // 1000
    millis = ms % 1000
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _write_srt(segments: Iterable, dest: Path) -> None:
    """Write recognised ``segments`` to ``dest`` in SRT format."""

    lines: list[str] = []
    for idx, seg in enumerate(segments, 1):
        start = _format_srt_time(seg.start)
        end = _format_srt_time(seg.end)
        text = seg.text.strip()
        lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
    dest.write_text("\n".join(lines), encoding="utf-8")


@app.command()
def main(
    input_dir: Path = typer.Option(
        Path("content/audio/voiceovers"), help="Directory containing narration MP3s"
    ),
    output_dir: Path = typer.Option(
        Path("content/subtitles"), help="Where to write generated subtitle files"
    ),
    model_size: str = typer.Option("tiny", help="Whisper model size"),
) -> None:
    """Transcribe all narration MP3s in ``input_dir`` to SRT files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(model_size, device="cpu")

    for voice_path in sorted(input_dir.glob("*.mp3")):
        out_path = output_dir / f"{voice_path.stem}.srt"
        if out_path.exists():
            continue

        segments, _info = model.transcribe(str(voice_path))
        _write_srt(segments, out_path)


if __name__ == "__main__":  # pragma: no cover
    app()

