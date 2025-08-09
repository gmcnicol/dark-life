"""Reddit API client for fetching posts.

Provides utilities for incremental updates using the ``after``
parameter and time window based backfills using Reddit's search
endpoint. Configuration is driven by environment variables:

``REDDIT_SUBREDDITS``      Comma separated list of subreddits.
``REDDIT_USER_AGENT``      User agent for requests.
``REQUESTS_PER_MINUTE``    Rate limiting for API calls.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


@dataclass
class RedditConfig:
    """Configuration for the Reddit client loaded from environment variables."""

    subreddits: List[str] = field(
        default_factory=lambda: [s.strip() for s in os.getenv("REDDIT_SUBREDDITS", "").split(",") if s.strip()]
    )
    user_agent: str = os.getenv("REDDIT_USER_AGENT", "dark-life-ingestor/1.0")
    requests_per_minute: int = int(os.getenv("REQUESTS_PER_MINUTE", "60"))


class RateLimiter:
    """Simple rate limiter based on requests per minute."""

    def __init__(self, requests_per_minute: int) -> None:
        self.min_interval = 60.0 / max(requests_per_minute, 1)
        self.last_time = 0.0

    def wait(self) -> None:
        now = time.time()
        elapsed = now - self.last_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_time = time.time()


class RedditClient:
    """Light-weight Reddit client for fetching posts."""

    BASE_URL = "https://www.reddit.com"

    def __init__(self, config: RedditConfig | None = None) -> None:
        self.config = config or RedditConfig()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.config.user_agent})
        self._rate_limiter = RateLimiter(self.config.requests_per_minute)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _request(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        backoff = 1.0
        while True:
            self._rate_limiter.wait()
            try:
                resp = self._session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:  # pragma: no cover - network failure
                logger.warning("Reddit API request failed: %s; retrying in %.1f s", exc, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 64)  # exponential backoff with cap

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_new_posts(
        self, subreddit: str, *, after: Optional[str] = None, limit: int = 100
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetch posts from a subreddit's ``new`` listing.

        Parameters
        ----------
        subreddit:
            Name of the subreddit to fetch from.
        after:
            Fullname of the last seen post. When provided, only posts after this
            ID are returned, enabling incremental updates.
        limit:
            Maximum number of posts to return (Reddit caps this at 100).

        Returns
        -------
        posts:
            List of post payload dictionaries.
        next_after:
            The ``fullname`` to use for the next page or ``None`` if at end.
        """

        url = f"{self.BASE_URL}/r/{subreddit}/new.json"
        params: Dict[str, Any] = {"limit": limit}
        if after:
            params["after"] = after
        data = self._request(url, params)
        children = data.get("data", {}).get("children", [])
        posts = [child.get("data", {}) for child in children]
        next_after = data.get("data", {}).get("after")
        return posts, next_after

    def fetch_posts_by_time_window(
        self,
        subreddit: str,
        start_utc: int,
        end_utc: int,
        *,
        limit: int = 100,
        after: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetch posts for a subreddit within a time window.

        Uses Reddit's search API with a ``timestamp`` range to perform a
        backfill for historical posts.
        """

        url = f"{self.BASE_URL}/r/{subreddit}/search.json"
        query = f"timestamp:{int(start_utc)}..{int(end_utc)}"
        params: Dict[str, Any] = {
            "q": query,
            "restrict_sr": "on",
            "sort": "new",
            "syntax": "cloudsearch",
            "limit": limit,
        }
        if after:
            params["after"] = after
        data = self._request(url, params)
        children = data.get("data", {}).get("children", [])
        posts = [child.get("data", {}) for child in children]
        next_after = data.get("data", {}).get("after")
        return posts, next_after


__all__ = ["RedditClient", "RedditConfig"]
