# Task 01: Fetch Reddit Stories

## Goal
Create a Python script `scripts/fetch_reddit.py` that fetches the top N stories from subreddits like `r/nosleep`, `r/confession`, and `r/TrueOffMyChest`.

## Requirements
- Use Reddit API via `praw` or requests if no API key available
- Save stories as Markdown files in `content/stories/`, e.g., `2025-08-07_story01.md`
- Filter out:
  - NSFW content
  - Posts under 300 characters or above 2000
  - Downvoted/controversial posts

## Output Example

```md
---
title: "I heard footsteps in the attic. I live alone."
subreddit: "r/nosleep"
url: "https://reddit.com/..."
created_utc: 1723460000
---

It was a quiet night, until I heard a sound I couldn't explain...
```
