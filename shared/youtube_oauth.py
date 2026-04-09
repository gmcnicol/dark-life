"""Shared YouTube OAuth scopes used by publishing and insights services."""

from __future__ import annotations

# Publishing requires upload access. Insights also call the Data API for
# channel/video reads and the Analytics API for report queries.
YOUTUBE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

