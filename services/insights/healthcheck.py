"""Healthcheck for the insights poller."""

from __future__ import annotations

import time
from pathlib import Path

from shared.config import settings

HEARTBEAT_PATH = Path("/tmp/renderer/insights_heartbeat")


def main() -> None:
    if not HEARTBEAT_PATH.exists():
        raise SystemExit(1)
    max_age = max(settings.INSIGHTS_SYNC_INTERVAL_SEC * 2, 120)
    age = time.time() - HEARTBEAT_PATH.stat().st_mtime
    raise SystemExit(0 if age <= max_age else 1)


if __name__ == "__main__":
    main()
