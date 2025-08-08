"""Generate placeholder subtitles for voiceover files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from pydub import AudioSegment
import typer

app = typer.Typer(add_completion=False)


def _load_story_text(voice_path: Path, stories_dir: Path) -> str:
    story_path = stories_dir / f"{voice_path.stem}.md"
    if not story_path.exists():
        return ""
    text = story_path.read_text(encoding="utf-8")
    if text.startswith("---"):
        _, _, body = text.partition("---\n\n")
        return body.strip()
    return text.strip()


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?]) +", text)
    return [p.strip() for p in parts if p.strip()]


def _format_srt_time(seconds: float) -> str:
    """Format seconds as SRT timestamp."""
    ms = int(round(seconds * 1000))
    hours = ms // 3_600_000
    minutes = (ms % 3_600_000) // 60_000
    secs = (ms % 60_000) // 1000
    millis = ms % 1000
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _format_ass_time(seconds: float) -> str:
    """Format seconds as ASS timestamp."""
    cs = int(round(seconds * 100))
    hours = cs // 360_000
    minutes = (cs % 360_000) // 6_000
    secs = (cs % 6_000) // 100
    centis = cs % 100
    return f"{hours:02}:{minutes:02}:{secs:02}.{centis:02}"


def _timings(duration: float, count: int) -> List[Tuple[float, float]]:
    """Return a list of (start, end) pairs for ``count`` segments."""
    if count == 0:
        return []
    per_sentence = duration / count
    timings: List[Tuple[float, float]] = []
    start = 0.0
    for _ in range(count):
        end = start + per_sentence
        timings.append((start, end))
        start = end
    return timings


def _write_srt(sentences: List[str], out_path: Path, duration: float) -> None:
    lines = []
    for idx, (sent, (start, end)) in enumerate(
        zip(sentences, _timings(duration, len(sentences))), 1
    ):
        lines.append(
            f"{idx}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{sent}\n"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_ass(sentences: List[str], out_path: Path, duration: float) -> None:
    header = (
        "[Script Info]\nScriptType: v4.00+\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, Bold\n"
        "Style: Default,Arial,20,&H00FFFFFF,0\n[Events]\nFormat: Layer, Start, End, Text"
    )
    lines = [header]
    for sent, (start, end) in zip(sentences, _timings(duration, len(sentences))):
        lines.append(
            f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},{sent}"
        )
    out_path.write_text("\n".join(lines), encoding="utf-8")


@app.command()
def main(
    input_dir: Path = typer.Option(Path("content/audio/voiceovers"), help="Directory with mp3 files"),
    stories_dir: Path = typer.Option(Path("content/stories"), help="Directory with source stories"),
    fmt: str = typer.Option("srt", "--format", help="Subtitle format: srt or ass"),
) -> None:
    """Create simple subtitles for each voiceover."""
    fmt = fmt.lower()
    for voice_path in sorted(input_dir.glob("*.mp3")):
        out_path = voice_path.with_suffix(f".{fmt}")
        if out_path.exists():
            continue
        text = _load_story_text(voice_path, stories_dir)
        sentences = _sentences(text)
        audio = AudioSegment.from_file(voice_path)
        duration = len(audio) / 1000.0
        if fmt == "ass":
            _write_ass(sentences, out_path, duration)
        else:
            _write_srt(sentences, out_path, duration)


if __name__ == "__main__":  # pragma: no cover
    app()

