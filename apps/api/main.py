"""FastAPI application setup."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from .db import init_db
from .stories import router as stories_router
from .jobs import router as jobs_router
from .reddit_admin import router as reddit_admin_router


logger = logging.getLogger(__name__)

app = FastAPI(title="Dark Life API")
app.include_router(stories_router)
app.include_router(jobs_router)
app.include_router(reddit_admin_router)


@app.on_event("startup")
def on_startup() -> None:
    """Initialize application services."""
    try:
        init_db()
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Database initialization failed: %s", exc)


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
