#!/usr/bin/env python3
"""
Quick sanity check for Reddit API credentials and ingestion.
Run inside the reddit_ingestor container, e.g.:

docker compose -f infra/docker-compose.yml --profile ops run --rm reddit_ingestor \
    python services/reddit_ingestor/ingest_sanity.py nosleep 5
"""
import os
import sys
import praw
import datetime as dt

def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest_sanity.py <subreddit> [limit]")
        sys.exit(1)

    subreddit_name = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "darklife-sanity/1.0")

    if not client_id or not client_secret:
        print("ERROR: Missing REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET in environment")
        sys.exit(1)

    print(f"Connecting to Reddit API for subreddit '{subreddit_name}' (limit={limit})...")
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )

    try:
        posts = list(reddit.subreddit(subreddit_name).new(limit=limit))
    except Exception as e:
        print(f"ERROR: Could not fetch posts: {e}")
        sys.exit(1)

    print(f"✅ Retrieved {len(posts)} posts from r/{subreddit_name}:\n")
    for post in posts:
        created_str = dt.datetime.utcfromtimestamp(post.created_utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{created_str} UTC] ↑{post.score} 💬{post.num_comments} :: {post.title[:80]}")

    print("\nDone.")

if __name__ == "__main__":
    main()
