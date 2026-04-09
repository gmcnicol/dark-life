"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

try:  # Optional dependency
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dotenv not installed
    def load_dotenv(*args, **kwargs):  # type: ignore
        return None
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings

load_dotenv()


# Absolute path constants used across renderer components
# Environment variables can override these defaults.
CONTENT_DIR = Path(os.getenv("CONTENT_DIR", "/content"))
MUSIC_DIR = Path(
    os.getenv("MUSIC_DIR", str(Path(CONTENT_DIR) / "audio" / "music"))
)
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/output"))
TMP_DIR = Path(os.getenv("TMP_DIR", "/tmp/renderer"))
REMOTE_ASSET_CACHE_DIR = Path(
    os.getenv("REMOTE_ASSET_CACHE_DIR", str(Path(CONTENT_DIR) / "cache" / "remote-assets"))
)
DEFAULT_REDDIT_SUBREDDITS = (
    "Odd_directions",
    "shortscarystories",
    "nosleep",
    "stayawake",
    "Ruleshorror",
    "libraryofshadows",
    "JustNotRight",
    "TheCrypticCompendium",
    "SignalHorrorFiction",
    "scarystories",
    "SLEEPSPELL",
    "TwoSentenceHorror",
)
DEFAULT_REDDIT_SUBREDDITS_CSV = ",".join(DEFAULT_REDDIT_SUBREDDITS)


def parse_csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Application settings read from environment variables."""

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    CONTENT_DIR: Path = Field(default=CONTENT_DIR)
    MUSIC_DIR: Path = Field(default=MUSIC_DIR)
    OUTPUT_DIR: Path = Field(default=OUTPUT_DIR)
    TMP_DIR: Path = Field(default=TMP_DIR)
    REMOTE_ASSET_CACHE_DIR: Path = Field(default=REMOTE_ASSET_CACHE_DIR)
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
    REDDIT_DEFAULT_SUBREDDITS: str = Field(
        default=DEFAULT_REDDIT_SUBREDDITS_CSV,
        description="Comma-separated default subreddit list, in polling order",
    )
    API_BASE_URL: str = Field(
        default="http://api:8000",
        description="Base URL for the Dark Life API (used by ingestors)",
    )
    PUBLIC_BASE_URL: str = Field(
        default="http://localhost:8000",
        description="Public base URL used when generating signed artifact links",
    )
    API_AUTH_TOKEN: str = Field(
        default="",
        description="Bearer token for privileged API access",
        validation_alias=AliasChoices("API_AUTH_TOKEN", "ADMIN_API_TOKEN"),
    )
    ARTIFACT_SIGNING_SECRET: str = Field(
        default="",
        description="Secret used to sign public artifact URLs",
    )
    POLL_INTERVAL_MS: int = Field(
        default=5000,
        description="Polling interval for renderer worker in milliseconds",
    )
    HEARTBEAT_INTERVAL_SEC: int = Field(
        default=10,
        description="Renderer heartbeat interval in seconds",
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
    JOB_TIMEOUT_SEC: int = Field(
        default=600,
        description="Maximum seconds a render job may run before timing out",
    )

    # Background music mix configuration
    MUSIC_GAIN_DB: float = Field(
        default=-3.0,
        description="Baseline gain applied to music tracks in dB",
    )
    DUCKING_DB: float = Field(
        default=-12.0,
        description="Additional attenuation applied to music when voice is present",
    )

    # ElevenLabs TTS configuration
    TTS_PROVIDER: str = Field(
        default="elevenlabs",
        description="TTS provider to use (elevenlabs or xtts_local)",
    )
    ELEVENLABS_API_KEY: str = Field(
        default="",
        description="ElevenLabs authentication key",
    )
    ELEVENLABS_VOICE_ID: str = Field(
        default="",
        description="Voice identifier for synthesis",
    )
    ELEVENLABS_MODEL_ID: str = Field(
        default="eleven_multilingual_v2",
        description="Model identifier for synthesis",
    )
    TTS_CACHE_DIR: Path = Field(
        default_factory=lambda: CONTENT_DIR / "tts_cache",
        description="Directory for cached TTS audio",
    )
    TTS_RATE_LIMIT_RPS: int = Field(
        default=3,
        description="Polite request rate limit (requests per second)",
    )
    INSIGHTS_SYNC_INTERVAL_SEC: int = Field(
        default=3600,
        description="Polling interval for release insights collection in seconds",
    )
    INSIGHTS_LOOKBACK_DAYS: int = Field(
        default=30,
        description="How many days of published YouTube releases to track in insights",
    )
    INSIGHTS_BATCH_LIMIT: int = Field(
        default=50,
        description="Maximum number of published releases fetched per insights sync pass",
    )
    TTS_SPEAKING_STYLE: float = Field(
        default=0.0,
        description="Speaking style intensity (0-100)",
    )
    TTS_SPEAKING_SPEED: float = Field(
        default=1.0,
        description="Speaking speed multiplier",
    )
    XTTS_MODEL_DIR: Path | None = Field(
        default=None,
        description="Preferred XTTS artifact directory containing config/checkpoints/vocab/speaker files",
    )
    XTTS_CHECKPOINT_GLOB: str = Field(
        default="best_model*.pth",
        description="Glob used to auto-select the newest XTTS checkpoint inside XTTS_MODEL_DIR",
    )
    XTTS_WORKSPACE_DIR: Path | None = Field(
        default=None,
        description="Legacy XTTS workspace path retained for compatibility with older local setups",
    )
    XTTS_RUN_DIR: Path | None = Field(
        default=None,
        description="Legacy XTTS run directory; XTTS_MODEL_DIR is preferred",
    )
    XTTS_CHECKPOINT_PATH: Path | None = Field(
        default=None,
        description="Optional explicit XTTS checkpoint path overriding XTTS_RUN_DIR/best_model.pth",
    )
    XTTS_CONFIG_PATH: Path | None = Field(
        default=None,
        description="Optional explicit XTTS config path overriding XTTS_RUN_DIR/config.json",
    )
    XTTS_VOCAB_PATH: Path | None = Field(
        default=None,
        description="Optional explicit XTTS vocab path overriding derived defaults",
    )
    XTTS_SPEAKER_FILE_PATH: Path | None = Field(
        default=None,
        description="Optional explicit XTTS speakers_xtts.pth path overriding XTTS_RUN_DIR/speakers_xtts.pth",
    )
    XTTS_SPEAKER_WAV: Path | None = Field(
        default=None,
        description="Reference speaker wav passed to XTTS inference",
    )
    XTTS_LANGUAGE: str = Field(
        default="en",
        description="Language passed to XTTS inference",
    )
    XTTS_DEVICE: str = Field(
        default="cpu",
        description="Device hint used by the XTTS helper (cpu or mps)",
    )

    # Whisper ASR and subtitle configuration
    WHISPER_MODEL: str = Field(
        default="base", description="Whisper model size"
    )
    WHISPER_PROVIDER: str = Field(
        default="local", description="Subtitle provider (local or openai)"
    )
    WHISPER_DEVICE: str = Field(
        default="cpu", description="Device for Whisper inference"
    )
    SUBTITLES_FORMAT: str = Field(
        default="srt", description="Subtitle output format (srt or vtt)"
    )
    SUBTITLES_BURN_IN: bool = Field(
        default=False, description="Burn subtitles into video when true"
    )
    OPENAI_API_KEY: str = Field(
        default="",
        description="OpenAI API key for Whisper API",
    )
    OPENAI_SCRIPT_MODEL: str = Field(
        default="gpt-4.1-mini",
        description="OpenAI model used for script adaptation",
    )
    OPENAI_CRITIC_MODEL: str = Field(
        default="gpt-4.1-mini",
        description="OpenAI model used for script critique",
    )
    OPENAI_ANALYST_MODEL: str = Field(
        default="gpt-4.1-mini",
        description="OpenAI model used for experiment analysis",
    )
    REFINEMENT_POLL_INTERVAL_SEC: int = Field(
        default=10,
        description="Polling interval for refinement jobs",
    )
    REFINEMENT_MAX_CONCURRENT: int = Field(
        default=1,
        description="Maximum concurrent refinement jobs",
    )
    REFINEMENT_LEASE_SECONDS: int = Field(
        default=180,
        description="Lease duration when claiming refinement jobs",
    )
    REFINEMENT_DEFAULT_BATCH_SIZE: int = Field(
        default=20,
        description="Default number of candidates generated per refinement batch",
    )
    REFINEMENT_DEFAULT_SHORTLIST_SIZE: int = Field(
        default=3,
        description="Default number of shortlisted scripts per batch",
    )
    PEXELS_API_KEY: str = Field(
        default="",
        description="Pexels API key for remote image search",
    )
    PIXABAY_API_KEY: str = Field(
        default="",
        description="Pixabay API key for remote image search",
    )
    SCHEDULER_INTERVAL_SEC: int = Field(
        default=3600,
        description="Polling interval for recurring scheduler tasks",
    )
    SCHEDULER_ENABLE_REDDIT: bool = Field(
        default=True,
        description="Whether the scheduler should enqueue reddit incremental jobs",
    )
    SCHEDULER_ENABLE_APPROVED_SHORTS: bool = Field(
        default=False,
        description="Whether the scheduler should auto-schedule approved stories into short render jobs",
    )
    SCHEDULER_ENABLE_WEEKLY: bool = Field(
        default=True,
        description="Whether the scheduler should enqueue weekly compilation jobs",
    )
    PUBLISH_POLL_INTERVAL_SEC: int = Field(
        default=15,
        description="Polling interval for the publisher worker in seconds",
    )
    PUBLISH_MAX_CONCURRENT: int = Field(
        default=1,
        description="Maximum concurrent publish jobs",
    )
    PUBLISH_LEASE_SECONDS: int = Field(
        default=180,
        description="Lease duration when claiming publish jobs",
    )
    PUBLISH_RETRY_LIMIT: int = Field(
        default=3,
        description="Maximum publish retries before leaving a release errored",
    )
    ACTIVE_PUBLISH_PLATFORMS: str = Field(
        default="youtube",
        description="Comma-separated list of active publish platforms",
    )
    SHORTS_PUBLISH_SLOTS_UTC: str = Field(
        default="08:00,13:00,18:00",
        description="Comma-separated UTC publish slots for short-form releases in HH:MM format",
    )
    SHORTS_PUBLISH_HOUR_UTC: int = Field(
        default=12,
        description="Legacy fallback UTC hour for scheduled short-form publishes when no slot list is configured",
    )
    SHORTS_PUBLISH_MINUTE_UTC: int = Field(
        default=0,
        description="Legacy fallback UTC minute for scheduled short-form publishes when no slot list is configured",
    )
    EARLY_SIGNAL_WINDOW_HOURS: int = Field(
        default=4,
        description="Primary early decision window in hours for short-form release performance",
    )
    WEEKLY_COMPILATION_DAY_UTC: int = Field(
        default=4,
        description="UTC weekday for weekly compilation publish scheduling, where Monday is 0",
    )
    WEEKLY_COMPILATION_HOUR_UTC: int = Field(
        default=12,
        description="UTC hour for scheduled weekly compilation publishes",
    )
    WEEKLY_COMPILATION_MINUTE_UTC: int = Field(
        default=0,
        description="UTC minute for scheduled weekly compilation publishes",
    )
    INSTAGRAM_GRAPH_API_BASE: str = Field(
        default="https://graph.facebook.com/v23.0",
        description="Base URL for the Instagram Graph API",
    )
    INSTAGRAM_APP_ID: str = Field(
        default="",
        description="Instagram or Meta app identifier",
    )
    INSTAGRAM_BUSINESS_ACCOUNT_ID: str = Field(
        default="",
        description="Instagram business account identifier",
    )
    INSTAGRAM_ACCESS_TOKEN: str = Field(
        default="",
        description="Instagram Graph API access token",
    )

    # Compatibility attribute; ``ADMIN_API_TOKEN`` is retained as a property
    # so existing code referencing it continues to function. The backing
    # environment variable may be either ``API_AUTH_TOKEN`` or
    # ``ADMIN_API_TOKEN``.
    @property
    def ADMIN_API_TOKEN(self) -> str:  # pragma: no cover - simple alias
        return self.API_AUTH_TOKEN

    @ADMIN_API_TOKEN.setter
    def ADMIN_API_TOKEN(self, value: str) -> None:  # pragma: no cover - alias
        self.API_AUTH_TOKEN = value


settings = Settings()

__all__ = [
    "Settings",
    "settings",
    "CONTENT_DIR",
    "DEFAULT_REDDIT_SUBREDDITS",
    "DEFAULT_REDDIT_SUBREDDITS_CSV",
    "MUSIC_DIR",
    "OUTPUT_DIR",
    "TMP_DIR",
    "REMOTE_ASSET_CACHE_DIR",
    "parse_csv_list",
]
