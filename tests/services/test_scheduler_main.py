from __future__ import annotations

from pathlib import Path

from services.scheduler import main as scheduler_main


class FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self):
        self.bundle_payloads: list[dict] = []
        self.release_payloads: list[dict] = []

    def get(self, url, params=None, headers=None, timeout=0):
        if url.endswith("/stories"):
            return FakeResponse(
                [
                    {
                        "id": 160,
                        "status": "approved",
                        "active_script_version_id": 88,
                    }
                ]
            )
        if url.endswith("/stories/160/releases"):
            return FakeResponse([])
        if url.endswith("/stories/160/asset-bundles"):
            return FakeResponse([{"id": 1}, {"id": 2}])
        if url.endswith("/stories/160/assets"):
            assert params == {"page": 4}
            return FakeResponse(
                [
                    {
                        "key": "pixabay:9001",
                        "remote_url": "https://example.com/fresh-image.jpg",
                        "provider": "pixabay",
                        "provider_id": "9001",
                        "type": "image",
                        "orientation": "portrait",
                    }
                ]
            )
        raise AssertionError(url)

    def post(self, url, json=None, headers=None, timeout=0):
        if url.endswith("/stories/160/asset-bundles"):
            self.bundle_payloads.append(json or {})
            return FakeResponse({"id": 77})
        if url.endswith("/stories/160/releases"):
            self.release_payloads.append(json or {})
            return FakeResponse([{"id": 501}, {"id": 502}])
        raise AssertionError(url)


def test_schedule_approved_shorts_creates_fresh_bundle_and_releases(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(scheduler_main.settings, "API_AUTH_TOKEN", "local-admin")

    scheduler_main.schedule_approved_shorts(session)

    assert session.bundle_payloads
    assert session.bundle_payloads[0]["asset_refs"][0]["provider"] == "pixabay"
    assert session.bundle_payloads[0]["variant"] == "short"
    assert session.release_payloads == [
        {
            "preset_slug": "short-form",
            "asset_bundle_id": 77,
        }
    ]


def test_write_heartbeat_creates_scheduler_marker(monkeypatch, tmp_path):
    heartbeat_path = tmp_path / "scheduler_heartbeat"
    monkeypatch.setattr(scheduler_main, "HEARTBEAT_PATH", heartbeat_path)

    scheduler_main.write_heartbeat()

    assert heartbeat_path.exists()
