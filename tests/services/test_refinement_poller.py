import pytest

from apps.api.refinement import OpenAIRefinementError
from services.refinement import poller
from shared.config import settings


class Resp:
    def __init__(self, data=None, status_code=200):
        self._data = data
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_run_refinement_job_extract_includes_retry_metadata(monkeypatch):
    monkeypatch.setattr(
        poller.RefinementApiClient,
        "get_context",
        lambda self, job_id: {
            "story": {"id": 10, "title": "A story", "body_md": "One. Two."},
        },
    )
    monkeypatch.setattr(
        poller,
        "extract_concept_payload",
        lambda story, include_retry_metadata=True: (
            {"concept_key": "mirror", "concept_label": "Mirror", "anomaly_type": "entity", "object_focus": "mirror", "specificity": "concrete"},
            {"attempt_count": 3, "last_error_class": "Timeout", "last_error_message": "timed out"},
        ),
    )

    result = poller.run_refinement_job({"id": 1, "kind": "refine_extract_concept"})

    assert result["metadata"]["concept"]["concept_key"] == "mirror"
    assert result["metadata"]["attempt_count"] == 3
    assert result["metadata"]["last_error_class"] == "Timeout"


def test_process_job_reports_retryable_openai_failure(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 1)
    monkeypatch.setattr(settings, "HEARTBEAT_INTERVAL_SEC", 0.01)

    calls = []

    def fake_get(url, params=None, timeout=0, headers=None):
        if url.endswith("/context"):
            return Resp(
                data={
                    "story": {"id": 10, "title": "A story", "body_md": "One. Two."},
                    "batch": {"candidate_count": 2},
                }
            )
        raise AssertionError(url)

    def fake_post(url, json=None, timeout=0, headers=None):
        calls.append((url, json))
        return Resp()

    monkeypatch.setattr(poller.requests, "get", fake_get)
    monkeypatch.setattr(poller.requests, "post", fake_post)
    monkeypatch.setattr(
        poller,
        "run_refinement_job",
        lambda job, session=None: (_ for _ in ()).throw(
            OpenAIRefinementError(
                "OpenAI candidate generation failed",
                retryable=True,
                attempt_count=5,
                last_error_class="ReadTimeout",
                last_error_message="timed out",
                response_summary="status=incomplete",
            )
        ),
    )

    poller.process_job({"id": 7, "kind": "refine_generate_batch", "correlation_id": "cid-7"})

    status_payloads = [json for url, json in calls if url.endswith("/status")]
    assert any(payload.get("retryable") is True for payload in status_payloads)
    errored = next(payload for payload in status_payloads if payload.get("status") == "errored")
    assert errored["metadata"]["attempt_count"] == 5
    assert errored["metadata"]["last_error_class"] == "ReadTimeout"
    assert errored["stderr_snippet"] == "status=incomplete"
