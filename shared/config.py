"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

try:  # Optional dependency
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv not installed
    def load_dotenv(*args, **kwargs):  # type: ignore
        return None
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
    YOUTUBE_CLIENT_SECRETS_FILE: Path | None = Field(
        default=None,
        description="Path to OAuth client secrets JSON for YouTube uploads",
    )
    YOUTUBE_TOKEN_FILE: Path | None = Field(
        default=None,
        description="Path to stored YouTube OAuth token",
    )
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@postgres:5432/darklife",
        description="Postgres connection string",
    )
    BACKFILL_USE_CLOUDSEARCH: bool = Field(
        default=False, description="Use cloudsearch windows during backfill"
        )
    BACKFILL_MAX_PAGES: int = Field(
        default=12, description="Max pages fetched via new()"
        )
    LOG_LEVEL: str = Field(
        default="INFO", description="Logging level"
        )
    DEBUG_INGEST_SAMPLE: bool = Field(
        default=False, description="Log sample titles during ingest"
        )
    REDDIT_CLIENT_ID: str = Field(
        default="", description="Reddit API client id"
        )
    REDDIT_CLIENT_SECRET: str = Field(
        default="", description="Reddit API client secret"
        )
    REDDIT_USER_AGENT: str = Field(
        default="darklife/1.0", description="User agent for Reddit API"
    )
    API_BASE_URL: str = Field(
        default="",
        description="Base URL for the Dark Life API (used by ingestors)",
    )
    ADMIN_API_TOKEN: str = Field(
        default="",
        description="Bearer token for privileged API access",
    )


settings = Settings()

__all__ = ["Settings", "settings"]
