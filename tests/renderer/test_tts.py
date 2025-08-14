import io
import shutil
import wave
from unittest.mock import Mock

import pytest

from services.renderer import tts
from shared.config import settings


def _silent_wav_bytes(sr: int = 44100, duration: float = 0.1) -> bytes:
    buf = io.BytesIO()
    nframes = int(sr * duration)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * nframes)
    return buf.getvalue()


def test_cache_key_stability():
    key1 = tts.cache_key("s", "p", "v1", "m1", "hello")
    key2 = tts.cache_key("s", "p", "v1", "m1", "hello")
    key3 = tts.cache_key("s", "p", "v1", "m1", "world")
    assert key1 == key2
    assert key1 != key3


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffmpeg required")
def test_synthesize_uses_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ELEVENLABS_API_KEY", "testkey")
    monkeypatch.setattr(settings, "ELEVENLABS_VOICE_ID", "voice")
    monkeypatch.setattr(settings, "ELEVENLABS_MODEL_ID", "model")
    monkeypatch.setattr(settings, "TTS_CACHE_DIR", tmp_path / "cache")
    audio_bytes = _silent_wav_bytes()

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def post(self, url, json, headers, timeout):
            self.calls += 1
            resp = Mock()
            resp.status_code = 200
            resp.content = audio_bytes
            resp.raise_for_status = lambda: None
            return resp

    session = FakeSession()
    out1 = tmp_path / "vo1.wav"
    out2 = tmp_path / "vo2.wav"

    tts.synthesize("hello", story_id="s", part_id="p", out_path=out1, session=session)
    tts.synthesize("hello", story_id="s", part_id="p", out_path=out2, session=session)

    assert session.calls == 1
    assert out1.read_bytes() == out2.read_bytes()
