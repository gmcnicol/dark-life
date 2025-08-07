"""Build a static dashboard showing pipeline progress."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import typer

app = typer.Typer(add_completion=False)


def _status_for_story(story: Path, visuals_dir: Path, voice_dir: Path, videos_dir: Path) -> Dict[str, str]:
    story_id = story.stem
    has_visuals = any(visuals_dir.glob(f"{story_id}_*.jpg"))
    voice = voice_dir / f"{story_id}.mp3"
    has_voice = voice.exists()
    has_sub = voice.with_suffix(".srt").exists() or voice.with_suffix(".ass").exists()
    video = videos_dir / f"{story_id}_final.mp4"
    has_video = video.exists()
    missing: List[str] = []
    if not has_visuals:
        missing.append("visuals")
    if not has_voice:
        missing.append("audio")
    if not has_sub:
        missing.append("subtitles")
    if not has_video:
        missing.append("video")
    status = "✅ Complete" if not missing else f"❌ Missing {'/'.join(missing)}"
    preview = (
        f"<video src='../output/videos/{video.name}' width='320' controls></video>" if has_video else "—"
    )
    date = story_id.split("_")[0]
    return {"date": date, "status": status, "preview": preview}


@app.command()
def main(
    stories_dir: Path = typer.Option(Path("content/stories"), help="Story markdown directory"),
    visuals_dir: Path = typer.Option(Path("content/visuals"), help="Visual assets"),
    voice_dir: Path = typer.Option(Path("content/audio/voiceovers"), help="Voiceover directory"),
    videos_dir: Path = typer.Option(Path("output/videos"), help="Rendered videos"),
    dashboard_file: Path = typer.Option(Path("dashboard/index.html"), help="Output HTML file"),
) -> None:
    """Generate the dashboard HTML summarising pipeline state."""
    dashboard_file.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        _status_for_story(s, visuals_dir, voice_dir, videos_dir)
        for s in sorted(stories_dir.glob("*.md"))
    ]
    html = [
        "<html><head><meta charset='utf-8'><title>Dark Life Dashboard</title></head><body>",
        "<table border='1'><tr><th>Date</th><th>Status</th><th>Preview</th></tr>",
    ]
    for row in rows:
        html.append(
            f"<tr><td>{row['date']}</td><td>{row['status']}</td><td>{row['preview']}</td></tr>"
        )
    html.append("</table></body></html>")
    dashboard_file.write_text("\n".join(html), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    app()

