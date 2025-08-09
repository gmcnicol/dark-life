from __future__ import annotations

"""Utilities for normalizing and filtering Reddit posts.

The normalizer enforces project-wide content filters and prepares the body for
hashing and storage. Filters are driven by environment variables:

``LANG_ALLOW``       ISO language code expected for posts.
``ALLOW_NSFW``       When ``true`` NSFW posts are accepted.
``MIN_BODY_CHARS``   Minimum allowed characters in post body.
``MAX_BODY_CHARS``   Maximum allowed characters in post body.
"""

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from langdetect import detect, LangDetectException


# ---------------------------------------------------------------------------
# Configuration & Result Types
# ---------------------------------------------------------------------------


@dataclass
class NormalizationConfig:
    """Configuration values sourced from environment variables."""

    lang_allow: str = os.getenv("LANG_ALLOW", "en")
    allow_nsfw: bool = os.getenv("ALLOW_NSFW", "false").lower() == "true"
    min_body_chars: int = int(os.getenv("MIN_BODY_CHARS", "300"))
    max_body_chars: int = int(os.getenv("MAX_BODY_CHARS", "3500"))


@dataclass
class NormalizedPost:
    """Post representation after normalization."""

    title: str
    body: str
    language: str
    nsfw: bool
    hash_title_body: str


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def normalize_markdown(text: str) -> str:
    """Normalize markdown content.

    Steps:
    - Trim leading and trailing whitespace.
    - Remove common boilerplate lines (e.g. "Edit:" or "TL;DR").
    - Collapse all consecutive whitespace into a single space.
    """

    text = text.strip()

    boilerplate_patterns = [
        r"(?im)^\s*edit:.*$",
        r"(?im)^\s*tl;dr:.*$",
    ]
    for pattern in boilerplate_patterns:
        text = re.sub(pattern, "", text)

    # Collapse whitespace (including newlines) to single spaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_post(
    post: Dict[str, Any], config: NormalizationConfig | None = None
) -> Tuple[Optional[NormalizedPost], Optional[str]]:
    """Normalize a Reddit post and apply project filters.

    Parameters
    ----------
    post:
        Raw post dictionary from Reddit's API.
    config:
        Optional configuration override. If omitted, values are loaded from
        environment variables.

    Returns
    -------
    normalized:
        ``NormalizedPost`` when all filters pass, otherwise ``None``.
    reason:
        ``None`` when accepted or a string describing why the post was
        rejected.
    """

    cfg = config or NormalizationConfig()

    title = (post.get("title") or "").strip()
    body_raw = post.get("selftext") or ""
    nsfw = bool(post.get("over_18") or post.get("nsfw"))

    if nsfw and not cfg.allow_nsfw:
        return None, "nsfw"

    body = normalize_markdown(body_raw)
    body_len = len(body)
    if body_len < cfg.min_body_chars:
        return None, "too_short"
    if body_len > cfg.max_body_chars:
        return None, "too_long"

    try:
        language = detect(f"{title} {body}")
    except LangDetectException:
        return None, "lang_unknown"
    if language != cfg.lang_allow:
        return None, f"lang_{language}"

    hash_title_body = hashlib.sha256((title + body).encode("utf-8")).hexdigest()

    normalized = NormalizedPost(
        title=title,
        body=body,
        language=language,
        nsfw=nsfw,
        hash_title_body=hash_title_body,
    )
    return normalized, None


__all__ = [
    "NormalizationConfig",
    "NormalizedPost",
    "normalize_markdown",
    "normalize_post",
]
