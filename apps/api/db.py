"""Database configuration for the API."""

from __future__ import annotations

from sqlmodel import SQLModel, Session, create_engine

from shared.config import settings


engine = create_engine(settings.DATABASE_URL, echo=False)


def init_db() -> None:
    """Create database tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """Yield a database session."""
    with Session(engine) as session:
        yield session


__all__ = ["engine", "init_db", "get_session"]

