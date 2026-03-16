from services.publisher import poller
from services.publisher.pipeline import PublishPipelineError
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


def test_process_publish_job_happy_path(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 1)
    monkeypatch.setattr(settings, "HEARTBEAT_INTERVAL_SEC", 0.01)

    calls = []

    def fake_get(url, params=None, timeout=0, headers=None):
        if url.endswith("/publish-jobs"):
            return Resp(data=[{"id": 1, "platform": "youtube"}])
        if url.endswith("/context"):
            return Resp(
                data={
                    "publish_job": {"id": 1},
                    "release": {"id": 10, "story_id": 20, "platform": "youtube"},
                    "artifact": {"video_path": "/output/video.mp4"},
                }
            )
        raise AssertionError(url)

    def fake_post(url, json=None, timeout=0, headers=None):
        calls.append((url, json))
        return Resp()

    monkeypatch.setattr(poller.requests, "get", fake_get)
    monkeypatch.setattr(poller.requests, "post", fake_post)
    monkeypatch.setattr(poller, "publish_release", lambda context, session=None: {"platform_video_id": "yt-123"})

    job = poller.poll_jobs()[0]
    poller.process_job(job)

    assert any(url.endswith("/claim") for url, _json in calls)
    assert any((json or {}).get("status") == "publishing" for _url, json in calls)
    assert any((json or {}).get("platform_video_id") == "yt-123" for _url, json in calls if _url.endswith("/status"))


def test_publish_job_manual_handoff(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 1)
    monkeypatch.setattr(settings, "HEARTBEAT_INTERVAL_SEC", 0.01)

    calls = []

    def fake_get(url, params=None, timeout=0, headers=None):
        if url.endswith("/publish-jobs"):
            return Resp(data=[{"id": 2, "platform": "tiktok"}])
        if url.endswith("/context"):
            return Resp(
                data={
                    "publish_job": {"id": 2},
                    "release": {"id": 11, "story_id": 21, "platform": "tiktok"},
                    "artifact": {"video_path": "/output/video.mp4"},
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
        "publish_release",
        lambda context, session=None: {
            "release_status_override": "manual_handoff",
            "metadata": {"manual_handoff": {"asset_url": "https://example.com/video.mp4"}},
        },
    )

    job = poller.poll_jobs()[0]
    poller.process_job(job)

    assert any((json or {}).get("release_status_override") == "manual_handoff" for _url, json in calls if _url.endswith("/status"))


def test_publish_job_retryable_error(monkeypatch):
    monkeypatch.setattr(settings, "API_BASE_URL", "http://api")
    monkeypatch.setattr(settings, "API_AUTH_TOKEN", "local-admin")
    monkeypatch.setattr(settings, "JOB_TIMEOUT_SEC", 1)
    monkeypatch.setattr(settings, "HEARTBEAT_INTERVAL_SEC", 0.01)

    calls = []

    def fake_get(url, params=None, timeout=0, headers=None):
        if url.endswith("/publish-jobs"):
            return Resp(data=[{"id": 3, "platform": "instagram"}])
        if url.endswith("/context"):
            return Resp(
                data={
                    "publish_job": {"id": 3},
                    "release": {"id": 12, "story_id": 22, "platform": "instagram"},
                    "artifact": {"video_path": "/output/video.mp4"},
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
        "publish_release",
        lambda context, session=None: (_ for _ in ()).throw(PublishPipelineError("retry later", retryable=True)),
    )

    job = poller.poll_jobs()[0]
    poller.process_job(job)

    assert any((json or {}).get("retryable") is True for _url, json in calls if _url.endswith("/status"))
