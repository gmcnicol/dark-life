import os
import logging
import hashlib
import re
from typing import Optional, Dict, Any

log = logging.getLogger(__name__)


def normalize_and_filter(post) -> Optional[Dict[str, Any]]:
    title = (post.title or "").strip()
    is_self = bool(getattr(post, "is_self", False))
    body = (post.selftext or "") if is_self else ""
    upvotes = int(getattr(post, "score", 0))
    nsfw = bool(getattr(post, "over_18", False))
    lang = "en"

    if not title and not body:
        log.debug("reject: empty content id=%s", getattr(post, "id", "?"))
        return None
    if nsfw and os.getenv("ALLOW_NSFW", "false").lower() != "true":
        log.debug("reject: nsfw id=%s", getattr(post, "id", "?"))
        return None

    min_chars = int(os.getenv("MIN_BODY_CHARS", "300"))
    max_chars = int(os.getenv("MAX_BODY_CHARS", "3500"))
    if len(body) < min_chars:
        log.debug("reject: too_short id=%s len=%s", getattr(post, "id", "?"), len(body))
        return None
    if len(body) > max_chars:
        log.debug("reject: too_long id=%s len=%s", getattr(post, "id", "?"), len(body))
        return None

    min_up = int(os.getenv("REDDIT_MIN_UPVOTES", "0"))
    if upvotes < min_up:
        log.debug(
            "reject: low_upvotes id=%s score=%s", getattr(post, "id", "?"), upvotes
        )
        return None

    norm_t = re.sub(r"\s+", " ", title).strip().lower()
    norm_b = re.sub(r"\s+", " ", body).strip().lower()
    h = hashlib.sha256((norm_t + "\n" + norm_b).encode("utf-8")).hexdigest()

    doc = {
        "reddit_id": f"t3_{post.id}",
        "subreddit": str(post.subreddit),
        "title": title,
        "author": str(getattr(post, "author", "")),
        "url": f"https://www.reddit.com{post.permalink}",
        "is_self": is_self,
        "selftext": body,
        "created_utc": int(getattr(post, "created_utc", 0)),
        "nsfw": nsfw,
        "language": lang,
        "upvotes": upvotes,
        "num_comments": int(getattr(post, "num_comments", 0)),
        "hash_title_body": h,
    }

    if os.getenv("DEBUG_INGEST_SAMPLE", "false").lower() == "true":
        log.info("SAMPLE keep: %s", title[:80])

    return doc
