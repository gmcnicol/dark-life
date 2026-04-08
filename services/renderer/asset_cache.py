"""Materialize the selected media reference into the current job directory."""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from shared.config import settings


@dataclass(frozen=True)
class MaterializedAsset:
    path: Path
    cache_hit: bool


def _suffix_for_asset(asset: dict, response: requests.Response | None = None) -> str:
    remote_url = asset.get("remote_url") or ""
    parsed = urlparse(remote_url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix:
        return suffix
    content_type = response.headers.get("content-type") if response is not None else None
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed:
            return guessed
    return ".mp4" if asset.get("type") == "video" else ".jpg"


def _resolve_pixabay_remote_url(provider_id: str) -> str | None:
    if not settings.PIXABAY_API_KEY:
        return None
    response = requests.get(
        "https://pixabay.com/api/",
        params={
            "key": settings.PIXABAY_API_KEY,
            "id": provider_id,
        },
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    hit = next(iter(payload.get("hits", [])), None)
    if not isinstance(hit, dict):
        return None
    return hit.get("webformatURL") or hit.get("largeImageURL")


def materialize_asset(
    asset: dict,
    *,
    output_dir: Path | None = None,
    session: requests.sessions.Session | None = None,
) -> MaterializedAsset:
    local_path = asset.get("local_path")
    if local_path:
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(path)
        return MaterializedAsset(path=path, cache_hit=True)

    remote_url = asset.get("remote_url")
    if not remote_url:
        raise FileNotFoundError("Asset missing remote_url")

    dest_dir = output_dir or Path(settings.TMP_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    sess = session or requests
    try:
        resp = sess.get(remote_url, timeout=60, stream=True)
        resp.raise_for_status()
    except requests.HTTPError:
        provider = str(asset.get("provider") or "")
        provider_id = str(asset.get("provider_id") or "")
        if provider != "pixabay" or not provider_id:
            raise
        refreshed_url = _resolve_pixabay_remote_url(provider_id)
        if not refreshed_url or refreshed_url == remote_url:
            raise
        remote_url = refreshed_url
        resp = sess.get(remote_url, timeout=60, stream=True)
        resp.raise_for_status()
    suffix = _suffix_for_asset(asset, response=resp)
    stem = asset.get("key") or asset.get("provider_id") or "selected-media"
    target = dest_dir / f"{stem}{suffix}"
    tmp = target.with_suffix(f"{target.suffix}.tmp")
    with tmp.open("wb") as handle:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    return MaterializedAsset(path=target, cache_hit=False)


__all__ = ["MaterializedAsset", "materialize_asset"]
