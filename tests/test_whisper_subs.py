import pytest
from pydub import AudioSegment

from video_renderer import whisper_subs as ws


@pytest.mark.parametrize("duration_ms", [3000, 6000])
def test_srt_timings_vary_with_audio_length(tmp_path, duration_ms):
    voice_dir = tmp_path / "voiceovers"
    story_dir = tmp_path / "stories"
    voice_dir.mkdir()
    story_dir.mkdir()

    # create audio file
    audio = AudioSegment.silent(duration=duration_ms)
    voice_path = voice_dir / "sample.mp3"
    audio.export(voice_path, format="mp3")

    # corresponding story with two sentences
    (story_dir / "sample.md").write_text("One. Two.", encoding="utf-8")

    ws.main(input_dir=voice_dir, stories_dir=story_dir, fmt="srt")

    srt_path = voice_path.with_suffix(".srt")
    lines = srt_path.read_text().splitlines()
    timings = [l for l in lines if " --> " in l]
    per_sentence = (duration_ms / 1000) / 2
    expected_first_end = ws._format_srt_time(per_sentence)
    expected_total = ws._format_srt_time(duration_ms / 1000)
    assert timings[0] == f"00:00:00,000 --> {expected_first_end}"
    assert timings[1] == f"{expected_first_end} --> {expected_total}"


def test_ass_timings(tmp_path):
    voice_dir = tmp_path / "voiceovers"
    story_dir = tmp_path / "stories"
    voice_dir.mkdir()
    story_dir.mkdir()

    duration_ms = 4000
    audio = AudioSegment.silent(duration=duration_ms)
    voice_path = voice_dir / "story.mp3"
    audio.export(voice_path, format="mp3")
    (story_dir / "story.md").write_text("First. Second.", encoding="utf-8")

    ws.main(input_dir=voice_dir, stories_dir=story_dir, fmt="ass")

    ass_path = voice_path.with_suffix(".ass")
    lines = ass_path.read_text().splitlines()
    dialogue = [l for l in lines if l.startswith("Dialogue")]
    per_sentence = (duration_ms / 1000) / 2
    expected_first_end = ws._format_ass_time(per_sentence)
    expected_total = ws._format_ass_time(duration_ms / 1000)
    assert dialogue[0] == f"Dialogue: 0,00:00:00.00,{expected_first_end},First."
    assert dialogue[1] == f"Dialogue: 0,{expected_first_end},{expected_total},Second."
