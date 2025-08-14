from pathlib import Path

from shared.config import settings
from services.renderer import poller


def test_poller_processes_series(tmp_path, monkeypatch):
    video_dir = tmp_path / "videos"
    monkeypatch.setattr(settings, "VIDEO_OUTPUT_DIR", video_dir)
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")

    api_response = {
        "story": {"id": 1, "title": "Test Story"},
        "assets": [{"id": 1, "remote_url": "http://example.com/img.jpg"}],
        "parts": [
            {"job_id": 123, "index": 1, "body_md": "Hello world"},
        ],
    }

    def fake_get(url, timeout, headers=None):
        class Resp:
            def __init__(self, content: bytes = b"", data=None):
                self.content = content
                self._data = data

            def raise_for_status(self):
                pass

            def json(self):  # type: ignore[override]
                return self._data

        if url.endswith("/render/next-series"):
            return Resp(data=api_response)
        return Resp(content=b"img")

    patch_calls = []

    def fake_patch(url, json, timeout, headers=None):
        patch_calls.append((url, json))
        class Resp:
            def raise_for_status(self):
                pass
        return Resp()

    def fake_slideshow(args):
        story_id = args[args.index("--story_id") + 1]
        output_dir = Path(args[args.index("--output-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{story_id}_final.mp4").write_bytes(b"vid")
        return 0

    monkeypatch.setattr(poller.requests, "get", fake_get)
    monkeypatch.setattr(poller.requests, "patch", fake_patch)
    monkeypatch.setattr(poller.create_slideshow, "main", fake_slideshow)
    monkeypatch.setattr(poller.voiceover, "_synth_with_pyttsx3", lambda engine, text, dest: False)
    monkeypatch.setattr(poller.voiceover, "_placeholder_audio", lambda text, dest: dest.write_bytes(b"a"))

    processed = poller.process_once()

    assert processed
    video_path = video_dir / "test-story_p01.mp4"
    assert video_path.exists()
    assert patch_calls and patch_calls[0][1]["status"] == "success"
