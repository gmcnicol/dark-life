"""Stories API router."""

from __future__ import annotations

from datetime import datetime
import os
import re
import json
import sqlite3
from typing import Iterable

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from .db import get_session
from .models import (
    Asset,
    AssetRead,
    AssetUpdate,
    Story,
    StoryCreate,
    StoryRead,
    StoryUpdate,
)
from shared.config import settings


router = APIRouter(prefix="/stories", tags=["stories"])


def _extract_keywords(story: Story) -> str:
    """Return a simple space-separated keyword string from a story."""
    text = f"{story.title} {story.body_md or ''}"
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return " ".join(words[:5])


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
            params={"key": api_key, "q": keywords, "image_type": "photo", "per_page": 8},
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
def list_stories(session: Session = Depends(get_session)) -> list[StoryRead]:
    """Return all stories."""
    return session.exec(select(Story)).all()


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


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(story_id: int, session: Session = Depends(get_session)) -> None:
    """Delete a story."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    session.delete(story)
    session.commit()
    return None


@router.post("/{story_id}/fetch-images", response_model=list[AssetRead])
def fetch_images(story_id: int, session: Session = Depends(get_session)) -> list[AssetRead]:
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
    for idx, data in enumerate(assets_data):
        if not data.get("remote_url") or data["remote_url"] in existing_urls:
            continue
        asset = Asset(
            story_id=story_id,
            type="image",
            remote_url=data["remote_url"],
            provider=data.get("provider"),
            provider_id=data.get("provider_id"),
            rank=idx,
        )
        session.add(asset)
        assets.append(asset)
    session.commit()
    for asset in assets:
        session.refresh(asset)
    return assets


@router.get("/{story_id}/images", response_model=list[AssetRead])
def list_images(story_id: int, session: Session = Depends(get_session)) -> list[AssetRead]:
    """List images associated with a story."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return session.exec(
        select(Asset)
        .where(Asset.story_id == story_id, Asset.type == "image")
        .order_by(Asset.rank)
    ).all()


@router.patch("/{story_id}/images/{asset_id}", response_model=AssetRead)
def update_image(
    story_id: int,
    asset_id: int,
    asset_in: AssetUpdate,
    session: Session = Depends(get_session),
) -> AssetRead:
    """Update selection or rank for an image asset."""
    asset = session.get(Asset, asset_id)
    if not asset or asset.story_id != story_id:
        raise HTTPException(status_code=404, detail="Image not found")
    data = asset_in.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(asset, key, value)
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@router.post("/{story_id}/enqueue-render", status_code=status.HTTP_202_ACCEPTED)
def enqueue_render(story_id: int, session: Session = Depends(get_session)) -> dict[str, int]:
    """Validate selected images and enqueue a render job."""
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    images = session.exec(
        select(Asset)
        .where(Asset.story_id == story_id, Asset.type == "image", Asset.selected == True)
        .order_by(Asset.rank)
    ).all()
    if not images:
        raise HTTPException(status_code=400, detail="No selected images")

    payload = json.dumps(
        {"story_id": story_id, "image_urls": [img.remote_url for img in images]}
    )

    db_path = settings.BASE_DIR / "jobs.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur = conn.execute(
            "INSERT INTO jobs (kind, status, payload) VALUES ('render', 'queued', ?)",
            (payload,),
        )
        job_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    return {"job_id": job_id}


__all__ = ["router"]

