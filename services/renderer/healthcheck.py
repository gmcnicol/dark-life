"""Docker healthcheck for the renderer worker."""

from __future__ import annotations

import time
from pathlib import Path

import requests

from shared.config import settings

HEARTBEAT_FILE = Path(settings.TMP_DIR) / "worker_heartbeat"


def main() -> int:
    try:
        resp = requests.get(
            f"{settings.API_BASE_URL.rstrip('/')}/healthz",
            timeout=5,
        )
        resp.raise_for_status()
    except Exception:
        return 1

    try:
        mtime = HEARTBEAT_FILE.stat().st_mtime
    except FileNotFoundError:
        return 1
    if time.time() - mtime > 60:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
