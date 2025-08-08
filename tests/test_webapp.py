from typer.testing import CliRunner
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import webapp.main as main  # noqa: E402

app = main.app
cli = main.cli


def test_index_route():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_cli_run_command_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["run", "--help"])
    assert result.exit_code == 0
    assert "Run the Flask development server." in result.stdout


@pytest.mark.parametrize(
    "story_name,images,create_story",
    [
        ("missing.md", "", False),
        ("story.md", "missing.jpg", True),
    ],
)
def test_queue_story_invalid_inputs(tmp_path, monkeypatch, story_name, images, create_story):
    stories_dir = tmp_path / "stories"
    visuals_dir = tmp_path / "visuals"
    queue_dir = tmp_path / "queue"
    stories_dir.mkdir()
    visuals_dir.mkdir()
    queue_dir.mkdir()
    monkeypatch.setattr(main.config, "STORIES_DIR", stories_dir)
    monkeypatch.setattr(main.config, "VISUALS_DIR", visuals_dir)
    monkeypatch.setattr(main.config, "RENDER_QUEUE_DIR", queue_dir)
    if create_story:
        (stories_dir / story_name).write_text("content")

    client = app.test_client()
    resp = client.post("/queue", data={"story": story_name, "images": images})
    assert resp.status_code == 302
    assert list(queue_dir.iterdir()) == []
    with client.session_transaction() as sess:
        assert "_flashes" in sess
