import os

os.environ["METRICS_ENABLED"] = "false"

from apps.api import reddit_admin
from services.reddit_ingestor import cli
from shared.config import (
    DEFAULT_REDDIT_SUBREDDITS,
    DEFAULT_REDDIT_SUBREDDITS_CSV,
    settings,
)


def test_default_subreddit_order_is_authoritative() -> None:
    settings.REDDIT_DEFAULT_SUBREDDITS = DEFAULT_REDDIT_SUBREDDITS_CSV

    expected = list(DEFAULT_REDDIT_SUBREDDITS)
    assert cli._default_subreddits() == expected
    assert reddit_admin._default_subreddits() == expected


def test_default_subreddits_trim_whitespace() -> None:
    settings.REDDIT_DEFAULT_SUBREDDITS = "Odd_directions, shortscarystories , nosleep"

    assert cli._default_subreddits() == [
        "Odd_directions",
        "shortscarystories",
        "nosleep",
    ]
