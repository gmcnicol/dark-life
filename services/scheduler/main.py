"""Recurring scheduler for ingestion and weekly compilation creation."""

from __future__ import annotations

import time

import requests

from shared.config import settings
from shared.logging import log_error, log_info


def _headers() -> dict[str, str]:
    if settings.API_AUTH_TOKEN:
        return {"Authorization": f"Bearer {settings.API_AUTH_TOKEN}"}
    return {}


def run_once(session: requests.sessions.Session | None = None) -> None:
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    if settings.SCHEDULER_ENABLE_REDDIT:
        try:
            sess.post(
                f"{base}/admin/reddit/incremental",
                json={},
                headers=_headers(),
                timeout=30,
            ).raise_for_status()
            log_info("scheduler_reddit_incremental")
        except Exception as exc:
            log_error("scheduler_reddit_incremental_error", error=str(exc))

    if settings.SCHEDULER_ENABLE_WEEKLY:
        try:
            stories = sess.get(
                f"{base}/stories",
                params={"status": "publish_ready", "limit": 100},
                headers=_headers(),
                timeout=30,
            )
            stories.raise_for_status()
            for story in stories.json():
                compilations = sess.get(
                    f"{base}/stories/{story['id']}/compilations",
                    headers=_headers(),
                    timeout=30,
                )
                compilations.raise_for_status()
                if compilations.json():
                    continue
                res = sess.post(
                    f"{base}/stories/{story['id']}/compilations",
                    json={"preset_slug": "weekly-full", "platforms": ["youtube"]},
                    headers=_headers(),
                    timeout=30,
                )
                res.raise_for_status()
                log_info("scheduler_compilation_created", story_id=story["id"])
        except Exception as exc:
            log_error("scheduler_weekly_error", error=str(exc))

    try:
        sess.post(
            f"{base}/refinement-jobs/maintenance",
            headers=_headers(),
            timeout=30,
        ).raise_for_status()
        log_info("scheduler_refinement_maintenance")
    except Exception as exc:
        log_error("scheduler_refinement_maintenance_error", error=str(exc))


def run() -> None:  # pragma: no cover - continuous loop
    log_info("scheduler_start", interval_sec=settings.SCHEDULER_INTERVAL_SEC)
    while True:
        run_once()
        time.sleep(settings.SCHEDULER_INTERVAL_SEC)


if __name__ == "__main__":
    run()
