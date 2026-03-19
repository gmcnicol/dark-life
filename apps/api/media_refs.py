from __future__ import annotations

import hashlib
from typing import Any

from sqlmodel import Session, select

from .models import Asset, AssetBundle, StoryPart


def media_key(raw: dict[str, Any]) -> str:
    provider = raw.get("provider") or "remote"
    provider_id = raw.get("provider_id")
    if provider_id:
        return f"{provider}:{provider_id}"
    remote_url = raw.get("remote_url")
    if remote_url:
        return hashlib.sha256(str(remote_url).encode("utf-8")).hexdigest()[:16]
    local_path = raw.get("local_path")
    if local_path:
        return hashlib.sha256(str(local_path).encode("utf-8")).hexdigest()[:16]
    return hashlib.sha256(repr(sorted(raw.items())).encode("utf-8")).hexdigest()[:16]


def asset_to_media_ref(asset: Asset) -> dict[str, Any]:
    return {
        "key": media_key(
            {
                "provider": asset.provider,
                "provider_id": asset.provider_id,
                "remote_url": asset.remote_url,
                "local_path": asset.local_path,
            }
        ),
        "type": asset.type,
        "remote_url": asset.remote_url,
        "local_path": asset.local_path,
        "provider": asset.provider,
        "provider_id": asset.provider_id,
        "duration_ms": asset.duration_ms,
        "width": asset.width,
        "height": asset.height,
        "orientation": asset.orientation,
        "attribution": asset.attribution,
        "tags": asset.tags,
    }


def normalize_media_ref(raw: dict[str, Any]) -> dict[str, Any]:
    ref = {
        "key": raw.get("key") or media_key(raw),
        "type": raw.get("type") or "image",
        "remote_url": raw.get("remote_url"),
        "local_path": raw.get("local_path"),
        "provider": raw.get("provider"),
        "provider_id": raw.get("provider_id"),
        "duration_ms": raw.get("duration_ms"),
        "width": raw.get("width"),
        "height": raw.get("height"),
        "orientation": raw.get("orientation"),
        "attribution": raw.get("attribution"),
        "tags": raw.get("tags"),
    }
    if not ref["remote_url"] and not ref["local_path"]:
        raise ValueError("Media reference must include remote_url or local_path")
    return ref


def normalize_asset_refs(raw_refs: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_refs or []:
        ref = normalize_media_ref(raw)
        if ref["key"] in seen:
            continue
        seen.add(ref["key"])
        normalized.append(ref)
    return normalized


def bundle_asset_refs(bundle: AssetBundle, session: Session | None = None) -> list[dict[str, Any]]:
    normalized = normalize_asset_refs([item for item in bundle.asset_refs if isinstance(item, dict)])
    legacy_ids = [item for item in bundle.asset_refs if isinstance(item, int)]
    if legacy_ids and session is not None:
        assets = session.exec(select(Asset).where(Asset.id.in_(legacy_ids))).all()
        normalized.extend(
            ref for ref in (asset_to_media_ref(asset) for asset in assets) if ref["key"] not in {item["key"] for item in normalized}
        )
    return normalized


def ordered_part_asset_map(parts: list[StoryPart], asset_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not parts or not asset_refs:
        return []
    fallback_asset = asset_refs[0]
    return [
        {
            "story_part_id": part.id,
            "asset": asset_refs[index] if index < len(asset_refs) else fallback_asset,
        }
        for index, part in enumerate(parts)
    ]


def bundle_part_asset_map(
    bundle: AssetBundle,
    parts: list[StoryPart],
    session: Session | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    refs_by_key = {ref["key"]: ref for ref in bundle_asset_refs(bundle, session)}
    legacy_asset_ids: list[int] = []
    for row in bundle.part_asset_map:
        if not isinstance(row, dict):
            continue
        story_part_id = int(row["story_part_id"])
        if "asset" in row and isinstance(row["asset"], dict):
            asset = normalize_media_ref(row["asset"])
            refs_by_key.setdefault(asset["key"], asset)
            rows.append({"story_part_id": story_part_id, "asset": asset})
            continue
        asset_id = row.get("asset_id")
        if asset_id is not None:
            legacy_asset_ids.append(int(asset_id))
            rows.append({"story_part_id": story_part_id, "asset_id": int(asset_id)})

    if legacy_asset_ids and session is not None:
        assets = session.exec(select(Asset).where(Asset.id.in_(legacy_asset_ids))).all()
        legacy_by_id = {asset.id: asset_to_media_ref(asset) for asset in assets if asset.id is not None}
        converted: list[dict[str, Any]] = []
        for row in rows:
            if "asset" in row:
                converted.append(row)
                continue
            asset = legacy_by_id.get(row["asset_id"])
            if asset is not None:
                refs_by_key.setdefault(asset["key"], asset)
                converted.append({"story_part_id": row["story_part_id"], "asset": asset})
        rows = converted

    if rows:
        return rows
    return ordered_part_asset_map(parts, list(refs_by_key.values()))
