"""Stories API router."""

from __future__ import annotations

from datetime import datetime
import os
import re
from typing import Iterable, Any

import requests
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlmodel import Session, select, SQLModel

from .db import get_session
from .models import (
    Asset,
    AssetRead,
    AssetUpdate,
    StoryPart,
    StoryPartRead,
    Story,
    StoryCreate,
    StoryRead,
    StoryUpdate,
    Job,
)

router = APIRouter(prefix="/stories", tags=["stories"])


# Domain-specific keywords for image search
KEYWORDS = [
    "cabin",
    "forest",
    "fog",
    "attic",
    "window",
    "shadow",
    "alley",
    "night",
    "mist",
    "abandoned",
]
KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in KEYWORDS) + r")\b", re.IGNORECASE
)

WORDS_PER_MINUTE = 160
WORDS_PER_SECOND = WORDS_PER_MINUTE / 60
CHARS_PER_WORD = 5
CHARS_PER_SECOND = WORDS_PER_SECOND * CHARS_PER_WORD

MIN_PART_SECONDS = 30
MAX_PART_SECONDS = 75


def _estimate_seconds(text: str) -> int:
    """Estimate duration in seconds from character length."""
    return max(1, int(round(len(text) / CHARS_PER_SECOND)))


SENTENCE_RE = re.compile(r"[^.!?]+[.!?](?:\s+|$)")


def _sentence_spans(text: str) -> list[tuple[str, int, int]]:
    """Return list of (sentence, start, end) for the given text."""
    spans: list[tuple[str, int, int]] = []
    for match in SENTENCE_RE.finditer(text):
        spans.append((match.group().strip(), match.start(), match.end()))
    if spans and spans[-1][2] < len(text):
        # trailing text without terminal punctuation
        spans.append((text[spans[-1][2]:].strip(), spans[-1][2], len(text)))
    elif not spans:
        spans.append((text.strip(), 0, len(text)))
    return spans


def _snap_boundaries(text: str, start: int, end: int) -> tuple[int, int]:
    """Snap start/end to nearest sentence boundaries."""
    sentences = _sentence_spans(text)
    for _, s, e in sentences:
        if s <= start < e:
            start = s
        if s < end <= e:
            end = e
    if start >= end:
        raise ValueError("Invalid boundaries")
    end = min(end, len(text))
    # trim trailing whitespace from end boundary
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _build_parts(body: str, target_seconds: int) -> list[tuple[int, int]]:
    """Split body into (start, end) parts honoring duration bounds."""
    spans = _sentence_spans(body)
    target_chars = target_seconds * CHARS_PER_SECOND
    max_chars = MAX_PART_SECONDS * CHARS_PER_SECOND
    parts: list[tuple[int, int]] = []
    current_start = spans[0][1]
    current_end = spans[0][2]
    current_chars = current_end - current_start
    for sent, s, e in spans[1:]:
        sent_chars = e - s
        projected = current_chars + sent_chars
        if current_chars and (projected > target_chars or projected > max_chars):
            parts.append((current_start, current_end))
            current_start = s
            current_chars = sent_chars
        else:
            current_chars = projected
        current_end = e
    parts.append((current_start, current_end))
    # merge last part if too short
    if len(parts) > 1:
        start, end = parts[-1]
        if _estimate_seconds(body[start:end]) < MIN_PART_SECONDS:
            prev_start, _ = parts[-2]
            parts[-2] = (prev_start, end)
            parts.pop()
    # validate bounds
    for start, end in parts:
        secs = _estimate_seconds(body[start:end])
        if secs < MIN_PART_SECONDS or secs > MAX_PART_SECONDS:
            raise HTTPException(status_code=400, detail="Part duration out of bounds")
    return parts


class PartBounds(SQLModel):
    start_char: int
    end_char: int


class PartPreview(SQLModel):
    index: int
    body_md: str
    est_seconds: int
    start_char: int
    end_char: int


def _extract_keywords(story: Story) -> str:
    """Return matched domain keywords from a story title/body."""
    text = f"{story.title} {story.body_md or ''}".lower()
    matches = KEYWORD_RE.findall(text)
    # remove duplicates while preserving order
    keywords = list(dict.fromkeys(matches))
    return " ".join(keywords)


def _fetch_pexels(keywords: str) -> Iterable[dict[str, str]]:
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return []
    try:
        res = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": keywords, "per_page": 8},
            headers={"Authorization": api_key},
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        for photo in data.get("photos", []):
            yield {
                "remote_url": photo.get("src", {}).get("medium"),
                "provider": "pexels",
                "provider_id": str(photo.get("id")),
            }
    except Exception:  # pragma: no cover - network failures ignored
        return []


def _fetch_pixabay(keywords: str) -> Iterable[dict[str, str]]:
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
        return []
    try:
        res = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": api_key,
                "q": keywords,
                "image_type": "photo",
                "per_page": 8,
            },
            timeout=10,
        )
        res.raise_for_status()
        data = res.json()
        for hit in data.get("hits", []):
            yield {
                "remote_url": hit.get("webformatURL"),
                "provider": "pixabay",
                "provider_id": str(hit.get("id")),
            }
    except Exception:  # pragma: no cover - network failures ignored
        return []


@router.get("/", response_model=list[StoryRead])
def list_stories(
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> list[StoryRead]:
    """Return stories filtered by status/query with pagination."""
    query = select(Story)
    if status:
        query = query.where(Story.status == status)
    if q:
        query = query.where(Story.title.ilike(f"%{q}%"))
    query = query.offset((page - 1) * limit).limit(limit)
    return session.exec(query).all()


@router.get("/{story_id}", response_model=StoryRead)
def get_story(story_id: int, session: Session = Depends(get_session)) -> StoryRead:
    """Return a story by ID."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


@router.post("/", response_model=StoryRead, status_code=status.HTTP_201_CREATED)
def create_story(
    story_in: StoryCreate, session: Session = Depends(get_session)
) -> StoryRead:
    """Create a new story."""
    story = Story(**story_in.model_dump())
    session.add(story)
    session.commit()
    session.refresh(story)
    return story


@router.patch("/{story_id}", response_model=StoryRead)
def update_story(
    story_id: int, story_in: StoryUpdate, session: Session = Depends(get_session)
) -> StoryRead:
    """Update an existing story."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    data = story_in.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(story, key, value)
    story.updated_at = datetime.utcnow()
    session.add(story)
    session.commit()
    session.refresh(story)
    return story


@router.delete("/{story_id}")
def delete_story(story_id: int, session: Session = Depends(get_session)) -> Response:
    """Delete a story."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    session.delete(story)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{story_id}/fetch-images", response_model=list[AssetRead])
def fetch_images(
    story_id: int, session: Session = Depends(get_session)
) -> list[AssetRead]:
    """Fetch images for a story using external providers."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    keywords = _extract_keywords(story)
    assets_data = list(_fetch_pexels(keywords)) + list(_fetch_pixabay(keywords))
    assets: list[Asset] = []
    existing_urls = {
        a.remote_url
        for a in session.exec(
            select(Asset).where(Asset.story_id == story_id, Asset.type == "image")
        ).all()
    }
    for data in assets_data:
        url = data.get("remote_url")
        if not url or url in existing_urls:
            continue
        existing_urls.add(url)
        asset = Asset(
            story_id=story_id,
            type="image",
            remote_url=url,
            provider=data.get("provider"),
            provider_id=data.get("provider_id"),
            selected=False,
            rank=None,
        )
        session.add(asset)
        assets.append(asset)
    session.commit()
    for asset in assets:
        session.refresh(asset)
    return assets


@router.get("/{story_id}/images", response_model=list[AssetRead])
def list_images(
    story_id: int, session: Session = Depends(get_session)
) -> list[AssetRead]:
    """Return image assets for a story ordered by rank, unranked last."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return session.exec(
        select(Asset)
        .where(Asset.story_id == story_id, Asset.type == "image")
        .order_by(Asset.rank.is_(None), Asset.rank, Asset.id)
    ).all()


@router.patch("/{story_id}/images/{asset_id}", response_model=AssetRead)
def update_image(
    story_id: int,
    asset_id: int,
    asset_in: AssetUpdate,
    session: Session = Depends(get_session),
) -> AssetRead:
    """Update fields like ``selected`` or ``rank`` for an image asset."""
    asset = session.get(Asset, asset_id)
    if not asset or asset.story_id != story_id or asset.type != "image":
        raise HTTPException(status_code=404, detail="Image not found")
    data = asset_in.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(asset, key, value)
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@router.post("/{story_id}/split", response_model=list[StoryPartRead])
def split_story(
    story_id: int,
    target_seconds: int = 60,
    session: Session = Depends(get_session),
) -> list[StoryPartRead]:
    """Split a story body into timed parts and persist them."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if not story.body_md:
        raise HTTPException(status_code=400, detail="Story body is empty")

    parts_bounds = _build_parts(story.body_md, target_seconds)

    existing_parts = session.exec(
        select(StoryPart).where(StoryPart.story_id == story_id)
    ).all()
    for part in existing_parts:
        session.delete(part)

    parts: list[StoryPart] = []
    for idx, (start, end) in enumerate(parts_bounds, 1):
        text = story.body_md[start:end].strip()
        est_seconds = _estimate_seconds(text)
        part = StoryPart(
            story_id=story_id,
            index=idx,
            body_md=text,
            est_seconds=est_seconds,
            start_char=start,
            end_char=end,
        )
        session.add(part)
        parts.append(part)
    session.commit()
    for part in parts:
        session.refresh(part)
    return parts


@router.post("/{story_id}/preview", response_model=list[PartPreview])
def preview_parts(
    story_id: int, parts: list[PartBounds], session: Session = Depends(get_session)
) -> list[PartPreview]:
    """Preview parts by returning snapped boundaries and estimated durations."""
    story = session.get(Story, story_id)
    if not story or not story.body_md:
        raise HTTPException(status_code=404, detail="Story not found")
    previews: list[PartPreview] = []
    body = story.body_md
    for idx, pb in enumerate(sorted(parts, key=lambda p: p.start_char), 1):
        start, end = _snap_boundaries(body, pb.start_char, pb.end_char)
        text = body[start:end].strip()
        secs = _estimate_seconds(text)
        previews.append(
            PartPreview(
                index=idx,
                body_md=text,
                est_seconds=secs,
                start_char=start,
                end_char=end,
            )
        )
    return previews


@router.put("/{story_id}/parts", response_model=list[StoryPartRead])
def replace_parts(
    story_id: int, parts: list[PartBounds], session: Session = Depends(get_session)
) -> list[StoryPartRead]:
    """Replace all parts for a story with provided boundaries."""
    story = session.get(Story, story_id)
    if not story or not story.body_md:
        raise HTTPException(status_code=404, detail="Story not found")
    if not parts:
        raise HTTPException(status_code=400, detail="No parts provided")
    body = story.body_md
    bounds: list[tuple[int, int]] = []
    prev_end = 0
    for pb in sorted(parts, key=lambda p: p.start_char):
        start, end = _snap_boundaries(body, pb.start_char, pb.end_char)
        if start < prev_end or start >= end:
            raise HTTPException(status_code=400, detail="Invalid part boundaries")
        secs = _estimate_seconds(body[start:end].strip())
        if secs < MIN_PART_SECONDS or secs > MAX_PART_SECONDS:
            raise HTTPException(status_code=400, detail="Part duration out of bounds")
        bounds.append((start, end))
        prev_end = end

    existing_parts = session.exec(
        select(StoryPart).where(StoryPart.story_id == story_id)
    ).all()
    for part in existing_parts:
        session.delete(part)

    parts_models: list[StoryPart] = []
    for idx, (start, end) in enumerate(bounds, 1):
        text = body[start:end].strip()
        secs = _estimate_seconds(text)
        part = StoryPart(
            story_id=story_id,
            index=idx,
            body_md=text,
            est_seconds=secs,
            start_char=start,
            end_char=end,
        )
        session.add(part)
        parts_models.append(part)
    session.commit()
    for p in parts_models:
        session.refresh(p)
    return parts_models


@router.post("/{story_id}/enqueue-series", status_code=status.HTTP_202_ACCEPTED)
def enqueue_series(
    story_id: int, session: Session = Depends(get_session)
) -> dict[str, list[dict[str, Any]]]:
    """Enqueue render_part jobs for each part of the story."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    images = session.exec(
        select(Asset)
        .where(
            Asset.story_id == story_id, Asset.type == "image", Asset.selected == True
        )
        .order_by(Asset.rank)
    ).all()
    if not images:
        raise HTTPException(status_code=400, detail="No selected images")

    parts = session.exec(
        select(StoryPart)
        .where(StoryPart.story_id == story_id)
        .order_by(StoryPart.index)
    ).all()
    if not parts:
        parts = split_story(story_id, session=session)

    asset_ids = [img.id for img in images]
    jobs: list[Job] = []
    for part in parts:
        job = Job(
            story_id=story_id,
            kind="render_part",
            status="queued",
            payload={
                "story_id": story_id,
                "part_index": part.index,
                "asset_ids": asset_ids,
            },
        )
        session.add(job)
        jobs.append(job)
    session.commit()
    for job in jobs:
        session.refresh(job)

    return {
        "jobs": [
            {
                "id": job.id,
                "story_id": job.story_id,
                "part_index": job.payload.get("part_index") if job.payload else None,
                "asset_ids": job.payload.get("asset_ids") if job.payload else [],
            }
            for job in jobs
        ]
    }


__all__ = ["router"]
