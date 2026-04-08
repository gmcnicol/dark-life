"""Recurring scheduler for ingestion and weekly compilation creation."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

from shared.config import settings
from shared.logging import log_error, log_info


def _headers() -> dict[str, str]:
    if settings.API_AUTH_TOKEN:
        return {"Authorization": f"Bearer {settings.API_AUTH_TOKEN}"}
    return {}


def _active_short_release_exists(story_id: int, active_script_version_id: int, sess: requests.sessions.Session, base: str) -> bool:
    releases = sess.get(
        f"{base}/stories/{story_id}/releases",
        headers=_headers(),
        timeout=30,
    )
    releases.raise_for_status()
    return any(
        release.get("variant") == "short" and release.get("script_version_id") == active_script_version_id
        for release in releases.json()
    )


def _fresh_pixabay_page(story_id: int, bundle_count: int) -> int:
    # Rotate through result pages so re-scheduling a story is less likely to reuse
    # the same first-page Pixabay hits every time.
    return max(1, min(10, bundle_count + 1 + (story_id % 3)))


def schedule_approved_shorts(session: requests.sessions.Session | None = None) -> None:
    sess = session or requests
    base = settings.API_BASE_URL.rstrip("/")
    stories = sess.get(
        f"{base}/stories",
        params={"status": "approved", "limit": 100},
        headers=_headers(),
        timeout=30,
    )
    stories.raise_for_status()

    for story in stories.json():
        story_id = int(story["id"])
        active_script_version_id = story.get("active_script_version_id")
        if not active_script_version_id:
            continue
        if _active_short_release_exists(story_id, int(active_script_version_id), sess, base):
            continue

        bundles = sess.get(
            f"{base}/stories/{story_id}/asset-bundles",
            headers=_headers(),
            timeout=30,
        )
        bundles.raise_for_status()
        fresh_page = _fresh_pixabay_page(story_id, len(bundles.json()))

        assets = sess.get(
            f"{base}/stories/{story_id}/assets",
            params={"page": fresh_page},
            headers=_headers(),
            timeout=30,
        )
        assets.raise_for_status()
        asset_refs = assets.json()
        if not asset_refs:
            log_error("scheduler_approved_shorts_no_assets", story_id=story_id, page=fresh_page)
            continue

        bundle_name = f"pixabay-fresh-{active_script_version_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        bundle = sess.post(
            f"{base}/stories/{story_id}/asset-bundles",
            json={
                "name": bundle_name,
                "variant": "short",
                "asset_refs": asset_refs,
                "music_policy": "first",
            },
            headers=_headers(),
            timeout=30,
        )
        bundle.raise_for_status()
        bundle_id = bundle.json()["id"]

        releases = sess.post(
            f"{base}/stories/{story_id}/releases",
            json={
                "preset_slug": "short-form",
                "asset_bundle_id": bundle_id,
            },
            headers=_headers(),
            timeout=30,
        )
        releases.raise_for_status()
        log_info(
            "scheduler_approved_short_scheduled",
            story_id=story_id,
            script_version_id=active_script_version_id,
            asset_bundle_id=bundle_id,
            release_count=len(releases.json()),
            pixabay_page=fresh_page,
        )


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

    if settings.SCHEDULER_ENABLE_APPROVED_SHORTS:
        try:
            schedule_approved_shorts(sess)
        except Exception as exc:
            log_error("scheduler_approved_shorts_error", error=str(exc))

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
