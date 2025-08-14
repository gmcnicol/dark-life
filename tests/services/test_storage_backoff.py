import pytest

from services.reddit_ingestor.storage import insert_post
from shared.config import settings


def _payload():
    return {
        "reddit_id": "t3_123",
        "title": "Hello",
        "author": "alice",
        "created_utc": 0,
        "selftext": "body",
        "url": "http://example.com",
        "nsfw": False,
    }


def test_insert_post_retries_on_429(monkeypatch):
    settings.API_BASE_URL = "http://api"
    settings.API_AUTH_TOKEN = "token"

    calls = []

    class Resp:
        def __init__(self, status, headers=None):
            self.status_code = status
            self.headers = headers or {}

    responses = iter([
        Resp(429, {"Retry-After": "1"}),
        Resp(201),
    ])

    def fake_post(url, json, headers, timeout):
        calls.append(url)
        return next(responses)

    sleep_calls = []
    monkeypatch.setattr(
        "services.reddit_ingestor.storage.requests.post", fake_post
    )
    monkeypatch.setattr(
        "services.reddit_ingestor.storage.time.sleep", lambda s: sleep_calls.append(s)
    )

    assert insert_post(_payload()) is True
    assert sleep_calls == [1.0]
    assert len(calls) == 2


def test_insert_post_retries_on_500(monkeypatch):
    settings.API_BASE_URL = "http://api"
    settings.API_AUTH_TOKEN = "token"

    class Resp:
        def __init__(self, status):
            self.status_code = status
            self.headers = {}

    responses = iter([Resp(500), Resp(201)])

    def fake_post(url, json, headers, timeout):
        return next(responses)

    sleep_calls = []
    monkeypatch.setattr(
        "services.reddit_ingestor.storage.requests.post", fake_post
    )
    monkeypatch.setattr(
        "services.reddit_ingestor.storage.random.uniform", lambda a, b: 0
    )
    monkeypatch.setattr(
        "services.reddit_ingestor.storage.time.sleep", lambda s: sleep_calls.append(s)
    )

    assert insert_post(_payload()) is True
    assert sleep_calls == [1]
