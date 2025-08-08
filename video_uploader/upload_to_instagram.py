"""Placeholder Instagram uploader using instagrapi."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:  # Optional dependency
    from instagrapi import Client  # type: ignore
except Exception:  # pragma: no cover
    Client = None  # type: ignore


def upload(video: Path, caption: str, username: str, password: str) -> None:
    if Client is None:
        print("instagrapi not installed; skipping upload")
        return
    cl = Client()
    cl.login(username, password)
    cl.video_upload(str(video), caption)
