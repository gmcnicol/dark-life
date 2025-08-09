"""Jobs API router."""

from __future__ import annotations

import json
import sqlite3
from typing import List, Dict, Any

from fastapi import APIRouter

from shared.config import settings

router = APIRouter(prefix="/jobs", tags=["jobs"])

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.BASE_DIR / "jobs.db")
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


@router.get("/", response_model=List[Dict[str, Any]])
def list_jobs() -> List[Dict[str, Any]]:
    """Return all jobs in the queue."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, kind, status, payload, created_at, updated_at FROM jobs ORDER BY id DESC"
        ).fetchall()
    jobs: List[Dict[str, Any]] = []
    for row in rows:
        job = dict(row)
        try:
            job["payload"] = json.loads(job["payload"])
        except Exception:
            pass
        jobs.append(job)
    return jobs


__all__ = ["router"]
