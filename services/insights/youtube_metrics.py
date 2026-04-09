"""YouTube metrics fetcher for the insights service."""

from __future__ import annotations

from datetime import datetime, timezone

try:
    from google.auth.transport.requests import Request  # type: ignore
    from googleapiclient.discovery import build  # type: ignore
    from google.oauth2.credentials import Credentials  # type: ignore
except Exception:  # pragma: no cover
    Request = None  # type: ignore
    build = None  # type: ignore
    Credentials = None  # type: ignore

from shared.config import settings
from shared.youtube_oauth import YOUTUBE_OAUTH_SCOPES


class YouTubeInsightsError(RuntimeError):
    pass


def _load_credentials():
    if build is None or Credentials is None:
        raise YouTubeInsightsError("google-api-python-client is not installed")
    if not settings.YOUTUBE_TOKEN_FILE or not settings.YOUTUBE_TOKEN_FILE.exists():
        raise YouTubeInsightsError("YouTube token is not configured for the insights service")
    try:
        creds = Credentials.from_authorized_user_file(
            str(settings.YOUTUBE_TOKEN_FILE),
            YOUTUBE_OAUTH_SCOPES,
        )
    except Exception as exc:  # pragma: no cover
        raise YouTubeInsightsError(f"Failed to load YouTube token: {exc}") from exc
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            if Request is None:
                raise YouTubeInsightsError("google-auth transport is not installed")
            try:
                creds.refresh(Request())
            except Exception as exc:  # pragma: no cover
                raise YouTubeInsightsError(f"Failed to refresh YouTube token: {exc}") from exc
            if settings.YOUTUBE_TOKEN_FILE:
                try:
                    settings.YOUTUBE_TOKEN_FILE.write_text(creds.to_json())
                except OSError:
                    pass
        else:
            raise YouTubeInsightsError("YouTube token is invalid or missing a refresh token")
    return creds


def _channel_id(youtube) -> str:
    response = youtube.channels().list(part="id", mine=True).execute()
    items = response.get("items") or []
    if not items:
        raise YouTubeInsightsError("Unable to resolve authenticated YouTube channel")
    channel_id = items[0].get("id")
    if not channel_id:
        raise YouTubeInsightsError("YouTube channel response did not include an id")
    return str(channel_id)


def fetch_release_metrics(video_id: str, *, published_at: datetime) -> dict[str, float]:
    creds = _load_credentials()
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    statistics_response = youtube.videos().list(part="statistics", id=video_id).execute()
    items = statistics_response.get("items") or []
    statistics = (items[0] or {}).get("statistics") if items else {}
    metrics = {
        "views": float((statistics or {}).get("viewCount") or 0.0),
        "likes": float((statistics or {}).get("likeCount") or 0.0),
        "comments": float((statistics or {}).get("commentCount") or 0.0),
        "shares": 0.0,
        "impressions": 0.0,
        "avg_view_duration": 0.0,
        "percent_viewed": 0.0,
        "completion_rate": 0.0,
        "subs_gained": 0.0,
    }

    start_date = published_at.astimezone(timezone.utc).date().isoformat()
    end_date = datetime.now(timezone.utc).date().isoformat()
    try:
        analytics = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
        channel_id = _channel_id(youtube)
        analytics_response = analytics.reports().query(
            ids=f"channel=={channel_id}",
            startDate=start_date,
            endDate=end_date,
            metrics=(
                "views,likes,comments,shares,averageViewDuration,averageViewPercentage,"
                "subscribersGained,impressions"
            ),
            filters=f"video=={video_id}",
        ).execute()
        headers = [column.get("name") for column in analytics_response.get("columnHeaders") or []]
        rows = analytics_response.get("rows") or []
        if rows:
            values = {headers[index]: rows[0][index] for index in range(min(len(headers), len(rows[0])))}
            metrics["views"] = float(values.get("views") or metrics["views"])
            metrics["likes"] = float(values.get("likes") or metrics["likes"])
            metrics["comments"] = float(values.get("comments") or metrics["comments"])
            metrics["shares"] = float(values.get("shares") or 0.0)
            metrics["impressions"] = float(values.get("impressions") or 0.0)
            metrics["avg_view_duration"] = float(values.get("averageViewDuration") or 0.0)
            metrics["percent_viewed"] = float(values.get("averageViewPercentage") or 0.0)
            metrics["completion_rate"] = float(values.get("averageViewPercentage") or 0.0)
            metrics["subs_gained"] = float(values.get("subscribersGained") or 0.0)
    except Exception:
        pass
    return metrics
