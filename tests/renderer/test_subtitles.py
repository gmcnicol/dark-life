import json
import logging
import wave
from pathlib import Path

import pytest

from services.renderer import subtitles
from shared.config import settings


class DummySegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class DummyModel:
    def __init__(self, *args, **kwargs):
        pass

    def transcribe(self, path):  # pragma: no cover - simple stub
        segments = [
            DummySegment(0.0, 1.0, "Hello"),
            DummySegment(1.0, 2.0, "world"),
            DummySegment(2.0, 3.0, "!!!"),
        ]
        return segments, None


def _silent_wav(path: Path, duration: float = 1.0, sr: int = 16000) -> None:
    nframes = int(sr * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(b"\x00\x00" * nframes)


def test_srt_and_vtt_formatting(tmp_path):
    segs = [subtitles.Segment(0.0, 1.0, "Hello"), subtitles.Segment(1.0, 2.0, "world")]
    srt = tmp_path / "test.srt"
    vtt = tmp_path / "test.vtt"
    subtitles._write_srt(segs, srt)
    subtitles._write_vtt(segs, vtt)
    assert "00:00:00,000 --> 00:00:01,000" in srt.read_text(encoding="utf-8")
    vtt_text = vtt.read_text(encoding="utf-8")
    assert vtt_text.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.000" in vtt_text


def test_drift_detection_warns(tmp_path, monkeypatch, caplog):
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    vo = job_dir / "vo.wav"
    _silent_wav(vo, duration=1.0)

    monkeypatch.setattr(settings, "TMP_DIR", tmp_path)
    monkeypatch.setattr(settings, "WHISPER_MODEL", "tiny")
    monkeypatch.setattr(settings, "WHISPER_DEVICE", "cpu")
    monkeypatch.setattr(settings, "SUBTITLES_FORMAT", "srt")
    monkeypatch.setattr(settings, "SUBTITLES_BURN_IN", False)

    monkeypatch.setattr(subtitles, "WhisperModel", DummyModel)

    with caplog.at_level(logging.WARNING):
        out = subtitles.generate(job_id="job", part_id="p1")

    assert out.exists()
    warnings = [json.loads(r.message) for r in caplog.records if r.levelname == "WARNING"]
    assert warnings and warnings[0]["event"] == "subs_drift"
