import sys
import json
from pathlib import Path

# Ensure project root is on sys.path for module imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.config import settings
from webapp.main import app


def test_queue_story_creates_job_file(tmp_path, monkeypatch):
    stories_dir = tmp_path / "stories"
    visuals_dir = tmp_path / "visuals"
    queue_dir = tmp_path / "queue"
    stories_dir.mkdir()
    visuals_dir.mkdir()
    queue_dir.mkdir()

    monkeypatch.setattr(settings, "STORIES_DIR", stories_dir)
    monkeypatch.setattr(settings, "VISUALS_DIR", visuals_dir)
    monkeypatch.setattr(settings, "RENDER_QUEUE_DIR", queue_dir)

    story_file = stories_dir / "story.md"
    story_file.write_text("Example story")
    image_file = visuals_dir / "image.jpg"
    image_file.write_text("fake image data")

    client = app.test_client()
    response = client.post("/queue", data={"story": story_file.name, "images": image_file.name})
    assert response.status_code == 302

    job_file = queue_dir / f"{story_file.stem}.json"
    assert job_file.exists()
    job_data = json.loads(job_file.read_text())
    assert job_data == {
        "story_path": str(story_file.resolve()),
        "image_paths": [str(image_file.resolve())],
    }

    # Clean up temporary files
    job_file.unlink()
    story_file.unlink()
    image_file.unlink()
