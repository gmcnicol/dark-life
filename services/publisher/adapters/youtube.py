"""YouTube publisher using the official Data API."""

from __future__ import annotations

from pathlib import Path

try:
    from google.auth.transport.requests import Request  # type: ignore
    from googleapiclient.discovery import build  # type: ignore
    from googleapiclient.http import MediaFileUpload  # type: ignore
    from google.oauth2.credentials import Credentials  # type: ignore
except Exception:  # pragma: no cover
    Request = None  # type: ignore
    build = None  # type: ignore
    MediaFileUpload = None  # type: ignore
    Credentials = None  # type: ignore

from shared.config import settings
from shared.youtube_oauth import YOUTUBE_OAUTH_SCOPES


class YouTubePublishError(RuntimeError):
    pass


def publish(video_path: Path, title: str, description: str) -> str:
    if build is None:
        raise YouTubePublishError("google-api-python-client is not installed")
    creds = None
    if settings.YOUTUBE_TOKEN_FILE and settings.YOUTUBE_TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(settings.YOUTUBE_TOKEN_FILE),
                YOUTUBE_OAUTH_SCOPES,
            )
        except Exception as exc:  # pragma: no cover
            raise YouTubePublishError(f"Failed to load YouTube token: {exc}") from exc
    if not creds:
        raise YouTubePublishError("YouTube token is not configured for the publisher service")
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            if Request is None:
                raise YouTubePublishError("google-auth transport is not installed")
            try:
                creds.refresh(Request())
            except Exception as exc:  # pragma: no cover
                raise YouTubePublishError(f"Failed to refresh YouTube token: {exc}") from exc
            if settings.YOUTUBE_TOKEN_FILE:
                try:
                    settings.YOUTUBE_TOKEN_FILE.write_text(creds.to_json())
                except OSError:
                    pass
        else:
            raise YouTubePublishError(
                "YouTube token is invalid or missing a refresh token; rerun the local OAuth bootstrap"
            )
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "24",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response.get("id")
    if not video_id:
        raise YouTubePublishError("YouTube upload completed without a video id")
    return str(video_id)
