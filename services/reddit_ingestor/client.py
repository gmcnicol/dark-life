import logging
from typing import Iterable, List, Dict, Any, Optional
import praw

from shared.config import settings


log = logging.getLogger(__name__)


class RedditClient:
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Create a PRAW Reddit client using env defaults when not provided."""

        client_id = client_id or settings.REDDIT_CLIENT_ID
        client_secret = client_secret or settings.REDDIT_CLIENT_SECRET
        user_agent = user_agent or settings.REDDIT_USER_AGENT

        if not all([client_id, client_secret, user_agent]):
            raise ValueError("Reddit API credentials are required")

        self._r = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )

    def list_new(self, subreddit: str, limit: Optional[int] = None) -> Iterable:
        """Yield new submissions, letting PRAW handle pagination."""
        sub = self._r.subreddit(subreddit)
        for post in sub.new(limit=limit):
            yield post

    def search_between(self, subreddit: str, start_ts: int, end_ts: int) -> List:
        """Best-effort cloudsearch between timestamps; returns possibly empty list."""
        sub = self._r.subreddit(subreddit)
        query = f"timestamp:{start_ts}..{end_ts}"
        try:
            results = list(
                sub.search(
                    query=query,
                    sort="new",
                    time_filter="all",
                    syntax="cloudsearch",
                    limit=None,
                )
            )
            log.info(
                "cloudsearch %s [%s..%s] -> %d",
                subreddit,
                start_ts,
                end_ts,
                len(results),
            )
            return results
        except Exception as e:
            log.warning(
                "cloudsearch failed %s [%s..%s]: %s",
                subreddit,
                start_ts,
                end_ts,
                e,
            )
            return []

    # ------------------------------------------------------------------
    # Legacy wrappers returning dictionaries (used by older helpers/tests)
    # ------------------------------------------------------------------
    def _to_dict(self, post) -> Dict[str, Any]:
        return {
            "id": post.id,
            "name": f"t3_{post.id}",
            "title": post.title,
            "selftext": post.selftext if getattr(post, "is_self", False) else "",
            "url": getattr(post, "url", ""),
            "author": str(getattr(post, "author", "") or ""),
            "created_utc": int(getattr(post, "created_utc", 0)),
            "over_18": bool(getattr(post, "over_18", False)),
        }

    def fetch_new_posts(
        self, subreddit: str, *, after: Optional[str] = None, limit: int = 100
    ) -> tuple[list[Dict[str, Any]], Optional[str]]:
        posts: list[Dict[str, Any]] = []
        next_after: Optional[str] = None
        for post in self.list_new(subreddit, limit=None):
            fullname = f"t3_{post.id}"
            if after and fullname == after:
                break
            posts.append(self._to_dict(post))
            if len(posts) >= limit:
                next_after = fullname
                break
        return posts, next_after

    def fetch_posts_by_time_window(
        self,
        subreddit: str,
        start_utc: int,
        end_utc: int,
        *,
        limit: int = 100,
        after: Optional[str] = None,
    ) -> tuple[list[Dict[str, Any]], Optional[str]]:
        posts = [
            self._to_dict(p)
            for p in self.search_between(subreddit, start_utc, end_utc)
        ]
        posts.sort(key=lambda p: p.get("created_utc", 0), reverse=True)
        return posts[:limit], None


__all__ = ["RedditClient"]
