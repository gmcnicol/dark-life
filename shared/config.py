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


# Absolute path constants used across renderer components
CONTENT_DIR = Path("/content")
MUSIC_DIR = CONTENT_DIR / "audio" / "music"
OUTPUT_DIR = Path("/output")
TMP_DIR = Path("/tmp/renderer")


class Settings(BaseSettings):
    """Application settings read from environment variables."""

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    CONTENT_DIR: Path = Field(default=CONTENT_DIR)
    MUSIC_DIR: Path = Field(default=MUSIC_DIR)
    OUTPUT_DIR: Path = Field(default=OUTPUT_DIR)
    TMP_DIR: Path = Field(default=TMP_DIR)
    STORIES_DIR: Path = Field(default_factory=lambda: CONTENT_DIR / "stories")
    AUDIO_DIR: Path = Field(default_factory=lambda: CONTENT_DIR / "audio")
    VISUALS_DIR: Path = Field(default_factory=lambda: CONTENT_DIR / "visuals")
    VIDEO_OUTPUT_DIR: Path = Field(default_factory=lambda: OUTPUT_DIR / "videos")
    MANIFEST_DIR: Path = Field(default_factory=lambda: OUTPUT_DIR / "manifest")
    RENDER_QUEUE_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "render_queue"
    )
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
    POLL_INTERVAL_MS: int = Field(
        default=5000,
        description="Polling interval for renderer worker in milliseconds",
    )
    MAX_CONCURRENT: int = Field(
        default=1,
        description="Maximum concurrent render jobs",
    )
    MAX_CLAIM: int = Field(
        default=1,
        description="Maximum jobs to claim per poll",
    )
    LEASE_SECONDS: int = Field(
        default=120,
        description="Lease duration when claiming render jobs",
    )


settings = Settings()

__all__ = [
    "Settings",
    "settings",
    "CONTENT_DIR",
    "MUSIC_DIR",
    "OUTPUT_DIR",
    "TMP_DIR",
]
