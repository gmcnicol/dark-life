from datetime import datetime, timezone
from sqlalchemy import text


def test_normalization_filters(ingestor_env, monkeypatch):
    normalizer = ingestor_env.normalizer
    config = normalizer.NormalizationConfig(
        lang_allow="en", allow_nsfw=False, min_body_chars=5, max_body_chars=1000
    )

    # NSFW rejection
    post = {"title": "t", "selftext": "hello" * 2, "over_18": True}
    normalized, reason = normalizer.normalize_post(post, config)
    assert normalized is None and reason == "nsfw"

    # Too short rejection
    post = {"title": "t", "selftext": "hi"}
    normalized, reason = normalizer.normalize_post(post, config)
    assert normalized is None and reason == "too_short"

    # Language mismatch
    monkeypatch.setattr(normalizer, "detect", lambda text: "fr")
    post = {"title": "bonjour", "selftext": "bonjour " * 3}
    normalized, reason = normalizer.normalize_post(post, config)
    assert normalized is None and reason == "lang_fr"

    # Normalization of boilerplate and whitespace
    monkeypatch.setattr(normalizer, "detect", lambda text: "en")
    post = {"title": "A", "selftext": "Edit: ignore\nLine1\n\nLine2"}
    normalized, reason = normalizer.normalize_post(post, config)
    assert normalized.body == "Line1 Line2" and reason is None


def test_insert_post_deduplication(ingestor_env):
    storage = ingestor_env.storage
    session = storage.SessionLocal()
    payload = {
        "reddit_id": "t3_1",
        "subreddit": "testsub",
        "title": "Title 1",
        "author": "user",
        "url": "http://example.com/1",
        "created_utc": datetime.now(timezone.utc),
        "is_self": True,
        "selftext": "body1",
        "nsfw": False,
        "language": "en",
        "upvotes": 1,
        "num_comments": 0,
        "hash_title_body": "hash1",
    }
    assert storage.insert_post(session, payload) is True
    assert storage.insert_post(session, payload) is False

    payload2 = dict(payload, reddit_id="t3_2")
    assert storage.insert_post(session, payload2) is False

    payload3 = dict(payload, reddit_id="t3_3", hash_title_body="hash3")
    assert storage.insert_post(session, payload3) is True
    session.close()


def test_backfill_flow(ingestor_env, monkeypatch):
    storage = ingestor_env.storage
    backfill = ingestor_env.backfill
    normalizer = ingestor_env.normalizer
    monkeypatch.setattr(normalizer, "detect", lambda text: "en")

    class FakeClient:
        def fetch_posts_by_time_window(self, subreddit, start_utc, end_utc, limit=100):
            posts = [
                {
                    "id": "1",
                    "name": "t3_1",
                    "title": "Post1",
                    "selftext": "body one " * 5,
                    "url": "http://x/1",
                    "author": "a",
                    "created_utc": start_utc + 10,
                    "over_18": False,
                },
                {
                    "id": "2",
                    "name": "t3_2",
                    "title": "Post2",
                    "selftext": "body two " * 5,
                    "url": "http://x/2",
                    "author": "b",
                    "created_utc": start_utc + 20,
                    "over_18": False,
                },
            ]
            return posts, None

    inserted, earliest = backfill.backfill_by_window("testsub", 0, 100, client=FakeClient())
    assert inserted == 2 and earliest is not None

    with storage.engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM reddit_posts")).scalar()
    assert count == 2


def test_incremental_idempotency(ingestor_env, monkeypatch):
    incremental = ingestor_env.incremental
    normalizer = ingestor_env.normalizer
    monkeypatch.setattr(normalizer, "detect", lambda text: "en")

    class FakeClient:
        def fetch_new_posts(self, subreddit, after=None, limit=100):
            posts = [
                {
                    "id": "new",
                    "name": "t3_new",
                    "title": "New",
                    "selftext": "body new " * 5,
                    "url": "http://x/new",
                    "author": "a",
                    "created_utc": 200,
                },
                {
                    "id": "old",
                    "name": "t3_old",
                    "title": "Old",
                    "selftext": "body old " * 5,
                    "url": "http://x/old",
                    "author": "b",
                    "created_utc": 100,
                },
            ]
            return posts, None

    client = FakeClient()
    first = incremental.fetch_incremental("testsub", client=client)
    second = incremental.fetch_incremental("testsub", client=client)
    assert first == 2 and second == 0
