"""Generate placeholder subtitles for voiceover files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

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


def _write_srt(sentences: List[str], out_path: Path) -> None:
    lines = []
    start = 0
    for idx, sent in enumerate(sentences, 1):
        end = start + 3
        lines.append(f"{idx}\n00:00:{start:02},000 --> 00:00:{end:02},000\n{sent}\n")
        start = end
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_ass(sentences: List[str], out_path: Path) -> None:
    header = (
        "[Script Info]\nScriptType: v4.00+\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, Bold\n"
        "Style: Default,Arial,20,&H00FFFFFF,0\n[Events]\nFormat: Layer, Start, End, Text"
    )
    lines = [header]
    start = 0
    for sent in sentences:
        end = start + 3
        lines.append(f"Dialogue: 0,0:00:{start:02}.00,0:00:{end:02}.00,{sent}")
        start = end
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
        if fmt == "ass":
            _write_ass(sentences, out_path)
        else:
            _write_srt(sentences, out_path)


if __name__ == "__main__":  # pragma: no cover
    app()

