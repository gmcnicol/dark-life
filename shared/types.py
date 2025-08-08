"""Shared data types for the dark-life monorepo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class RenderJob:
    """Information required to render a video."""

    story_path: Path
    image_paths: List[Path]


@dataclass
class StoryMetadata:
    """Metadata extracted from story front matter."""

    title: str
    subreddit: str
    url: str
    created_utc: int
