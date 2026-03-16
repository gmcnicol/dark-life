"""Remote asset caching and materialization for renderer jobs."""

from __future__ import annotations

import hashlib
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from shared.config import settings
from shared.logging import log_info


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


def _cache_key(asset: dict) -> str:
    provider = asset.get("provider") or "remote"
    provider_id = asset.get("provider_id")
    if provider_id:
        return f"{provider}-{provider_id}"
    remote_url = asset.get("remote_url")
    if not remote_url:
        return f"{provider}-local"
    digest = hashlib.sha256(str(remote_url).encode("utf-8")).hexdigest()
    return f"{provider}-{digest}"


def materialize_asset(
    asset: dict,
    *,
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

    sess = session or requests
    cache_root = Path(settings.REMOTE_ASSET_CACHE_DIR)
    cache_root.mkdir(parents=True, exist_ok=True)
    provider = asset.get("provider") or "remote"
    provider_dir = cache_root / provider
    provider_dir.mkdir(parents=True, exist_ok=True)

    provisional = provider_dir / _cache_key(asset)
    existing = next(provider_dir.glob(f"{provisional.name}.*"), None)
    if existing and existing.exists():
        log_info(
            "asset_cache_hit",
            asset_id=asset.get("id"),
            provider=provider,
            path=str(existing),
        )
        return MaterializedAsset(path=existing, cache_hit=True)

    resp = sess.get(remote_url, timeout=60, stream=True)
    resp.raise_for_status()
    suffix = _suffix_for_asset(asset, response=resp)
    target = provider_dir / f"{provisional.name}{suffix}"
    if target.exists():
        return MaterializedAsset(path=target, cache_hit=True)

    tmp = target.with_suffix(f"{target.suffix}.tmp")
    with tmp.open("wb") as handle:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    log_info(
        "asset_cache_miss",
        asset_id=asset.get("id"),
        provider=provider,
        path=str(target),
    )
    return MaterializedAsset(path=target, cache_hit=False)


__all__ = ["MaterializedAsset", "materialize_asset"]
