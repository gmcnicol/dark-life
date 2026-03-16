import json

import apps.api.pipeline as pipeline
from apps.api.models import ScriptVersion, Story


class _DummyResponse:
    def __init__(self, payload: dict[str, str]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return self._payload


def test_generate_script_payload_uses_serial_chapter_prompt(monkeypatch):
    captured: dict[str, object] = {}

    def fake_post(url: str, headers: dict[str, str], json: dict[str, object], timeout: int):
        captured["url"] = url
        captured["payload"] = json
        return _DummyResponse(
            {
                "output_text": json_module.dumps(
                    {
                        "hook": "I knew the call was a mistake.",
                        "narration_text": "\n\n".join(f"Chapter body {index}" for index in range(1, 6)),
                        "outro": "But I still answered.",
                    }
                )
            }
        )

    json_module = json
    monkeypatch.setattr(pipeline.settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(pipeline.settings, "OPENAI_SCRIPT_MODEL", "gpt-5-mini")
    monkeypatch.setattr(pipeline.requests, "post", fake_post)

    story = Story(title="The Call From Upstairs", body_md="I heard footsteps above me every night.")
    result = pipeline.generate_script_payload(story)

    assert result["model_name"] == "gpt-5-mini"
    payload = captured["payload"]
    assert payload["model"] == "gpt-5-mini"
    prompt = payload["input"][0]["content"][0]["text"]
    assert "5 to 7 shorts/reels" in prompt
    assert "The full story must stay coherent" in prompt
    assert "separated by a blank line" in prompt
    assert "'I remember'" in prompt


def test_heuristic_first_person_avoids_repetitive_i_remember():
    payload = pipeline._heuristic_first_person(
        "The hallway was empty. A door moved on its own.",
        "The Hallway",
    )

    assert payload["model_name"] == "rule_based"
    assert "I remember" not in payload["hook"]
    assert "I remember" not in payload["narration_text"]
    assert payload["narration_text"] == "The hallway was empty. A door moved on its own."


def test_script_part_specs_preserve_chapter_breaks():
    script = ScriptVersion(
        story_id=1,
        source_text="source",
        hook="Something was already in the house.",
        narration_text="\n\n".join(
            [
                "I heard it in the walls before I saw it.",
                "The sound kept moving closer every night.",
                "My brother said he heard nothing at all.",
                "Then the bedroom door opened by itself.",
                "I finally looked under the bed.",
            ]
        ),
        outro="I should have kept the lights on.",
    )

    parts = pipeline._script_part_specs(script)

    assert len(parts) == 5
    assert parts[0][0].startswith("Something was already in the house.")
    assert parts[-1][0].endswith("I should have kept the lights on.")
