"""YouTube uploader using the official Data API."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:  # Optional dependencies
    from googleapiclient.discovery import build  # type: ignore
    from googleapiclient.http import MediaFileUpload  # type: ignore
    from google.oauth2.credentials import Credentials  # type: ignore
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
except Exception:  # pragma: no cover - dependencies may be missing
    build = None  # type: ignore
    MediaFileUpload = None  # type: ignore
    Credentials = None  # type: ignore
    InstalledAppFlow = None  # type: ignore


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def upload(
    video: Path,
    title: str,
    client_secrets_file: Optional[Path] = None,
    token_file: Optional[Path] = None,
) -> None:
    """Upload ``video`` to YouTube with ``title``.

    If credentials are missing or the google API client isn't installed,
    the upload is skipped gracefully.
    """

    if build is None:
        print("google-api-python-client not installed; skipping upload")
        return

    creds = None
    if token_file and token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        except Exception as exc:  # pragma: no cover - handled gracefully
            print(f"Failed to load YouTube token: {exc}")

    if not creds or not creds.valid:
        if not client_secrets_file or not client_secrets_file.exists() or InstalledAppFlow is None:
            print("YouTube credentials missing; skipping upload")
            return
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secrets_file), SCOPES
        )
        creds = flow.run_local_server(port=0)
        if token_file:
            token_file.write_text(creds.to_json())

    try:
        youtube = build("youtube", "v3", credentials=creds)
        body = {"snippet": {"title": title}, "status": {"privacyStatus": "private"}}
        media = MediaFileUpload(str(video), mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )
        response = request.execute()
        print(f"Uploaded to YouTube: https://youtu.be/{response['id']}")
    except Exception as exc:  # pragma: no cover - handled gracefully
        print(f"YouTube upload failed: {exc}")

