"""Fetch top Reddit stories and save them as Markdown files."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import typer
import requests

try:
    import praw
except ImportError:  # pragma: no cover - praw optional
    praw = None

app = typer.Typer(add_completion=False)


def _save_markdown(post: Dict, output_dir: Path, index: int) -> Path:
    date_str = datetime.utcfromtimestamp(post["created_utc"]).strftime("%Y-%m-%d")
    filename = f"{date_str}_story{index:02d}.md"
    path = output_dir / filename
    front_matter = (
        "---\n"
        f"title: \"{post['title'].replace('\\', '').replace('"', '\\"')}\"\n"
        f"subreddit: \"{post['subreddit']}\"\n"
        f"url: \"https://reddit.com{post['permalink']}\"\n"
        f"created_utc: {int(post['created_utc'])}\n"
        "---\n\n"
    )
    content = post.get("selftext", "").strip()
    path.write_text(front_matter + content)
    return path


def _fetch_via_requests(subreddit: str, limit: int) -> List[Dict]:
    url = f"https://www.reddit.com/r/{subreddit}/top.json?limit={limit}"
    headers = {"User-Agent": "dark-life-script"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return [child["data"] for child in data["data"]["children"]]


def _fetch_via_praw(reddit: "praw.Reddit", subreddit: str, limit: int) -> List[Dict]:
    posts = []
    for submission in reddit.subreddit(subreddit).top(limit=limit):
        posts.append(
            {
                "title": submission.title,
                "subreddit": submission.subreddit.display_name,
                "selftext": submission.selftext,
                "permalink": submission.permalink,
                "created_utc": submission.created_utc,
                "score": submission.score,
                "over_18": submission.over_18,
                "upvote_ratio": getattr(submission, "upvote_ratio", 1.0),
            }
        )
    return posts


def _filter_posts(posts: List[Dict]) -> List[Dict]:
    filtered = []
    for p in posts:
        text_len = len(p.get("selftext", ""))
        if p.get("over_18"):
            continue
        if text_len < 300 or text_len > 2000:
            continue
        if p.get("score", 0) <= 0 or p.get("upvote_ratio", 0.0) < 0.5:
            continue
        filtered.append(p)
    return filtered


@app.command()
def main(
    subreddits: List[str] = typer.Option(
        ["nosleep", "confession", "TrueOffMyChest"],
        help="Subreddits to pull from",
    ),
    limit: int = typer.Option(5, help="Number of posts per subreddit"),
    output_dir: Path = typer.Option(Path("content/stories"), help="Where to save stories"),
) -> None:
    """Fetch stories and write them as markdown files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    use_praw = praw is not None and all(
        os.getenv(var) for var in ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]
    )
    reddit = None
    if use_praw:
        reddit = praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT", "dark-life-script"),
        )
    index = 1
    for subreddit in subreddits:
        if use_praw:
            posts = _fetch_via_praw(reddit, subreddit, limit)
        else:
            posts = _fetch_via_requests(subreddit, limit)
        for post in _filter_posts(posts):
            _save_markdown(post, output_dir, index)
            index += 1


if __name__ == "__main__":  # pragma: no cover
    app()
