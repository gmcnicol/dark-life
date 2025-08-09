from video_renderer import whisper_subs as ws


def test_whisper_generates_srt(tmp_path, monkeypatch):
    voice_dir = tmp_path / "voiceovers"
    subs_dir = tmp_path / "subs"
    voice_dir.mkdir()
    subs_dir.mkdir()

    # Create a dummy MP3 file; the patched model does not read its contents
    (voice_dir / "hello.mp3").write_bytes(b"not a real mp3")

    class DummySegment:
        def __init__(self, start, end, text):
            self.start = start
            self.end = end
            self.text = text

    class DummyModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, path):  # pragma: no cover - simple stub
            return [DummySegment(0.0, 1.0, "hello world")], None

    monkeypatch.setattr(ws, "WhisperModel", DummyModel)

    ws.main(input_dir=voice_dir, output_dir=subs_dir, model_size="tiny")

    srt_path = subs_dir / "hello.srt"
    assert srt_path.exists()
    text = srt_path.read_text(encoding="utf-8").lower()
    assert "hello" in text and "world" in text

