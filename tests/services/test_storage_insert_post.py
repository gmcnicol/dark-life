from datetime import datetime, timezone

import pytest

from services.reddit_ingestor.storage import insert_post
from shared.config import settings


def test_insert_post_sends_payload(monkeypatch: pytest.MonkeyPatch):
    settings.API_BASE_URL = "http://api"
    settings.API_AUTH_TOKEN = "token"

    captured = {}

    class Resp:
        status_code = 201

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return Resp()

    monkeypatch.setattr("services.reddit_ingestor.storage.requests.post", fake_post)

    payload = {
        "reddit_id": "t3_123",
        "title": "Hello",
        "author": "alice",
        "created_utc": datetime.fromtimestamp(0, tz=timezone.utc),
        "selftext": "body",
        "url": "http://example.com",
        "nsfw": False,
    }

    assert insert_post(payload) is True
    assert captured["url"] == "http://api/admin/stories"
    assert captured["json"]["external_id"] == "t3_123"
    assert captured["json"]["created_utc"] == 0
    assert captured["headers"]["Authorization"] == "Bearer token"
