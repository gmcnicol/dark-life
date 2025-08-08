from __future__ import annotations

"""Simple poller that processes queued render jobs from the jobs table."""

import sqlite3
import time
from pathlib import Path

import typer

from shared.config import settings

app = typer.Typer(add_completion=False)


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


def _db_path() -> Path:
    """Return path to the jobs database."""
    return settings.BASE_DIR / "jobs.db"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA)
    conn.commit()


def process_once(conn: sqlite3.Connection) -> bool:
    """Process a single queued render job.

    Returns True if a job was processed.
    """
    cur = conn.execute(
        "SELECT id, payload FROM jobs WHERE status = 'queued' AND kind = 'render' ORDER BY created_at LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        return False

    job_id, payload = row
    # Mark running
    conn.execute("UPDATE jobs SET status = 'running', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
    conn.commit()

    # Print payload for demonstration
    print(payload)

    # Mark success
    conn.execute("UPDATE jobs SET status = 'success', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (job_id,))
    conn.commit()
    return True


@app.command()
def run(interval: float = 1.0) -> None:
    """Continuously poll for queued render jobs."""
    db_path = _db_path()
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn)
        while True:
            processed = process_once(conn)
            if not processed:
                time.sleep(interval)
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    app()
