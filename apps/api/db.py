"""Database configuration and migration helpers for the API."""

from __future__ import annotations

from pathlib import Path
import logging

from alembic import command
from alembic.config import Config
from sqlmodel import Session, create_engine

from shared.config import settings


logger = logging.getLogger(__name__)

engine = create_engine(settings.DATABASE_URL, echo=False)


def init_db() -> None:
    """Run Alembic migrations to ensure the schema is up to date."""
    root_path = Path(__file__).resolve().parents[2]
    alembic_cfg = Config(str(root_path / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    logger.info("running alembic upgrade head")
    command.upgrade(alembic_cfg, "head")


def get_session() -> Session:
    """Yield a database session."""
    with Session(engine) as session:
        yield session


__all__ = ["engine", "init_db", "get_session"]

