import json
import sqlite3
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from shared.config import settings
from services.renderer import poller


def test_poller_processes_job(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(settings, "BASE_DIR", tmp_path)
    db_path = tmp_path / "jobs.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, status TEXT, payload TEXT, created_at TEXT, updated_at TEXT)"
    )
    payload = json.dumps({"story": 123})
    conn.execute("INSERT INTO jobs (kind, status, payload) VALUES ('render', 'queued', ?)", (payload,))
    conn.commit()
    conn.close()

    conn = sqlite3.connect(db_path)
    try:
        processed = poller.process_once(conn)
    finally:
        conn.close()

    assert processed
    out = capsys.readouterr().out.strip()
    assert out == payload

    conn = sqlite3.connect(db_path)
    status = conn.execute("SELECT status FROM jobs WHERE id = 1").fetchone()[0]
    conn.close()
    assert status == "success"
