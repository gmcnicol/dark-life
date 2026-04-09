"""Insights poller for published YouTube Shorts."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from shared.config import settings

from .api_client import InsightsApiClient
from .youtube_metrics import YouTubeInsightsError, fetch_release_metrics

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("insights")
HEARTBEAT_PATH = Path("/tmp/renderer/insights_heartbeat")


def log_event(event: str, **payload) -> None:
    logger.info(json.dumps({"service": "insights", "event": event, **payload}))


def touch_heartbeat() -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(str(time.time()))


def run_forever() -> None:
    client = InsightsApiClient()
    interval = max(settings.INSIGHTS_SYNC_INTERVAL_SEC, 60)
    while True:
        touch_heartbeat()
        try:
            targets = client.list_sync_targets(limit=settings.INSIGHTS_BATCH_LIMIT)
            log_event("poll", count=len(targets))
            for target in targets:
                try:
                    published_at = datetime.fromisoformat(str(target["published_at"]).replace("Z", "+00:00"))
                    metrics = fetch_release_metrics(str(target["platform_video_id"]), published_at=published_at)
                    client.post_snapshot(
                        {
                            "release_id": int(target["release_id"]),
                            "metrics": metrics,
                        }
                    )
                    log_event(
                        "snapshot",
                        release_id=target["release_id"],
                        story_id=target["story_id"],
                        views=metrics.get("views", 0.0),
                    )
                except YouTubeInsightsError as exc:
                    log_event(
                        "sync_skipped",
                        release_id=target["release_id"],
                        story_id=target["story_id"],
                        error_class="YouTubeInsightsError",
                        error_message=str(exc),
                    )
                except Exception as exc:  # pragma: no cover
                    log_event(
                        "sync_skipped",
                        release_id=target["release_id"],
                        story_id=target["story_id"],
                        error_class=exc.__class__.__name__,
                        error_message=str(exc),
                    )
        except YouTubeInsightsError as exc:
            log_event("error", error_class="YouTubeInsightsError", error_message=str(exc))
        except Exception as exc:  # pragma: no cover
            log_event("error", error_class=exc.__class__.__name__, error_message=str(exc))
        touch_heartbeat()
        time.sleep(interval)


if __name__ == "__main__":
    run_forever()
