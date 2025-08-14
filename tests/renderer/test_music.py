import re
import shutil
import subprocess
from pathlib import Path

import pytest

from services.renderer import music
from shared.config import settings


def test_select_track_policy(tmp_path, monkeypatch):
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    (music_dir / "b.mp3").write_bytes(b"b")
    (music_dir / "a.mp3").write_bytes(b"a")
    monkeypatch.setattr(settings, "MUSIC_DIR", music_dir)

    track = music.select_track(required=True)
    assert track.name == "a.mp3"

    track = music.select_track("named:b.mp3", required=True)
    assert track.name == "b.mp3"

    with pytest.raises(FileNotFoundError):
        music.select_track("named:nope.mp3", required=True)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_mix_ducking(tmp_path, monkeypatch):
    voice = tmp_path / "voice.wav"
    music_src = tmp_path / "music.mp3"
    out = tmp_path / "mix.wav"

    subprocess.run([
        "ffmpeg",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=44100:cl=mono:d=1",
        "-filter_complex",
        "[0]volume=18dB[a];[a][1]concat=n=2:v=0:a=1",
        str(voice),
    ],
        check=True,
    )

    subprocess.run([
        "ffmpeg", "-f", "lavfi", "-i", "sine=frequency=880:duration=2", "-q:a", "9", "-acodec", "libmp3lame", str(music_src)
    ], check=True)

    monkeypatch.setattr(settings, "MUSIC_GAIN_DB", -3.0)
    monkeypatch.setattr(settings, "DUCKING_DB", -12.0)

    music.mix(voice, music_src, out)
    assert out.exists()

    def max_vol(
        path: Path,
        start: float | None = None,
        dur: float | None = None,
        bandpass: bool = False,
    ) -> float:
        cmd = ["ffmpeg", "-hide_banner"]
        if start is not None:
            cmd += ["-ss", str(start)]
        if dur is not None:
            cmd += ["-t", str(dur)]
        filter_chain = "volumedetect"
        if bandpass:
            filter_chain = "bandpass=f=880:width_type=h:width=100,volumedetect"
        cmd += ["-i", str(path), "-af", filter_chain, "-f", "null", "-"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
        m = re.search(r"max_volume: ([\-0-9\.]+) dB", res.stdout)
        assert m, res.stdout
        return float(m.group(1))

    peak = max_vol(out)
    assert peak < -1.0

    orig = max_vol(music_src, bandpass=True)
    ducked = max_vol(out, 0.2, 0.5, bandpass=True)
    assert orig - ducked > 5.0
