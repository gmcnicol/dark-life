from __future__ import annotations

"""Helpers for extracting media information from Reddit posts."""

from html import unescape
from typing import Any, Dict, List
from urllib.parse import urlparse


def _add_url(urls: List[str], url: str | None) -> None:
    if not url:
        return
    parsed = urlparse(url)
    if parsed.netloc.endswith("redd.it"):
        clean = unescape(url)
        if clean not in urls:
            urls.append(clean)


def extract_image_urls(post: Dict[str, Any]) -> List[str]:
    """Return list of Reddit-hosted image URLs from ``post``."""

    urls: List[str] = []
    preview = post.get("preview", {})
    for image in preview.get("images", []):
        _add_url(urls, image.get("source", {}).get("url"))
        for res in image.get("resolutions", []):
            _add_url(urls, res.get("url"))

    media_metadata = post.get("media_metadata", {})
    for item in media_metadata.values():
        _add_url(urls, item.get("s", {}).get("u"))
        for res in item.get("p", []):
            _add_url(urls, res.get("u"))

    _add_url(urls, post.get("url"))
    return urls


__all__ = ["extract_image_urls"]
