from apps.api.stories import (
    _snap_boundaries,
    _estimate_seconds,
    CHARS_PER_SECOND,
)


def test_snap_boundaries_expands_to_sentence():
    text = "First sentence. Second one here. Third!"
    start, end = _snap_boundaries(text, 17, 25)
    assert text[start:end] == "Second one here."


def test_estimate_seconds_char_heuristic():
    length = int(CHARS_PER_SECOND * 2)
    text = "x" * length
    assert _estimate_seconds(text) == 2

