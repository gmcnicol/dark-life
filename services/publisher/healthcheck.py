"""Docker healthcheck for the publisher worker."""

from __future__ import annotations

import time
from pathlib import Path

from shared.config import settings

from .api_client import PublishApiClient


HEARTBEAT_FILE = Path(settings.TMP_DIR) / "publisher_heartbeat"


def main() -> int:
    try:
        PublishApiClient().list_jobs(status="queued", limit=1)
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
