import json

import pytest
import requests

from apps.api.models import Story
from apps.api.refinement import OpenAIRefinementError, extract_concept_payload, generate_candidate_payloads
from shared.config import settings


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error


def _story() -> Story:
    return Story(id=12, title="Spoons", body_md="One. Two. Three. Four. Five.")


def test_extract_concept_retries_timeout_then_succeeds(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "token")
    monkeypatch.setattr(settings, "OPENAI_SCRIPT_MODEL", "gpt-5")
    monkeypatch.setattr(settings, "REFINEMENT_OPENAI_MAX_ATTEMPTS", 5)

    calls = {"count": 0}
    sleep_calls = []

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.Timeout("timed out")
        return FakeResponse(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "concept_key": "spoon-thing",
                                        "concept_label": "Spoon Thing",
                                        "anomaly_type": "entity",
                                        "object_focus": "spoon",
                                        "specificity": "concrete",
                                    }
                                ),
                            }
                        ],
                    }
                ]
            }
        )

    monkeypatch.setattr("apps.api.refinement.requests.post", fake_post)
    monkeypatch.setattr("apps.api.refinement.time.sleep", lambda delay: sleep_calls.append(delay))
    monkeypatch.setattr("apps.api.refinement.random.uniform", lambda a, b: 0.0)

    payload, metadata = extract_concept_payload(_story(), include_retry_metadata=True)

    assert payload["concept_key"] == "spoon-thing"
    assert metadata["attempt_count"] == 3
    assert metadata["last_error_class"] == "Timeout"
    assert len(sleep_calls) == 2


def test_generate_candidates_falls_back_after_empty_responses(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "token")
    monkeypatch.setattr(settings, "OPENAI_SCRIPT_MODEL", "gpt-5")
    monkeypatch.setattr(settings, "REFINEMENT_OPENAI_MAX_ATTEMPTS", 5)

    def fake_post(*args, **kwargs):
        return FakeResponse(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({"candidates": []}),
                            }
                        ],
                    }
                ]
            }
        )

    monkeypatch.setattr("apps.api.refinement.requests.post", fake_post)
    monkeypatch.setattr("apps.api.refinement.time.sleep", lambda delay: None)
    monkeypatch.setattr("apps.api.refinement.random.uniform", lambda a, b: 0.0)

    candidates, metadata = generate_candidate_payloads(
        _story(),
        concept=None,
        candidate_count=2,
        include_retry_metadata=True,
    )

    assert len(candidates) == 2
    assert metadata["fallback_used"] is True
    assert metadata["fallback_reason"] == "openai_empty_response"
    assert metadata["attempt_count"] == 5


def test_generate_candidates_raises_on_non_retryable_invalid_json(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "token")
    monkeypatch.setattr(settings, "OPENAI_SCRIPT_MODEL", "gpt-5")
    monkeypatch.setattr(settings, "REFINEMENT_OPENAI_MAX_ATTEMPTS", 5)

    monkeypatch.setattr(
        "apps.api.refinement.requests.post",
        lambda *args, **kwargs: FakeResponse(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "{not-json"}],
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr("apps.api.refinement.time.sleep", lambda delay: None)
    monkeypatch.setattr("apps.api.refinement.random.uniform", lambda a, b: 0.0)

    with pytest.raises(OpenAIRefinementError) as exc_info:
        generate_candidate_payloads(_story(), concept=None, candidate_count=1)

    assert exc_info.value.retryable is False
    assert exc_info.value.attempt_count == 1
