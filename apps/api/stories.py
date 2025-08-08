"""Stories API router."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from .db import get_session
from .models import Story, StoryCreate, StoryRead, StoryUpdate


router = APIRouter(prefix="/stories", tags=["stories"])


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


__all__ = ["router"]

