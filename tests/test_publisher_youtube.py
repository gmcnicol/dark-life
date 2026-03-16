from pathlib import Path

from services.publisher.adapters import youtube
from shared.config import settings


class FakeCreds:
    def __init__(self, *, valid: bool, expired: bool, refresh_token: str | None) -> None:
        self.valid = valid
        self.expired = expired
        self.refresh_token = refresh_token
        self.refresh_calls = 0

    def refresh(self, _request) -> None:
        self.refresh_calls += 1
        self.valid = True
        self.expired = False

    def to_json(self) -> str:
        return '{"token": "refreshed"}'


def test_publish_refreshes_expired_token(monkeypatch, tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token":"stale"}')
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")

    creds = FakeCreds(valid=False, expired=True, refresh_token="refresh-token")
    build_calls: list[tuple[str, str, object]] = []

    class FakeCredentials:
        @staticmethod
        def from_authorized_user_file(_path: str, _scopes: list[str]) -> FakeCreds:
            return creds

    class FakeInsertRequest:
        def execute(self) -> dict[str, str]:
            return {"id": "yt-123"}

    class FakeVideosResource:
        def insert(self, *, part: str, body: dict, media_body: object) -> FakeInsertRequest:
            assert part == "snippet,status"
            assert body["snippet"]["categoryId"] == "24"
            assert body["snippet"]["defaultLanguage"] == "en"
            assert body["snippet"]["defaultAudioLanguage"] == "en"
            assert body["status"]["privacyStatus"] == "public"
            assert body["status"]["selfDeclaredMadeForKids"] is False
            assert media_body == {"path": str(video_path), "mimetype": "video/mp4", "resumable": True}
            return FakeInsertRequest()

    class FakeYouTube:
        def videos(self) -> FakeVideosResource:
            return FakeVideosResource()

    monkeypatch.setattr(settings, "YOUTUBE_TOKEN_FILE", token_file)
    monkeypatch.setattr(youtube, "Credentials", FakeCredentials)
    monkeypatch.setattr(youtube, "Request", lambda: object())
    monkeypatch.setattr(
        youtube,
        "MediaFileUpload",
        lambda path, mimetype, resumable: {
            "path": path,
            "mimetype": mimetype,
            "resumable": resumable,
        },
    )
    monkeypatch.setattr(
        youtube,
        "build",
        lambda service, version, credentials: build_calls.append((service, version, credentials)) or FakeYouTube(),
    )

    result = youtube.publish(video_path, "Title", "Description")

    assert result == "yt-123"
    assert creds.refresh_calls == 1
    assert token_file.read_text() == '{"token": "refreshed"}'
    assert build_calls == [("youtube", "v3", creds)]


def test_publish_rejects_invalid_non_refreshable_token(monkeypatch, tmp_path):
    token_file = tmp_path / "token.json"
    token_file.write_text('{"token":"bad"}')
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"video")

    creds = FakeCreds(valid=False, expired=False, refresh_token=None)

    class FakeCredentials:
        @staticmethod
        def from_authorized_user_file(_path: str, _scopes: list[str]) -> FakeCreds:
            return creds

    monkeypatch.setattr(settings, "YOUTUBE_TOKEN_FILE", token_file)
    monkeypatch.setattr(youtube, "Credentials", FakeCredentials)

    try:
        youtube.publish(video_path, "Title", "Description")
    except youtube.YouTubePublishError as exc:
        assert "refresh token" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected YouTubePublishError")
