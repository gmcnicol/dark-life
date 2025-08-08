"""Placeholder TikTok uploader."""

from __future__ import annotations

from pathlib import Path

try:  # Optional dependency
    import pywhatkit  # type: ignore
except Exception:  # pragma: no cover
    pywhatkit = None  # type: ignore


def upload(video: Path, caption: str) -> None:
    if pywhatkit is None:
        print("pywhatkit not installed; skipping upload")
        return
    # Real implementation would use pywhatkit or TikTok API.
    print(f"Uploading {video} to TikTok with caption: {caption}")
