import io
import shutil
import sys
import wave
from pathlib import Path
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


def test_cache_key_changes_with_provider():
    elevenlabs = tts.cache_key("s", "p", "v1", "m1", "hello", provider="elevenlabs")
    xtts_local = tts.cache_key("s", "p", "v1", "m1", "hello", provider="xtts_local")
    assert elevenlabs != xtts_local


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffmpeg required")
def test_synthesize_uses_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TTS_PROVIDER", "elevenlabs")
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


def test_synthesize_xtts_local_uses_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TTS_PROVIDER", "xtts_local")
    monkeypatch.setattr(settings, "TTS_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(settings, "XTTS_MODEL_DIR", tmp_path / "xtts_model")
    monkeypatch.setattr(settings, "XTTS_RUN_DIR", None)
    monkeypatch.setattr(settings, "XTTS_CHECKPOINT_PATH", None)
    monkeypatch.setattr(settings, "XTTS_CONFIG_PATH", None)
    monkeypatch.setattr(settings, "XTTS_VOCAB_PATH", None)
    monkeypatch.setattr(settings, "XTTS_SPEAKER_FILE_PATH", None)
    monkeypatch.setattr(settings, "XTTS_CHECKPOINT_GLOB", "best_model*.pth")
    monkeypatch.setattr(settings, "XTTS_SPEAKER_WAV", tmp_path / "ref.wav")
    monkeypatch.setattr(settings, "XTTS_LANGUAGE", "en")
    monkeypatch.setattr(settings, "XTTS_DEVICE", "cpu")
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 90)

    model_dir = settings.XTTS_MODEL_DIR
    assert model_dir is not None
    model_dir.mkdir(parents=True)
    (model_dir / "best_model_10.pth").write_bytes(b"older-checkpoint")
    (model_dir / "best_model_42.pth").write_bytes(b"newer-checkpoint")
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "vocab.json").write_text("{}", encoding="utf-8")
    (model_dir / "speakers_xtts.pth").write_bytes(b"speaker")
    assert settings.XTTS_SPEAKER_WAV is not None
    settings.XTTS_SPEAKER_WAV.write_bytes(_silent_wav_bytes())

    monkeypatch.setattr(tts, "_probe_duration_ms", lambda path: 1234)
    monkeypatch.setattr(tts, "_ensure_pcm", lambda src, dst: shutil.copyfile(src, dst))

    class FakeCompletedProcess:
        def __init__(self):
            self.stdout = ""
            self.stderr = ""

    class FakeSubprocess:
        def __init__(self):
            self.calls = 0

        def run(self, cmd, cwd, stdout, stderr, text, check, timeout, env):
            self.calls += 1
            assert cmd[:3] == [sys.executable, "-m", "services.renderer.xtts_runner"]
            assert cmd[cmd.index("--checkpoint") + 1].endswith("best_model_42.pth")
            assert "--vocab-path" in cmd
            assert "--speaker-file-path" in cmd
            assert "--language" in cmd
            assert env["PYTORCH_ENABLE_MPS_FALLBACK"] == "1"
            out_path = Path(cmd[cmd.index("--out") + 1])
            out_path.write_bytes(_silent_wav_bytes())
            return FakeCompletedProcess()

    fake_subprocess = FakeSubprocess()
    monkeypatch.setattr(tts.subprocess, "run", fake_subprocess.run)

    out1 = tmp_path / "vo1.wav"
    out2 = tmp_path / "vo2.wav"

    result1 = tts.synthesize_result("hello", story_id="s", part_id="p", out_path=out1)
    result2 = tts.synthesize_result("hello", story_id="s", part_id="p", out_path=out2)

    assert fake_subprocess.calls == 1
    assert result1.cache_hit is False
    assert result2.cache_hit is True
    assert result2.duration_ms == 1234
    assert out1.read_bytes() == out2.read_bytes()


def test_resolve_xtts_paths_uses_parent_vocab_fallback(monkeypatch, tmp_path):
    model_dir = tmp_path / "xtts_model"
    original_model_dir = tmp_path / "xtts_original_model_files"
    model_dir.mkdir(parents=True)
    original_model_dir.mkdir(parents=True)
    (model_dir / "best_model_5.pth").write_bytes(b"checkpoint")
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (original_model_dir / "vocab.json").write_text("{}", encoding="utf-8")
    speaker_wav = tmp_path / "ref.wav"
    speaker_wav.write_bytes(_silent_wav_bytes())

    monkeypatch.setattr(settings, "XTTS_MODEL_DIR", model_dir)
    monkeypatch.setattr(settings, "XTTS_RUN_DIR", None)
    monkeypatch.setattr(settings, "XTTS_CHECKPOINT_PATH", None)
    monkeypatch.setattr(settings, "XTTS_CONFIG_PATH", None)
    monkeypatch.setattr(settings, "XTTS_VOCAB_PATH", None)
    monkeypatch.setattr(settings, "XTTS_SPEAKER_FILE_PATH", None)
    monkeypatch.setattr(settings, "XTTS_CHECKPOINT_GLOB", "best_model*.pth")
    monkeypatch.setattr(settings, "XTTS_SPEAKER_WAV", speaker_wav)

    resolved = tts.resolve_xtts_paths()

    assert resolved.model_dir == model_dir
    assert resolved.run_dir == model_dir
    assert resolved.checkpoint_path == model_dir / "best_model_5.pth"
    assert resolved.vocab_path == original_model_dir / "vocab.json"
    assert resolved.speaker_file_path is None
