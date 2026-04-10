"""Canonical operator-facing API routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import mimetypes
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse
import requests

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlmodel import Session, select

from shared.config import settings
from shared.workflow import PublishApprovalStatus, PublishJobStatus, ReleaseStatus, RenderVariant, StoryStatus, can_transition_story

from .db import get_session
from .media_refs import asset_to_media_ref, bundle_asset_refs, bundle_part_asset_map, media_key, normalize_asset_refs, normalize_media_ref, ordered_part_asset_map
from .models import (
    Asset,
    AssetBundle,
    AssetBundleRead,
    AssetRead,
    ScriptBatch,
    ScriptBatchRead,
    Compilation,
    CompilationRead,
    Release,
    ReleaseRead,
    RenderArtifact,
    RenderArtifactRead,
    RenderPreset,
    RenderPresetRead,
    ScriptVersion,
    ScriptVersionRead,
    MediaReference,
    PartMediaSelection,
    Story,
    StoryCreate,
    StoryPart,
    StoryPartRead,
    StoryRead,
    StoryUpdate,
)
from .publishing import (
    active_publish_platforms,
    approval_payload_status,
    delivery_mode_for_platform,
    ensure_publish_job,
    manual_handoff_metadata,
    maybe_mark_story_published,
    release_read,
    resolve_publish_job,
    short_release_schedule_from,
    weekly_compilation_schedule,
    validate_release_platform,
)
from .pipeline import (
    create_asset_bundle,
    create_short_releases,
    create_weekly_compilation,
    ensure_default_presets,
    generate_release_metadata,
    upsert_script,
)
from .script_refinement import enqueue_compat_script_generation, run_compat_script_generation
from .story_duplicates import find_duplicate_story

router = APIRouter(tags=["stories"])
logger = logging.getLogger(__name__)

WORDS_PER_MINUTE = 160
WORDS_PER_SECOND = WORDS_PER_MINUTE / 60
CHARS_PER_WORD = 5
CHARS_PER_SECOND = WORDS_PER_SECOND * CHARS_PER_WORD
MIN_PART_SECONDS = 30
MAX_PART_SECONDS = 75
SENTENCE_RE = re.compile(r"[^.!?]+[.!?](?:\s+|$)")
IMAGE_SEARCH_BASE_TERMS = (
    "uncanny",
    "liminal",
    "subtle",
)
PIXABAY_RESULT_LIMIT = 24
IMAGE_SEARCH_THEME_CUES = (
    {
        "name": "isolation",
        "triggers": ("alone", "lonely", "empty", "isolated", "missing", "silent", "quiet", "vacant", "remote", "stranded"),
        "terms": ("vacant", "stillness", "silhouette"),
    },
    {
        "name": "decay",
        "triggers": ("abandoned", "rotting", "derelict", "ruin", "decay", "forgotten", "vacant", "neglected"),
        "terms": ("abandoned", "vacant", "threshold"),
    },
    {
        "name": "confinement",
        "triggers": ("hallway", "corridor", "basement", "attic", "door", "window", "apartment", "house", "room", "stair"),
        "terms": ("hallway", "doorway", "empty"),
    },
    {
        "name": "wilderness",
        "triggers": ("forest", "woods", "wood", "cabin", "lake", "road", "trail", "field", "swamp", "fog"),
        "terms": ("forest", "mist", "stillness"),
    },
    {
        "name": "night",
        "triggers": ("night", "midnight", "moon", "storm", "rain", "fog", "dark"),
        "terms": ("night", "fog", "quiet"),
    },
    {
        "name": "presence",
        "triggers": ("shadow", "watching", "watched", "stare", "whisper", "breath", "footstep", "knock", "scratch", "voice"),
        "terms": ("uncanny", "stillness", "figure"),
    },
)


class PartInput(BaseModel):
    body_md: str | None = None
    approved: bool = True
    start_char: int | None = None
    end_char: int | None = None


class AssetBundleCreate(BaseModel):
    name: str = "Primary bundle"
    asset_refs: list[MediaReference]
    part_asset_map: list[PartMediaSelection] | None = None
    variant: str = RenderVariant.SHORT.value
    music_policy: str = "first"
    music_track: str | None = None


class ReleaseCreate(BaseModel):
    platforms: list[str] = ["youtube"]
    preset_slug: str = "short-form"
    asset_bundle_id: int | None = None


class CompilationCreate(BaseModel):
    preset_slug: str = "weekly-full"
    platforms: list[str] = ["youtube"]


class ScriptGenerationAccepted(BaseModel):
    batch_id: int
    status: str


class PublishUpdate(BaseModel):
    platform_video_id: str | None = None
    notes: str | None = None


class ReleaseRescheduleResult(BaseModel):
    total_rescheduled: int
    releases: list[ReleaseRead]


class ReleaseApprovalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    publish_at: datetime | None = None


def _get_story(session: Session, story_id: int) -> Story:
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


def _serialize_releases(session: Session, releases: list[Release]) -> list[ReleaseRead]:
    return [release_read(session, release) for release in releases]


def _sync_release_state(release: Release, status: str) -> None:
    release.status = status
    release.publish_status = status


def _extract_image_keywords(story: Story) -> str:
    text = f"{story.title} {story.body_md or ''}".lower()
    scored_cues: list[tuple[int, int, tuple[str, ...]]] = []

    for index, cue in enumerate(IMAGE_SEARCH_THEME_CUES):
        score = sum(1 for trigger in cue["triggers"] if trigger in text)
        if score:
            scored_cues.append((score, index, cue["terms"]))

    keywords: list[str] = []
    if scored_cues:
        for _score, _index, terms in sorted(scored_cues, key=lambda item: (-item[0], item[1]))[:2]:
            keywords.extend(terms)
        keywords.extend(IMAGE_SEARCH_BASE_TERMS)
    else:
        keywords.extend(IMAGE_SEARCH_BASE_TERMS)
        keywords.extend(("shadows", "mist", "silhouette"))

    return " ".join(list(dict.fromkeys(keywords))[:7])


def _list_existing_story_images(session: Session, story_id: int) -> list[Asset]:
    return session.exec(
        select(Asset)
        .where(Asset.story_id == story_id, Asset.type == "image")
        .order_by(Asset.rank.is_(None), Asset.rank, Asset.id.desc())
    ).all()


def _pixabay_orientation(width: Any, height: Any) -> str | None:
    try:
        image_width = int(width or 0)
        image_height = int(height or 0)
    except (TypeError, ValueError):
        return None
    if image_width <= 0 or image_height <= 0:
        return None
    if image_height > image_width:
        return "portrait"
    if image_width > image_height:
        return "landscape"
    return "square"


def _pixabay_hit_score(hit: dict[str, Any]) -> float:
    width = int(hit.get("imageWidth") or 0)
    height = int(hit.get("imageHeight") or 0)
    area = max(width * height, 0)
    likes = int(hit.get("likes") or 0)
    comments = int(hit.get("comments") or 0)
    downloads = int(hit.get("downloads") or 0)
    views = int(hit.get("views") or 0)
    orientation = _pixabay_orientation(width, height)
    portrait_bonus = 250_000 if orientation == "portrait" else 100_000 if orientation == "square" else 0
    return (
        float(area)
        + (likes * 50_000.0)
        + (comments * 75_000.0)
        + (downloads * 2_000.0)
        + (views * 50.0)
        + portrait_bonus
    )


def _fetch_pixabay_assets(keywords: str, *, page: int = 1) -> list[dict[str, Any]]:
    if not settings.PIXABAY_API_KEY:
        logger.warning("pixabay_assets_skipped_missing_key", extra={"keywords": keywords, "page": page})
        return []
    try:
        response = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": settings.PIXABAY_API_KEY,
                "q": keywords,
                "image_type": "photo",
                "per_page": PIXABAY_RESULT_LIMIT,
                "page": max(page, 1),
                "safesearch": "true",
            },
            headers={"User-Agent": "dark-life-api/1.0"},
            timeout=(3.05, 8),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.warning(
            "pixabay_assets_request_failed",
            extra={
                "keywords": keywords,
                "page": page,
                "error_class": exc.__class__.__name__,
                "error_message": str(exc)[:300],
            },
        )
        return []
    except ValueError as exc:
        logger.warning(
            "pixabay_assets_invalid_json",
            extra={
                "keywords": keywords,
                "page": page,
                "error_class": exc.__class__.__name__,
                "error_message": str(exc)[:300],
            },
        )
        return []

    assets: list[dict[str, Any]] = []
    sorted_hits = sorted(
        [hit for hit in payload.get("hits", []) if isinstance(hit, dict)],
        key=_pixabay_hit_score,
        reverse=True,
    )
    for hit in sorted_hits[:12]:
        remote_url = hit.get("webformatURL") or hit.get("largeImageURL")
        if not remote_url:
            continue
        assets.append(
            {
                "key": media_key(
                    {
                        "provider": "pixabay",
                        "provider_id": str(hit.get("id")),
                        "remote_url": remote_url,
                    }
                ),
                "remote_url": remote_url,
                "provider": "pixabay",
                "provider_id": str(hit.get("id")),
                "type": "image",
                "orientation": _pixabay_orientation(hit.get("imageWidth"), hit.get("imageHeight")),
                "tags": [tag.strip() for tag in str(hit.get("tags", "")).split(",") if tag.strip()],
                "width": hit.get("imageWidth"),
                "height": hit.get("imageHeight"),
                "attribution": hit.get("user"),
            }
        )
    return assets


def _fetch_and_store_story_images(session: Session, story: Story) -> list[Asset]:
    keywords = _extract_image_keywords(story)
    fetched = _fetch_pixabay_assets(keywords)
    existing = _list_existing_story_images(session, story.id)
    existing_by_url = {asset.remote_url: asset for asset in existing if asset.remote_url}
    fetched_assets: list[Asset] = []
    touched_assets: list[Asset] = []

    for result in fetched:
        remote_url = result["remote_url"]
        asset = existing_by_url.pop(remote_url, None)
        if asset is None:
            asset = Asset(
                story_id=story.id,
                type="image",
                remote_url=remote_url,
                source="remote",
                provider=result.get("provider"),
                provider_id=result.get("provider_id"),
                selected=False,
                orientation=result.get("orientation"),
                tags=result.get("tags"),
                width=result.get("width"),
                height=result.get("height"),
                attribution=result.get("attribution"),
            )
        else:
            asset.provider = result.get("provider")
            asset.provider_id = result.get("provider_id")
            asset.orientation = result.get("orientation")
            asset.tags = result.get("tags")
            asset.width = result.get("width")
            asset.height = result.get("height")
            asset.attribution = result.get("attribution")
        fetched_assets.append(asset)
        touched_assets.append(asset)

    for rank, asset in enumerate(fetched_assets):
        asset.rank = rank
        session.add(asset)

    for rank, asset in enumerate(existing_by_url.values(), start=len(fetched_assets)):
        asset.rank = rank
        session.add(asset)

    if touched_assets:
        session.commit()
        for asset in touched_assets:
            session.refresh(asset)

    return fetched_assets


def _estimate_seconds(text: str) -> int:
    return max(1, int(round(len(text) / CHARS_PER_SECOND)))


def _resolve_bundle_part_asset_map(bundle: AssetBundle, parts: list[StoryPart]) -> list[dict[str, int]]:
    return bundle_part_asset_map(bundle, parts)


def _validate_bundle_payload(
    story: Story,
    parts: list[StoryPart],
    *,
    asset_refs: list[dict[str, Any]],
    part_asset_map: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized_refs = normalize_asset_refs(asset_refs)
    if not normalized_refs:
        raise HTTPException(status_code=400, detail="Bundle must include at least one asset")
    refs_by_key = {asset["key"]: asset for asset in normalized_refs}
    parts_by_id = {part.id: part for part in parts}
    normalized_map: list[dict[str, Any]] = []
    for row in part_asset_map or []:
        if isinstance(row, PartMediaSelection):
            story_part_id = int(row.story_part_id)
            asset = normalize_media_ref(row.asset.model_dump())
        else:
            story_part_id = int(row["story_part_id"])
            asset = normalize_media_ref(row["asset"])
        normalized_map.append({"story_part_id": story_part_id, "asset": asset})
    if not normalized_map:
        normalized_map = ordered_part_asset_map(parts, normalized_refs)
    if parts and not normalized_map:
        raise HTTPException(status_code=400, detail="Bundle must assign an asset to each part")

    seen_parts: set[int] = set()
    for row in normalized_map:
        story_part_id = row["story_part_id"]
        asset = row["asset"]
        if story_part_id in seen_parts:
            raise HTTPException(status_code=400, detail="Duplicate story part in part_asset_map")
        if story_part_id not in parts_by_id:
            raise HTTPException(status_code=400, detail="Unknown story part in part_asset_map")
        if asset["key"] not in refs_by_key:
            raise HTTPException(status_code=400, detail="Unknown asset in part_asset_map")
        seen_parts.add(story_part_id)

    if len(seen_parts) != len(parts_by_id):
        raise HTTPException(status_code=400, detail="Bundle must cover every story part")

    normalized_asset_refs = list(dict.fromkeys([row["asset"]["key"] for row in normalized_map]))
    ordered_refs = [refs_by_key[key] for key in normalized_asset_refs]
    return ordered_refs, normalized_map


def _remote_asset_suffix(asset: dict[str, Any], response: requests.Response | None = None) -> str:
    remote_url = str(asset.get("remote_url") or "")
    suffix = Path(urlparse(remote_url).path).suffix.lower()
    if suffix:
        return suffix
    content_type = response.headers.get("content-type") if response is not None else None
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed:
            return guessed
    return ".jpg"


def _resolve_pixabay_asset_url(provider_id: str) -> str | None:
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


def _download_bundle_asset(story_id: int, asset: dict[str, Any]) -> tuple[str | None, str | None]:
    remote_url = asset.get("remote_url")
    if not remote_url:
        return asset.get("local_path"), None
    resolved_remote_url = remote_url
    response: requests.Response | None = None
    try:
        response = requests.get(remote_url, timeout=60, stream=True)
        response.raise_for_status()
    except requests.HTTPError:
        provider = str(asset.get("provider") or "")
        provider_id = str(asset.get("provider_id") or "")
        if provider == "pixabay" and provider_id:
            refreshed_url = _resolve_pixabay_asset_url(provider_id)
            if refreshed_url and refreshed_url != remote_url:
                resolved_remote_url = refreshed_url
                response = requests.get(refreshed_url, timeout=60, stream=True)
                response.raise_for_status()
            else:
                raise
        else:
            raise

    if response is None:
        raise FileNotFoundError("Asset download did not start")

    bundle_dir = settings.VISUALS_DIR / "stories" / str(story_id) / "bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    stem = str(asset.get("provider_id") or asset.get("key") or "selected-media")
    suffix = _remote_asset_suffix(asset, response=response)
    target = bundle_dir / f"{stem}{suffix}"
    tmp = target.with_suffix(f"{target.suffix}.tmp")
    with tmp.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)
        handle.flush()
        handle.close()
    tmp.replace(target)
    return str(target), resolved_remote_url


def _persist_bundle_assets(
    session: Session,
    story: Story,
    *,
    asset_refs: list[dict[str, Any]],
    part_asset_map: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized_refs = normalize_asset_refs(asset_refs)
    existing_assets = session.exec(select(Asset).where(Asset.story_id == story.id)).all()
    existing_by_provider = {
        (asset.provider or "", asset.provider_id or ""): asset
        for asset in existing_assets
        if asset.provider_id
    }
    existing_by_remote = {
        asset.remote_url: asset for asset in existing_assets if asset.remote_url
    }
    persisted_by_key: dict[str, dict[str, Any]] = {}

    for ref in normalized_refs:
        provider = str(ref.get("provider") or "")
        provider_id = str(ref.get("provider_id") or "")
        remote_url = ref.get("remote_url")
        asset = existing_by_provider.get((provider, provider_id)) if provider_id else None
        if asset is None and remote_url:
            asset = existing_by_remote.get(remote_url)

        local_path = ref.get("local_path")
        refreshed_remote_url = remote_url
        if provider == "pixabay" and remote_url:
            local_path, refreshed_remote_url = _download_bundle_asset(story.id, ref)

        if asset is None:
            asset = Asset(
                story_id=story.id,
                type=ref.get("type") or "image",
                remote_url=refreshed_remote_url,
                local_path=local_path,
                provider=provider or None,
                provider_id=provider_id or None,
                source="remote" if refreshed_remote_url else "local",
                selected=True,
                duration_ms=ref.get("duration_ms"),
                width=ref.get("width"),
                height=ref.get("height"),
                orientation=ref.get("orientation"),
                attribution=ref.get("attribution"),
                tags=ref.get("tags"),
            )
            session.add(asset)
            session.flush()
        else:
            asset.type = ref.get("type") or asset.type
            asset.remote_url = refreshed_remote_url
            asset.local_path = local_path or asset.local_path
            asset.provider = provider or asset.provider
            asset.provider_id = provider_id or asset.provider_id
            asset.source = "remote" if asset.remote_url else "local"
            asset.selected = True
            asset.duration_ms = ref.get("duration_ms")
            asset.width = ref.get("width")
            asset.height = ref.get("height")
            asset.orientation = ref.get("orientation")
            asset.attribution = ref.get("attribution")
            asset.tags = ref.get("tags")
            session.add(asset)
            session.flush()

        persisted_ref = asset_to_media_ref(asset)
        persisted_by_key[ref["key"]] = persisted_ref

    persisted_map = [
        {
            "story_part_id": int(row["story_part_id"]),
            "asset": persisted_by_key[row["asset"]["key"]],
        }
        for row in part_asset_map
    ]
    persisted_refs = [persisted_by_key[ref["key"]] for ref in normalized_refs if ref["key"] in persisted_by_key]
    return persisted_refs, persisted_map


def _sentence_spans(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    for match in SENTENCE_RE.finditer(text):
        spans.append((match.group().strip(), match.start(), match.end()))
    if spans and spans[-1][2] < len(text):
        spans.append((text[spans[-1][2]:].strip(), spans[-1][2], len(text)))
    elif not spans and text.strip():
        spans.append((text.strip(), 0, len(text)))
    return spans


def _snap_boundaries(text: str, start: int, end: int) -> tuple[int, int]:
    sentences = _sentence_spans(text)
    for _, sentence_start, sentence_end in sentences:
        if sentence_start <= start < sentence_end:
            start = sentence_start
        if sentence_start < end <= sentence_end:
            end = sentence_end
    if start >= end:
        raise ValueError("Invalid boundaries")
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


@router.get("/stories", response_model=list[StoryRead])
def list_stories(
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> list[Story]:
    query = select(Story)
    if status:
        query = query.where(Story.status == status)
    if q:
        query = query.where(Story.title.ilike(f"%{q}%"))
    query = query.order_by(Story.id.desc()).offset((page - 1) * limit).limit(limit)
    return session.exec(query).all()


@router.get("/stories/{story_id}", response_model=StoryRead)
def get_story(story_id: int, session: Session = Depends(get_session)) -> Story:
    return _get_story(session, story_id)


@router.post("/stories", response_model=StoryRead, status_code=status.HTTP_201_CREATED)
def create_story(story_in: StoryCreate, session: Session = Depends(get_session)) -> Story:
    payload = story_in.model_dump()
    payload.setdefault("status", StoryStatus.INGESTED.value)
    duplicate = find_duplicate_story(
        session,
        title=payload.get("title"),
        author=payload.get("author"),
        body_md=payload.get("body_md"),
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"detail": "duplicate", "story_id": duplicate.id},
        )
    story = Story(**payload)
    session.add(story)
    session.commit()
    session.refresh(story)
    return story


@router.patch("/stories/{story_id}", response_model=StoryRead)
def update_story(
    story_id: int,
    story_in: StoryUpdate,
    session: Session = Depends(get_session),
) -> Story:
    story = _get_story(session, story_id)
    data = story_in.model_dump(exclude_unset=True)
    next_status = data.get("status")
    if next_status and next_status != story.status and not can_transition_story(story.status, next_status):
        raise HTTPException(status_code=409, detail="Invalid story transition")
    for key, value in data.items():
        setattr(story, key, value)
    story.updated_at = datetime.now(timezone.utc)
    session.add(story)
    session.commit()
    session.refresh(story)
    return story


@router.delete("/stories/{story_id}")
def delete_story(story_id: int, session: Session = Depends(get_session)) -> Response:
    story = _get_story(session, story_id)
    session.delete(story)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stories/{story_id}/scripts", response_model=list[ScriptVersionRead])
def list_scripts(story_id: int, session: Session = Depends(get_session)) -> list[ScriptVersion]:
    _get_story(session, story_id)
    return session.exec(
        select(ScriptVersion)
        .where(ScriptVersion.story_id == story_id)
        .order_by(ScriptVersion.id.desc())
    ).all()


@router.post("/stories/{story_id}/script", response_model=ScriptGenerationAccepted, status_code=status.HTTP_202_ACCEPTED)
def generate_script(story_id: int, session: Session = Depends(get_session)) -> ScriptGenerationAccepted:
    story = _get_story(session, story_id)
    batch = enqueue_compat_script_generation(session, story)
    story.status = StoryStatus.GENERATING_SCRIPT.value
    story.updated_at = datetime.now(timezone.utc)
    session.add(story)
    session.commit()
    session.refresh(batch)
    return ScriptGenerationAccepted(batch_id=batch.id or 0, status=batch.status)


@router.get("/stories/{story_id}/parts", response_model=list[StoryPartRead])
def list_parts(story_id: int, session: Session = Depends(get_session)) -> list[StoryPart]:
    story = _get_story(session, story_id)
    query = select(StoryPart).where(StoryPart.story_id == story_id)
    if story.active_script_version_id:
        query = query.where(StoryPart.script_version_id == story.active_script_version_id)
    return session.exec(query.order_by(StoryPart.index)).all()


@router.put("/stories/{story_id}/parts", response_model=list[StoryPartRead])
def replace_parts(
    story_id: int,
    parts: list[PartInput],
    session: Session = Depends(get_session),
) -> list[StoryPart]:
    story = _get_story(session, story_id)
    script = None
    if story.active_script_version_id:
        script = session.get(ScriptVersion, story.active_script_version_id)
    if not script:
        script = run_compat_script_generation(session, story)
    for existing in session.exec(select(StoryPart).where(StoryPart.script_version_id == script.id)).all():
        session.delete(existing)
    part_models: list[StoryPart] = []
    if all(part.start_char is not None and part.end_char is not None for part in parts):
        if not story.body_md:
            raise HTTPException(status_code=400, detail="Story body is empty")
        built_parts = []
        previous_end = 0
        for idx, part in enumerate(parts, 1):
            start_char, end_char = _snap_boundaries(
                story.body_md,
                int(part.start_char or 0),
                int(part.end_char or 0),
            )
            if start_char < previous_end:
                raise HTTPException(status_code=400, detail="Invalid part boundaries")
            body_md = story.body_md[start_char:end_char].strip()
            est_seconds = _estimate_seconds(body_md)
            if est_seconds < MIN_PART_SECONDS or est_seconds > MAX_PART_SECONDS:
                raise HTTPException(status_code=400, detail="Part duration out of bounds")
            built_parts.append((idx, body_md, start_char, end_char, est_seconds, part.approved))
            previous_end = end_char
    else:
        cursor = 0
        full_text = " ".join((part.body_md or "").strip() for part in parts)
        built_parts = []
        for idx, part in enumerate(parts, 1):
            body_md = (part.body_md or "").strip()
            start_char = full_text.find(body_md, cursor)
            end_char = start_char + len(body_md) if start_char >= 0 else cursor + len(body_md)
            cursor = max(cursor, end_char)
            built_parts.append(
                (
                    idx,
                    body_md,
                    max(0, start_char),
                    max(0, end_char),
                    max(1, round(len(body_md.split()) / 2.6)),
                    part.approved,
                )
            )
    for idx, body_md, start_char, end_char, est_seconds, approved in built_parts:
        model = StoryPart(
            story_id=story.id,
            script_version_id=script.id,
            asset_bundle_id=story.active_asset_bundle_id,
            index=idx,
            body_md=body_md,
            source_text=body_md,
            script_text=body_md,
            est_seconds=est_seconds,
            start_char=start_char,
            end_char=end_char,
            approved=approved,
        )
        session.add(model)
        part_models.append(model)
    story.status = StoryStatus.APPROVED.value
    session.add(story)
    session.commit()
    return session.exec(
        select(StoryPart)
        .where(StoryPart.story_id == story_id)
        .order_by(StoryPart.index)
    ).all()


@router.get("/assets/library", response_model=list[AssetRead])
def list_asset_library(
    q: str | None = None,
    asset_type: str | None = Query(default=None, alias="type"),
    session: Session = Depends(get_session),
) -> list[Asset]:
    query = select(Asset).where(Asset.story_id.is_(None))
    if asset_type:
        query = query.where(Asset.type == asset_type)
    assets = session.exec(query.order_by(Asset.id.desc())).all()
    if not q:
        return assets
    terms = {term.lower() for term in q.split() if term.strip()}
    return [
        asset
        for asset in assets
        if terms.intersection(set(asset.tags or []))
        or any(term in (asset.local_path or "").lower() for term in terms)
    ]


@router.post("/stories/{story_id}/assets/index", response_model=list[MediaReference])
def index_story_assets(
    story_id: int,
    page: int = Query(default=1, ge=1),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    story = _get_story(session, story_id)
    return normalize_asset_refs(_fetch_pixabay_assets(_extract_image_keywords(story), page=page))


@router.get("/stories/{story_id}/assets", response_model=list[MediaReference])
def list_story_assets(
    story_id: int,
    page: int = Query(default=1, ge=1),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    story = _get_story(session, story_id)
    return normalize_asset_refs(_fetch_pixabay_assets(_extract_image_keywords(story), page=page))


@router.get("/stories/{story_id}/asset-bundles", response_model=list[AssetBundleRead])
def list_asset_bundles(story_id: int, session: Session = Depends(get_session)) -> list[AssetBundle]:
    story = _get_story(session, story_id)
    parts = session.exec(
        select(StoryPart)
        .where(
            StoryPart.story_id == story_id,
            StoryPart.script_version_id == story.active_script_version_id,
        )
        .order_by(StoryPart.index)
    ).all()
    bundles = session.exec(
        select(AssetBundle)
        .where(AssetBundle.story_id == story_id)
        .order_by(AssetBundle.id.desc())
    ).all()
    for bundle in bundles:
        bundle.asset_refs = bundle_asset_refs(bundle, session)
        bundle.part_asset_map = bundle_part_asset_map(bundle, parts, session)
    return bundles


@router.post("/stories/{story_id}/asset-bundles", response_model=AssetBundleRead)
def create_bundle(
    story_id: int,
    bundle_in: AssetBundleCreate,
    session: Session = Depends(get_session),
) -> AssetBundle:
    story = _get_story(session, story_id)
    parts = session.exec(
        select(StoryPart).where(
            StoryPart.story_id == story_id,
            StoryPart.script_version_id == story.active_script_version_id,
        )
        .order_by(StoryPart.index)
    ).all()
    part_asset_rows = [row.model_dump() if isinstance(row, PartMediaSelection) else row for row in (bundle_in.part_asset_map or [])]
    asset_refs, part_asset_map = _validate_bundle_payload(
        story,
        parts,
        asset_refs=[asset.model_dump() if isinstance(asset, MediaReference) else asset for asset in bundle_in.asset_refs],
        part_asset_map=part_asset_rows,
    )
    persisted_asset_refs, persisted_part_asset_map = _persist_bundle_assets(
        session,
        story,
        asset_refs=asset_refs,
        part_asset_map=part_asset_map,
    )
    bundle = create_asset_bundle(
        session,
        story,
        name=bundle_in.name,
        asset_refs=persisted_asset_refs,
        part_asset_map=persisted_part_asset_map,
        variant=bundle_in.variant,
        music_policy=bundle_in.music_policy,
        music_track=bundle_in.music_track,
    )
    session.commit()
    session.refresh(bundle)
    return bundle


@router.get("/render-presets", response_model=list[RenderPresetRead])
def list_presets(session: Session = Depends(get_session)) -> list[RenderPreset]:
    ensure_default_presets(session)
    return session.exec(select(RenderPreset).order_by(RenderPreset.id)).all()


@router.post("/stories/{story_id}/releases", response_model=list[ReleaseRead])
def create_releases(
    story_id: int,
    payload: ReleaseCreate,
    session: Session = Depends(get_session),
) -> list[ReleaseRead]:
    story = _get_story(session, story_id)
    ensure_default_presets(session)
    preset = session.exec(select(RenderPreset).where(RenderPreset.slug == payload.preset_slug)).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Render preset not found")
    platforms = payload.platforms or active_publish_platforms(session)
    for platform in platforms:
        validate_release_platform(platform, preset.variant, session)
    bundle_id = payload.asset_bundle_id or story.active_asset_bundle_id
    if not bundle_id:
        raise HTTPException(status_code=400, detail="Active asset bundle required")
    bundle = session.get(AssetBundle, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Asset bundle not found")
    parts_query = select(StoryPart).where(StoryPart.story_id == story_id)
    if story.active_script_version_id:
        parts_query = parts_query.where(StoryPart.script_version_id == story.active_script_version_id)
    parts = session.exec(parts_query.order_by(StoryPart.index)).all()
    bundle.asset_refs = bundle_asset_refs(bundle, session)
    bundle.part_asset_map = bundle_part_asset_map(bundle, parts, session)
    if parts and len(bundle.part_asset_map) != len(parts):
        raise HTTPException(status_code=400, detail="Asset bundle must cover every story part")
    releases, _jobs = create_short_releases(
        session,
        story,
        platforms=platforms,
        preset=preset,
        asset_bundle=bundle,
        script_version=session.get(ScriptVersion, story.active_script_version_id) if story.active_script_version_id else None,
    )
    session.commit()
    return _serialize_releases(session, releases)


@router.get("/stories/{story_id}/releases", response_model=list[ReleaseRead])
def list_releases(story_id: int, session: Session = Depends(get_session)) -> list[ReleaseRead]:
    _get_story(session, story_id)
    releases = session.exec(
        select(Release)
        .where(Release.story_id == story_id)
        .order_by(Release.id.desc())
    ).all()
    return _serialize_releases(session, releases)


@router.get("/releases/queue", response_model=list[ReleaseRead])
def release_queue(session: Session = Depends(get_session)) -> list[ReleaseRead]:
    recent_published_cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.EARLY_SIGNAL_WINDOW_HOURS)
    releases = session.exec(
        select(Release)
        .where(
            or_(
                Release.status.in_(
                    [
                        ReleaseStatus.READY.value,
                        ReleaseStatus.APPROVED.value,
                        ReleaseStatus.SCHEDULED.value,
                        ReleaseStatus.PUBLISHING.value,
                        ReleaseStatus.MANUAL_HANDOFF.value,
                        ReleaseStatus.ERRORED.value,
                    ]
                ),
                and_(
                    Release.status == ReleaseStatus.PUBLISHED.value,
                    Release.published_at.is_not(None),
                    Release.published_at >= recent_published_cutoff,
                ),
            )
        )
        .order_by(Release.publish_at.asc().nullslast(), Release.published_at.desc().nullslast(), Release.id.asc())
    ).all()
    return _serialize_releases(session, releases)


@router.post("/releases/{release_id}/approve", response_model=ReleaseRead)
def approve_release(
    release_id: int,
    payload: ReleaseApprovalUpdate,
    session: Session = Depends(get_session),
) -> ReleaseRead:
    release = session.get(Release, release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    validate_release_platform(release.platform, release.variant, session)
    if not release.render_artifact_id:
        raise HTTPException(status_code=400, detail="Release is missing a render artifact")
    if payload.title is not None:
        release.title = payload.title.strip()
    if payload.description is not None:
        release.description = payload.description.strip()
    if payload.hashtags is not None:
        release.hashtags = payload.hashtags
    publish_at = payload.publish_at
    if publish_at and publish_at.tzinfo is None:
        publish_at = publish_at.replace(tzinfo=timezone.utc)
    release.publish_at = publish_at
    release.approved_at = datetime.now(timezone.utc)
    release.approval_status = PublishApprovalStatus.APPROVED.value
    release.delivery_mode = delivery_mode_for_platform(release.platform)
    _sync_release_state(release, approval_payload_status(publish_at))
    release.last_error = None
    ensure_publish_job(
        session,
        release,
        not_before=publish_at,
        payload={
            "delivery_mode": release.delivery_mode,
            "variant": release.variant,
        },
    )
    session.add(release)
    session.commit()
    return release_read(session, release)


@router.post("/releases/{release_id}/retry", response_model=ReleaseRead)
def retry_release(
    release_id: int,
    session: Session = Depends(get_session),
) -> ReleaseRead:
    release = session.get(Release, release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    if release.status != ReleaseStatus.ERRORED.value:
        raise HTTPException(status_code=409, detail="Only errored releases can be retried")
    next_status = approval_payload_status(release.publish_at)
    _sync_release_state(release, next_status)
    release.last_error = None
    ensure_publish_job(
        session,
        release,
        not_before=release.publish_at,
        payload={
            "delivery_mode": release.delivery_mode,
            "variant": release.variant,
            "retry": True,
        },
    )
    session.add(release)
    session.commit()
    return release_read(session, release)


@router.post("/releases/{release_id}/complete-manual-publish", response_model=ReleaseRead)
def complete_manual_publish(
    release_id: int,
    payload: PublishUpdate,
    session: Session = Depends(get_session),
) -> ReleaseRead:
    release = session.get(Release, release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    if release.delivery_mode != "manual":
        raise HTTPException(status_code=409, detail="Release is not a manual handoff")
    if release.status != ReleaseStatus.MANUAL_HANDOFF.value:
        raise HTTPException(status_code=409, detail="Release is not ready for manual completion")
    if not payload.platform_video_id:
        raise HTTPException(status_code=400, detail="platform_video_id is required")
    release.platform_video_id = payload.platform_video_id
    release.published_at = datetime.now(timezone.utc)
    release.provider_metadata = {
        **(release.provider_metadata or {}),
        **({"manual_notes": payload.notes} if payload.notes else {}),
        "manual_handoff": manual_handoff_metadata(
            release,
            release_read(session, release).signed_asset_url or "",
        ),
    }
    _sync_release_state(release, ReleaseStatus.PUBLISHED.value)
    publish_job = resolve_publish_job(session, release.id or 0)
    if publish_job:
        publish_job.status = PublishJobStatus.PUBLISHED.value
        publish_job.result = {
            **(publish_job.result or {}),
            "manual_completion": True,
            "platform_video_id": payload.platform_video_id,
        }
        session.add(publish_job)
    session.add(release)
    maybe_mark_story_published(session, release.story_id)
    session.commit()
    return release_read(session, release)


@router.post("/releases/{release_id}/clear", response_model=ReleaseRead)
def clear_release_from_queue(
    release_id: int,
    session: Session = Depends(get_session),
) -> ReleaseRead:
    release = session.get(Release, release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    if release.status == ReleaseStatus.PUBLISHED.value:
        return release_read(session, release)

    cleared_at = datetime.now(timezone.utc)
    release.last_error = None
    release.approval_status = PublishApprovalStatus.APPROVED.value
    release.published_at = cleared_at
    release.provider_metadata = {
        **(release.provider_metadata or {}),
        "queue_cleared": True,
        "queue_cleared_at": cleared_at.isoformat(),
    }
    _sync_release_state(release, ReleaseStatus.PUBLISHED.value)

    publish_job = resolve_publish_job(session, release.id or 0)
    if publish_job:
        publish_job.status = PublishJobStatus.PUBLISHED.value
        publish_job.error_class = None
        publish_job.error_message = None
        publish_job.stderr_snippet = None
        publish_job.result = {
            **(publish_job.result or {}),
            "queue_cleared": True,
            "queue_cleared_at": cleared_at.isoformat(),
        }
        session.add(publish_job)

    session.add(release)
    maybe_mark_story_published(session, release.story_id)
    session.commit()
    return release_read(session, release)


@router.post("/releases/reschedule", response_model=ReleaseRescheduleResult)
def reschedule_release_queue(
    session: Session = Depends(get_session),
) -> ReleaseRescheduleResult:
    eligible_statuses = [
        ReleaseStatus.READY.value,
        ReleaseStatus.APPROVED.value,
        ReleaseStatus.SCHEDULED.value,
        ReleaseStatus.MANUAL_HANDOFF.value,
        ReleaseStatus.ERRORED.value,
    ]
    releases = session.exec(
        select(Release)
        .where(
            Release.variant == RenderVariant.SHORT.value,
            Release.status.in_(eligible_statuses),
        )
        .order_by(Release.publish_at.asc().nullslast(), Release.id.asc())
    ).all()

    if not releases:
        return ReleaseRescheduleResult(total_rescheduled=0, releases=[])

    slots = short_release_schedule_from(datetime.now(timezone.utc), count=len(releases))
    for release, publish_at in zip(releases, slots, strict=True):
        release.publish_at = publish_at
        release.last_error = None
        if release.approval_status == PublishApprovalStatus.APPROVED.value:
            _sync_release_state(release, approval_payload_status(publish_at))
        ensure_publish_job(
            session,
            release,
            not_before=publish_at,
            payload={
                "delivery_mode": release.delivery_mode,
                "variant": release.variant,
                "rescheduled": True,
            },
        )
        session.add(release)

    session.commit()
    return ReleaseRescheduleResult(
        total_rescheduled=len(releases),
        releases=[release_read(session, release) for release in releases],
    )


@router.post("/stories/{story_id}/compilations", response_model=CompilationRead)
def create_compilation(
    story_id: int,
    payload: CompilationCreate,
    session: Session = Depends(get_session),
) -> Compilation:
    story = _get_story(session, story_id)
    ensure_default_presets(session)
    preset = session.exec(select(RenderPreset).where(RenderPreset.slug == payload.preset_slug)).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Render preset not found")
    for platform in payload.platforms:
        validate_release_platform(platform, RenderVariant.WEEKLY.value, session)
    compilation, _job = create_weekly_compilation(session, story, preset=preset)
    story_short_releases = session.exec(
        select(Release)
        .where(
            Release.story_id == story.id,
            Release.variant == RenderVariant.SHORT.value,
            Release.publish_at.is_not(None),
        )
        .order_by(Release.publish_at.desc())
    ).all()
    story_schedule_end = next(
        (release.publish_at for release in story_short_releases if release.publish_at),
        None,
    )
    metadata = generate_release_metadata(
        story,
        variant=RenderVariant.WEEKLY.value,
    )
    release = Release(
        story_id=story.id,
        compilation_id=compilation.id,
        platform=payload.platforms[0] if payload.platforms else "youtube",
        variant=RenderVariant.WEEKLY.value,
        title=str(metadata["title"]),
        description=str(metadata["description"]),
        hashtags=list(metadata["hashtags"]),
        status=ReleaseStatus.DRAFT.value,
        publish_status=ReleaseStatus.DRAFT.value,
        approval_status=PublishApprovalStatus.APPROVED.value,
        delivery_mode=delivery_mode_for_platform(payload.platforms[0] if payload.platforms else "youtube"),
        publish_at=weekly_compilation_schedule(session, after=story_schedule_end),
        approved_at=datetime.now(timezone.utc),
    )
    session.add(release)
    story.status = StoryStatus.QUEUED.value
    session.add(story)
    session.commit()
    session.refresh(compilation)
    return compilation


@router.get("/stories/{story_id}/compilations", response_model=list[CompilationRead])
def list_compilations(story_id: int, session: Session = Depends(get_session)) -> list[Compilation]:
    _get_story(session, story_id)
    return session.exec(
        select(Compilation)
        .where(Compilation.story_id == story_id)
        .order_by(Compilation.id.desc())
    ).all()


@router.get("/stories/{story_id}/artifacts", response_model=list[RenderArtifactRead])
def list_artifacts(story_id: int, session: Session = Depends(get_session)) -> list[RenderArtifact]:
    _get_story(session, story_id)
    return session.exec(
        select(RenderArtifact)
        .where(RenderArtifact.story_id == story_id)
        .order_by(RenderArtifact.id.desc())
    ).all()


@router.get("/stories/{story_id}/overview")
def story_overview(story_id: int, session: Session = Depends(get_session)) -> dict[str, Any]:
    story = _get_story(session, story_id)
    script = session.get(ScriptVersion, story.active_script_version_id) if story.active_script_version_id else None
    parts = session.exec(
        select(StoryPart)
        .where(
            StoryPart.story_id == story_id,
            StoryPart.script_version_id == story.active_script_version_id,
        )
        .order_by(StoryPart.index)
    ).all()
    script_versions = session.exec(
        select(ScriptVersion)
        .where(ScriptVersion.story_id == story_id)
        .order_by(ScriptVersion.id.desc())
    ).all()
    script_batches = session.exec(
        select(ScriptBatch)
        .where(ScriptBatch.story_id == story_id)
        .order_by(ScriptBatch.id.desc())
    ).all()
    bundles = session.exec(
        select(AssetBundle)
        .where(AssetBundle.story_id == story_id)
        .order_by(AssetBundle.id.desc())
    ).all()
    for bundle in bundles:
        bundle.asset_refs = bundle_asset_refs(bundle, session)
        bundle.part_asset_map = bundle_part_asset_map(bundle, parts, session)
    releases = session.exec(
        select(Release).where(Release.story_id == story_id).order_by(Release.id.desc())
    ).all()
    return {
        "story": StoryRead.model_validate(story).model_dump(),
        "active_script": ScriptVersionRead.model_validate(script).model_dump() if script else None,
        "script_versions": [ScriptVersionRead.model_validate(item).model_dump() for item in script_versions],
        "script_batches": [ScriptBatchRead.model_validate(item).model_dump() for item in script_batches],
        "parts": [StoryPartRead.model_validate(part).model_dump() for part in parts],
        "asset_bundles": [AssetBundleRead.model_validate(bundle).model_dump() for bundle in bundles],
        "releases": [release_read(session, release).model_dump() for release in releases],
        "artifacts": [
            RenderArtifactRead.model_validate(artifact).model_dump()
            for artifact in session.exec(
                select(RenderArtifact)
                .where(RenderArtifact.story_id == story_id)
                .order_by(RenderArtifact.id.desc())
            ).all()
        ],
    }
