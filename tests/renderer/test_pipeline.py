from pathlib import Path

from services.renderer import pipeline
from shared.config import settings


def test_render_compilation_job_reframes_segments_to_landscape(tmp_path, monkeypatch):
    tmp_dir = tmp_path / "tmp"
    out_dir = tmp_path / "out"
    tmp_dir.mkdir()
    out_dir.mkdir()
    monkeypatch.setattr(settings, "TMP_DIR", tmp_dir)
    monkeypatch.setattr(settings, "OUTPUT_DIR", out_dir)

    segment_one = tmp_path / "part-1.mp4"
    segment_two = tmp_path / "part-2.mp4"
    segment_one.write_bytes(b"one")
    segment_two.write_bytes(b"two")

    reframed: list[tuple[Path, Path, dict[str, int | bool]]] = []
    concatenated: list[tuple[list[Path], Path]] = []

    def fake_reframe(video: Path, out_path: Path, *, preset: dict[str, int | bool]) -> Path:
        reframed.append((video, out_path, preset))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(video.read_bytes())
        return out_path

    def fake_concat(inputs: list[Path], out_path: Path) -> Path:
        concatenated.append((inputs, out_path))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"weekly")
        return out_path

    monkeypatch.setattr(pipeline.ffmpeg, "reframe_video_to_landscape", fake_reframe)
    monkeypatch.setattr(pipeline.ffmpeg, "concat_videos", fake_concat)
    monkeypatch.setattr(pipeline.ffmpeg, "probe_duration_ms", lambda _path: 7_000)

    result = pipeline.render_compilation_job(
        {
            "job": {"id": 91},
            "story": {"id": 12},
            "compilation": {"id": 6},
            "render_preset": {"slug": "weekly-full", "width": 1920, "height": 1080, "fps": 30},
            "parts": [{"id": 101, "index": 1}, {"id": 102, "index": 2}],
            "artifacts": [
                {"variant": "short", "story_part_id": 101, "video_path": str(segment_one)},
                {"variant": "short", "story_part_id": 102, "video_path": str(segment_two)},
            ],
        }
    )

    assert [call[0] for call in reframed] == [segment_one, segment_two]
    assert all(call[2]["slug"] == "weekly-full" for call in reframed)
    assert concatenated
    assert concatenated[0][0] == [call[1] for call in reframed]
    assert result["metadata"]["compiler"] == "renderer.compilation.v2"
    assert result["metadata"]["preset_slug"] == "weekly-full"
    assert result["artifact_path"].endswith("/stories/12/jobs/91/video.mp4")
