"""Generate subtitles from narration audio using faster-whisper.

This module scans a directory of voiceover MP3 files and writes matching
``.srt`` files to an output directory.  The real ``faster-whisper`` library is
used when available but the import is optional so tests can provide a dummy
``WhisperModel`` without requiring the heavy dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

try:  # Optional dependency; tests monkeypatch ``WhisperModel``
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover - faster-whisper not installed
    WhisperModel = None  # type: ignore


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
        lines.append(f"{idx}\n{start} --> {end}\n{text}")

    dest.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def main(
    input_dir: Path = Path("content/audio/voiceovers"),
    output_dir: Path = Path("content/subtitles"),
    model_size: str = "tiny",
) -> None:
    """Transcribe all narration MP3s in ``input_dir`` to SRT files."""

    if WhisperModel is None:  # pragma: no cover - real model missing
        raise RuntimeError("faster-whisper is required to generate subtitles")

    output_dir.mkdir(parents=True, exist_ok=True)
    model = WhisperModel(model_size, device="cpu")

    for voice_path in sorted(input_dir.glob("*.mp3")):
        out_path = output_dir / f"{voice_path.stem}.srt"
        if out_path.exists():
            continue

        segments, _info = model.transcribe(str(voice_path))
        _write_srt(segments, out_path)


if __name__ == "__main__":  # pragma: no cover
    try:
        import typer

        typer.run(main)
    except Exception as exc:  # pragma: no cover - CLI path
        raise SystemExit(str(exc))

