"""Shared configuration constants."""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "content"
STORIES_DIR = CONTENT_DIR / "stories"
AUDIO_DIR = CONTENT_DIR / "audio"
VISUALS_DIR = CONTENT_DIR / "visuals"
OUTPUT_DIR = BASE_DIR / "output"
VIDEO_OUTPUT_DIR = OUTPUT_DIR / "videos"
MANIFEST_DIR = OUTPUT_DIR / "manifest"
RENDER_QUEUE_DIR = BASE_DIR / "render_queue"
