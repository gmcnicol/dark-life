"""YouTube publisher using the official Data API."""

from __future__ import annotations

from pathlib import Path

try:
    from googleapiclient.discovery import build  # type: ignore
    from googleapiclient.http import MediaFileUpload  # type: ignore
    from google.oauth2.credentials import Credentials  # type: ignore
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
except Exception:  # pragma: no cover
    build = None  # type: ignore
    MediaFileUpload = None  # type: ignore
    Credentials = None  # type: ignore
    InstalledAppFlow = None  # type: ignore

from shared.config import settings

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubePublishError(RuntimeError):
    pass


def publish(video_path: Path, title: str, description: str) -> str:
    if build is None:
        raise YouTubePublishError("google-api-python-client is not installed")
    creds = None
    if settings.YOUTUBE_TOKEN_FILE and settings.YOUTUBE_TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(settings.YOUTUBE_TOKEN_FILE), SCOPES)
        except Exception as exc:  # pragma: no cover
            raise YouTubePublishError(f"Failed to load YouTube token: {exc}") from exc
    if not creds or not creds.valid:
        if not settings.YOUTUBE_CLIENT_SECRETS_FILE or not settings.YOUTUBE_CLIENT_SECRETS_FILE.exists() or InstalledAppFlow is None:
            raise YouTubePublishError("YouTube credentials are not configured")
        flow = InstalledAppFlow.from_client_secrets_file(str(settings.YOUTUBE_CLIENT_SECRETS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
        if settings.YOUTUBE_TOKEN_FILE:
            settings.YOUTUBE_TOKEN_FILE.write_text(creds.to_json())
    youtube = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title, "description": description},
        "status": {"privacyStatus": "private"},
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response.get("id")
    if not video_id:
        raise YouTubePublishError("YouTube upload completed without a video id")
    return str(video_id)
