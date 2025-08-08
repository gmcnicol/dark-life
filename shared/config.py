"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """Application settings read from environment variables."""

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    CONTENT_DIR: Path = BASE_DIR / "content"
    STORIES_DIR: Path = CONTENT_DIR / "stories"
    AUDIO_DIR: Path = CONTENT_DIR / "audio"
    VISUALS_DIR: Path = CONTENT_DIR / "visuals"
    OUTPUT_DIR: Path = BASE_DIR / "output"
    VIDEO_OUTPUT_DIR: Path = OUTPUT_DIR / "videos"
    MANIFEST_DIR: Path = OUTPUT_DIR / "manifest"
    RENDER_QUEUE_DIR: Path = BASE_DIR / "render_queue"
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/darklife",
        description="Postgres connection string",
    )


settings = Settings()

__all__ = ["Settings", "settings"]
