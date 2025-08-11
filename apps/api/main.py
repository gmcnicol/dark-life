"""FastAPI application setup with startup migrations and readiness probes."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from .db import init_db
from .stories import router as stories_router
from .jobs import router as jobs_router
from .reddit_admin import router as reddit_admin_router
from .admin_stories import router as admin_stories_router


logger = logging.getLogger(__name__)
ready = False

app = FastAPI(title="Dark Life API")
app.include_router(stories_router)
app.include_router(jobs_router)
app.include_router(reddit_admin_router)
app.include_router(admin_stories_router)


@app.on_event("startup")
def on_startup() -> None:
    """Run database migrations before serving traffic."""
    global ready
    init_db()
    ready = True


@app.get("/healthz")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness probe that flips true after migrations."""
    if not ready:
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ok"}
