from pathlib import Path

from services.renderer.asset_cache import materialize_asset
from shared.config import settings


class FakeResponse:
    def __init__(self, content: bytes):
        self._content = content
        self.headers = {"content-type": "image/jpeg"}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size: int = 0):
        yield self._content


class FakeSession:
    def __init__(self, content: bytes):
        self.calls = 0
        self.content = content

    def get(self, url: str, timeout: int = 0, stream: bool = False):
        self.calls += 1
        return FakeResponse(self.content)


def test_remote_asset_cache_hit_and_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "REMOTE_ASSET_CACHE_DIR", tmp_path / "cache")
    asset = {
        "id": 5,
        "type": "image",
        "provider": "pixabay",
        "provider_id": "123",
        "remote_url": "https://example.com/fog.jpg",
    }
    session = FakeSession(b"abc")

    first = materialize_asset(asset, session=session)
    second = materialize_asset(asset, session=session)

    assert first.path.exists()
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert session.calls == 1


def test_local_asset_passthrough(tmp_path):
    asset_path = tmp_path / "local.jpg"
    asset_path.write_bytes(b"hello")
    result = materialize_asset({"id": 1, "local_path": str(asset_path), "type": "image"})
    assert result.path == asset_path
    assert result.cache_hit is True
