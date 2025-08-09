from pathlib import Path

from shared.config import settings
from shared.types import RenderJob
from video_renderer import render_job_runner


def test_process_job_writes_manifest(tmp_path, monkeypatch):
    content_dir = tmp_path / "content"
    stories_dir = content_dir / "stories"
    stories_dir.mkdir(parents=True)
    video_dir = tmp_path / "videos"
    manifest_dir = tmp_path / "manifest"

    monkeypatch.setattr(settings, "CONTENT_DIR", content_dir)
    monkeypatch.setattr(settings, "STORIES_DIR", stories_dir)
    monkeypatch.setattr(settings, "VIDEO_OUTPUT_DIR", video_dir)
    monkeypatch.setattr(settings, "MANIFEST_DIR", manifest_dir)

    story_file = stories_dir / "1.md"
    story_file.write_text("story")

    job = RenderJob(story_path=story_file, image_paths=[])

    def fake_voiceover(input_dir: Path, output_dir: Path) -> None:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    def fake_whisper(input_dir: Path, output_dir: Path) -> None:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    def fake_slideshow(args: list[str]) -> int:
        story_id = args[args.index("--story_id") + 1]
        video_dir.mkdir(parents=True, exist_ok=True)
        (video_dir / f"{story_id}_final.mp4").write_text("video")
        return 0

    monkeypatch.setattr(render_job_runner.voiceover, "main", fake_voiceover)
    monkeypatch.setattr(render_job_runner.whisper_subs, "main", fake_whisper)
    monkeypatch.setattr(render_job_runner.create_slideshow, "main", fake_slideshow)

    assert render_job_runner._process_job(job)
    manifest_file = manifest_dir / "1.json"
    assert manifest_file.exists()
