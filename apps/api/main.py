"""FastAPI application setup with startup migrations and readiness probes."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from time import monotonic

from .db import Session, engine, init_db
from .pipeline import ensure_default_presets
from .refinement import ensure_default_prompt_versions
from .script_refinement import router as script_refinement_router
from .stories import router as stories_router
from .jobs import router as jobs_router
from .reddit_admin import router as reddit_admin_router
from .admin_stories import router as admin_stories_router
from .admin_render_jobs import router as admin_render_jobs_router
from .admin_settings import router as admin_settings_router
from .insights import router as insights_router
from .publish_jobs import router as publish_jobs_router
from .public_artifacts import router as public_artifacts_router
from .render_jobs import router as render_jobs_router


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")
ready = False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global ready
    init_db()
    with Session(engine) as session:
        ensure_default_presets(session)
        ensure_default_prompt_versions(session)
    ready = True
    yield


app = FastAPI(title="Dark Life API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = monotonic()
        response = await call_next(request)
        duration_ms = int((monotonic() - start) * 1000)
        logger.info(
            json.dumps(
                {
                    "service": "api",
                    "event": "request",
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }
            )
        )
        return response


app.add_middleware(LogRequestsMiddleware)
app.include_router(stories_router)
app.include_router(script_refinement_router)
app.include_router(jobs_router)
app.include_router(reddit_admin_router)
app.include_router(admin_stories_router)
app.include_router(admin_render_jobs_router)
app.include_router(admin_settings_router)
app.include_router(insights_router)
app.include_router(render_jobs_router)
app.include_router(publish_jobs_router)
app.include_router(public_artifacts_router)


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
