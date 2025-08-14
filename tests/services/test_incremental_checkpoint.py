from datetime import datetime, timezone

import pytest

from services.reddit_ingestor import incremental


class DummyClient:
    def __init__(self, posts):
        self.posts = posts

    def fetch_new_posts(self, subreddit, after=None, limit=100):
        return self.posts, None


class Normalized:
    def __init__(self, title, body):
        self.title = title
        self.body = body
        self.language = "en"
        self.nsfw = False
        self.hash_title_body = "h"


def make_post(pid, created):
    return {
        "id": pid,
        "name": f"t3_{pid}",
        "title": pid,
        "selftext": "body",
        "created_utc": created,
        "ups": 1,
        "num_comments": 0,
        "author": "a",
        "is_self": True,
        "url": "",
    }


def test_fetch_incremental_checkpoint(monkeypatch):
    state = {"fullname": None, "created": None}

    def fake_load(sub):
        return state["fullname"], state["created"]

    def fake_update(sub, fullname, created):
        state["fullname"] = fullname
        state["created"] = created

    inserted = []

    def fake_insert(payload):
        inserted.append(payload["reddit_id"])
        return True

    monkeypatch.setattr(incremental, "_load_fetch_state", fake_load)
    monkeypatch.setattr(incremental, "_update_fetch_state", fake_update)
    monkeypatch.setattr(incremental, "insert_post", fake_insert)
    monkeypatch.setattr(incremental, "normalize_post", lambda p: (Normalized(p["title"], p["selftext"]), None))
    monkeypatch.setattr(incremental, "extract_image_urls", lambda p: [])
    monkeypatch.setattr(incremental, "push_new_story", lambda p: None)
    monkeypatch.setattr(incremental.time, "sleep", lambda s: None)

    now = int(datetime.now(tz=timezone.utc).timestamp())
    posts1 = [make_post("p2", now), make_post("p1", now - 1)]
    client1 = DummyClient(posts1)
    incremental.fetch_incremental("test", client=client1)
    assert inserted == ["t3_p2", "t3_p1"]

    posts2 = [make_post("p3", now + 1), make_post("p2", now)]
    client2 = DummyClient(posts2)
    incremental.fetch_incremental("test", client=client2)
    assert inserted == ["t3_p2", "t3_p1", "t3_p3"]
