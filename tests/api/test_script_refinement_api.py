import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from apps.api.db import get_session
import apps.api.main as main
from apps.api.pipeline import ensure_default_presets
from apps.api.models import Story
from apps.api.refinement import ensure_default_prompt_versions
from apps.api.script_refinement import run_compat_script_generation
from shared.config import settings


@pytest.fixture(name="client")
def client_fixture(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    monkeypatch.setattr(main, "init_db", lambda: None)
    monkeypatch.setattr(main, "engine", engine)
    main.app.dependency_overrides[get_session] = get_test_session
    monkeypatch.setenv("API_AUTH_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "local-admin")
    with TestClient(main.app) as client:
        with Session(engine) as session:
            ensure_default_presets(session)
            ensure_default_prompt_versions(session)
        yield client, engine
    main.app.dependency_overrides.clear()


def _worker_headers() -> dict[str, str]:
    return {"Authorization": "Bearer local-admin"}


def _candidate(label: str) -> dict[str, object]:
    episodes = []
    for index, episode_type in enumerate(["entry", "escalation", "escalation", "twist", "perspective"], start=1):
        episodes.append(
            {
                "episode_type": episode_type,
                "body_md": f"{label} episode {index} body.",
                "hook": f"{label} episode {index} hook.",
                "lines": [f"{label} line {index}a", f"{label} line {index}b"],
                "loop_line": f"{label} episode {index} loop?",
            }
        )
    return {
        "hook": f"{label} master hook.",
        "narration_text": "\n\n".join(str(episode["body_md"]) for episode in episodes),
        "outro": f"{label} outro.",
        "episodes": episodes,
    }


def test_script_batch_flow_creates_candidates_and_shortlist(client):
    client, _engine = client
    story = client.post("/stories", json={"title": "Refine me", "body_md": "One. Two. Three. Four. Five."}).json()

    created = client.post(
        f"/stories/{story['id']}/script-batches",
        json={"candidate_count": 2, "shortlisted_count": 1},
    )
    assert created.status_code == 200
    batch_id = created.json()["batch"]["id"]

    jobs = client.get("/refinement-jobs", params={"status": "queued"}, headers=_worker_headers())
    assert jobs.status_code == 200
    extract_job = next(job for job in jobs.json() if job["payload"]["batch_id"] == batch_id)
    claim = client.post(
        f"/refinement-jobs/{extract_job['id']}/claim",
        json={"lease_seconds": 180},
        headers=_worker_headers(),
    )
    assert claim.status_code == 200
    rendering = client.post(
        f"/refinement-jobs/{extract_job['id']}/status",
        json={"status": "rendering"},
        headers=_worker_headers(),
    )
    assert rendering.status_code == 200

    extract_done = client.post(
        f"/refinement-jobs/{extract_job['id']}/status",
        json={
            "status": "rendered",
            "metadata": {
                "concept": {
                    "concept_key": "mirror-thing",
                    "concept_label": "Mirror Thing",
                    "anomaly_type": "entity",
                    "object_focus": "mirror",
                    "specificity": "concrete",
                }
            },
        },
        headers=_worker_headers(),
    )
    assert extract_done.status_code == 200

    jobs = client.get("/refinement-jobs", params={"status": "queued"}, headers=_worker_headers()).json()
    generate_job = next(job for job in jobs if job["kind"] == "refine_generate_batch" and job["payload"]["batch_id"] == batch_id)
    claim = client.post(
        f"/refinement-jobs/{generate_job['id']}/claim",
        json={"lease_seconds": 180},
        headers=_worker_headers(),
    )
    assert claim.status_code == 200
    generate_rendering = client.post(
        f"/refinement-jobs/{generate_job['id']}/status",
        json={"status": "rendering"},
        headers=_worker_headers(),
    )
    assert generate_rendering.status_code == 200
    generate_done = client.post(
        f"/refinement-jobs/{generate_job['id']}/status",
        json={"status": "rendered", "metadata": {"candidates": [_candidate("A"), _candidate("B")]}},
        headers=_worker_headers(),
    )
    assert generate_done.status_code == 200

    jobs = client.get("/refinement-jobs", params={"status": "queued"}, headers=_worker_headers()).json()
    critic_job = next(job for job in jobs if job["kind"] == "refine_critic_batch" and job["payload"]["batch_id"] == batch_id)
    claim = client.post(
        f"/refinement-jobs/{critic_job['id']}/claim",
        json={"lease_seconds": 180},
        headers=_worker_headers(),
    )
    assert claim.status_code == 200
    critic_rendering = client.post(
        f"/refinement-jobs/{critic_job['id']}/status",
        json={"status": "rendering"},
        headers=_worker_headers(),
    )
    assert critic_rendering.status_code == 200
    critic_done = client.post(
        f"/refinement-jobs/{critic_job['id']}/status",
        json={"status": "rendered"},
        headers=_worker_headers(),
    )
    assert critic_done.status_code == 200

    detail = client.get(f"/script-batches/{batch_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["batch"]["status"] == "ready_for_review"
    assert payload["concept"]["concept_label"] == "Mirror Thing"
    assert len(payload["candidates"]) == 2
    assert sum(1 for candidate in payload["candidates"] if candidate["selection_state"] == "shortlisted") == 1


def test_script_version_releases_are_variant_aware(client):
    client, engine = client
    story = client.post("/stories", json={"title": "Variant story", "body_md": "One. Two. Three. Four. Five."}).json()
    with Session(engine) as session:
        story_model = session.get(Story, story["id"])
        assert story_model is not None
        script = run_compat_script_generation(session, story_model)
        session.commit()
        session.refresh(script)

    bundle = client.post(
        f"/stories/{story['id']}/asset-bundles",
        json={
            "name": "Primary bundle",
            "asset_refs": [
                {
                    "key": "asset-1",
                    "type": "image",
                    "remote_url": "https://example.com/asset.jpg",
                    "provider": "pixabay",
                    "provider_id": "asset-1",
                }
            ],
        },
    )
    assert bundle.status_code == 200

    releases = client.post(
        f"/script-versions/{script.id}/releases",
        json={"platforms": ["youtube"], "preset_slug": "short-form", "asset_bundle_id": bundle.json()["id"]},
    )
    assert releases.status_code == 200
    rows = releases.json()
    parts = client.get(f"/script-versions/{script.id}/parts")
    assert parts.status_code == 200
    assert len(rows) == len(parts.json())
    assert all(row["script_version_id"] == script.id for row in rows)


def test_prompt_version_activation_archives_previous_active(client):
    client, _engine = client
    created = client.post(
        "/prompt-versions",
        json={
            "kind": "generator",
            "version_label": "gen_prompt_v_next",
            "body": "A draft generator prompt.",
        },
    )
    assert created.status_code == 200

    activated = client.post(f"/prompt-versions/{created.json()['id']}/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    prompts = client.get("/prompt-versions?kind=generator")
    assert prompts.status_code == 200
    statuses = {prompt["version_label"]: prompt["status"] for prompt in prompts.json()}
    assert statuses["gen_prompt_v_next"] == "active"
    assert "archived" in statuses.values()


def test_generate_job_status_persists_retry_and_fallback_metadata(client):
    client, _engine = client
    story = client.post("/stories", json={"title": "Refine me", "body_md": "One. Two. Three. Four. Five."}).json()

    created = client.post(
        f"/stories/{story['id']}/script-batches",
        json={"candidate_count": 2, "shortlisted_count": 1},
    )
    batch_id = created.json()["batch"]["id"]

    jobs = client.get("/refinement-jobs", params={"status": "queued"}, headers=_worker_headers()).json()
    extract_job = next(job for job in jobs if job["payload"]["batch_id"] == batch_id)
    client.post(
        f"/refinement-jobs/{extract_job['id']}/claim",
        json={"lease_seconds": 180},
        headers=_worker_headers(),
    )
    client.post(
        f"/refinement-jobs/{extract_job['id']}/status",
        json={"status": "rendering"},
        headers=_worker_headers(),
    )
    client.post(
        f"/refinement-jobs/{extract_job['id']}/status",
        json={
            "status": "rendered",
            "metadata": {
                "concept": {
                    "concept_key": "mirror-thing",
                    "concept_label": "Mirror Thing",
                    "anomaly_type": "entity",
                    "object_focus": "mirror",
                    "specificity": "concrete",
                }
            },
        },
        headers=_worker_headers(),
    )

    jobs = client.get("/refinement-jobs", params={"status": "queued"}, headers=_worker_headers()).json()
    generate_job = next(job for job in jobs if job["kind"] == "refine_generate_batch" and job["payload"]["batch_id"] == batch_id)
    client.post(
        f"/refinement-jobs/{generate_job['id']}/claim",
        json={"lease_seconds": 180},
        headers=_worker_headers(),
    )
    client.post(
        f"/refinement-jobs/{generate_job['id']}/status",
        json={"status": "rendering"},
        headers=_worker_headers(),
    )
    generate_done = client.post(
        f"/refinement-jobs/{generate_job['id']}/status",
        json={
            "status": "rendered",
            "metadata": {
                "candidates": [_candidate("A"), _candidate("B")],
                "attempt_count": 5,
                "last_error_class": "ReadTimeout",
                "last_error_message": "timed out",
                "fallback_used": True,
                "fallback_reason": "openai_empty_response",
            },
        },
        headers=_worker_headers(),
    )
    assert generate_done.status_code == 200
    assert generate_done.json()["retries"] == 4
    assert generate_done.json()["result"]["fallback_used"] is True

    detail = client.get(f"/script-batches/{batch_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["batch"]["result"]["fallback_used"] is True
    assert payload["batch"]["result"]["fallback_reason"] == "openai_empty_response"


def test_retryable_refinement_error_updates_job_retries(client):
    client, _engine = client
    story = client.post("/stories", json={"title": "Retry me", "body_md": "One. Two. Three. Four. Five."}).json()
    created = client.post(
        f"/stories/{story['id']}/script-batches",
        json={"candidate_count": 2, "shortlisted_count": 1},
    )
    batch_id = created.json()["batch"]["id"]
    jobs = client.get("/refinement-jobs", params={"status": "queued"}, headers=_worker_headers()).json()
    extract_job = next(job for job in jobs if job["payload"]["batch_id"] == batch_id)

    client.post(
        f"/refinement-jobs/{extract_job['id']}/claim",
        json={"lease_seconds": 180},
        headers=_worker_headers(),
    )
    client.post(
        f"/refinement-jobs/{extract_job['id']}/status",
        json={"status": "rendering"},
        headers=_worker_headers(),
    )
    errored = client.post(
        f"/refinement-jobs/{extract_job['id']}/status",
        json={
            "status": "errored",
            "retryable": True,
            "error_class": "ReadTimeout",
            "error_message": "timed out",
            "metadata": {
                "attempt_count": 5,
                "last_error_class": "ReadTimeout",
                "last_error_message": "timed out",
            },
        },
        headers=_worker_headers(),
    )
    assert errored.status_code == 200
    assert errored.json()["retries"] == 4
    assert errored.json()["result"]["attempt_count"] == 5

    detail = client.get(f"/script-batches/{batch_id}")
    assert detail.status_code == 200
    assert detail.json()["batch"]["status"] == "errored"
    assert detail.json()["batch"]["result"]["last_error_class"] == "ReadTimeout"
