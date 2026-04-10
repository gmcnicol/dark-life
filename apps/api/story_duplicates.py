from __future__ import annotations

import re

from sqlmodel import Session, select

from .models import Story

WHITESPACE_RE = re.compile(r"\s+")


def _canonical_text(value: str | None) -> str:
    return WHITESPACE_RE.sub(" ", value or "").strip().casefold()


def story_duplicate_key(*, title: str | None, author: str | None, body_md: str | None) -> tuple[str, str, str]:
    return (
        _canonical_text(title),
        _canonical_text(author),
        _canonical_text(body_md),
    )


def find_duplicate_story(
    session: Session,
    *,
    title: str | None,
    author: str | None,
    body_md: str | None,
    exclude_story_id: int | None = None,
) -> Story | None:
    requested_key = story_duplicate_key(title=title, author=author, body_md=body_md)
    for story in session.exec(select(Story)).all():
        if exclude_story_id is not None and story.id == exclude_story_id:
            continue
        story_key = story_duplicate_key(
            title=story.title,
            author=story.author,
            body_md=story.body_md,
        )
        if story_key == requested_key:
            return story
    return None
