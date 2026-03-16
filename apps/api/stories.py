"""Canonical operator-facing API routes."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
import requests

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlmodel import Session, select

from shared.config import settings
from shared.workflow import ReleaseStatus, RenderVariant, StoryStatus, can_transition_story

from .db import get_session
from .models import (
    Asset,
    AssetBundle,
    AssetBundleRead,
    AssetRead,
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
    Story,
    StoryCreate,
    StoryPart,
    StoryPartRead,
    StoryRead,
    StoryUpdate,
)
from .pipeline import (
    create_asset_bundle,
    create_short_releases,
    create_weekly_compilation,
    ensure_default_presets,
    upsert_script,
)

router = APIRouter(tags=["stories"])

WORDS_PER_MINUTE = 160
WORDS_PER_SECOND = WORDS_PER_MINUTE / 60
CHARS_PER_WORD = 5
CHARS_PER_SECOND = WORDS_PER_SECOND * CHARS_PER_WORD
MIN_PART_SECONDS = 30
MAX_PART_SECONDS = 75
SENTENCE_RE = re.compile(r"[^.!?]+[.!?](?:\s+|$)")
REMOTE_IMAGE_KEYWORDS = (
    "shadow",
    "hallway",
    "forest",
    "basement",
    "attic",
    "fog",
    "night",
    "road",
    "window",
    "cabin",
    "lake",
    "storm",
    "door",
    "apartment",
    "corridor",
    "graveyard",
    "empty",
    "abandoned",
    "woods",
    "house",
)


class PartInput(BaseModel):
    body_md: str | None = None
    approved: bool = True
    start_char: int | None = None
    end_char: int | None = None


class AssetBundleCreate(BaseModel):
    name: str = "Primary bundle"
    asset_ids: list[int]
    part_asset_map: list[dict[str, int]] | None = None
    variant: str = RenderVariant.SHORT.value
    music_policy: str = "first"
    music_track: str | None = None


class ReleaseCreate(BaseModel):
    platforms: list[str] = ["youtube", "tiktok", "instagram"]
    preset_slug: str = "short-form"
    asset_bundle_id: int | None = None


class CompilationCreate(BaseModel):
    preset_slug: str = "weekly-full"
    platforms: list[str] = ["youtube"]


class PublishUpdate(BaseModel):
    platform_video_id: str | None = None


def _get_story(session: Session, story_id: int) -> Story:
    story = session.get(Story, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


def _extract_image_keywords(story: Story) -> str:
    text = f"{story.title} {story.body_md or ''}".lower()
    matched = [keyword for keyword in REMOTE_IMAGE_KEYWORDS if keyword in text]
    title_words = [
        token
        for token in re.findall(r"[a-zA-Z]{4,}", story.title.lower())
        if token not in matched
    ]
    keywords = list(dict.fromkeys([*matched, *title_words[:4]]))
    return " ".join(keywords[:6]) or story.title


def _list_existing_story_images(session: Session, story_id: int) -> list[Asset]:
    return session.exec(
        select(Asset)
        .where(Asset.story_id == story_id, Asset.type == "image")
        .order_by(Asset.rank.is_(None), Asset.rank, Asset.id.desc())
    ).all()


def _fetch_pixabay_assets(keywords: str) -> list[dict[str, Any]]:
    if not settings.PIXABAY_API_KEY:
        return []
    try:
        response = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": settings.PIXABAY_API_KEY,
                "q": keywords,
                "image_type": "photo",
                "orientation": "vertical",
                "per_page": 12,
                "safesearch": "true",
            },
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    assets: list[dict[str, Any]] = []
    for hit in payload.get("hits", []):
        remote_url = hit.get("webformatURL") or hit.get("largeImageURL")
        if not remote_url:
            continue
        assets.append(
            {
                "remote_url": remote_url,
                "provider": "pixabay",
                "provider_id": str(hit.get("id")),
                "type": "image",
                "orientation": "portrait" if (hit.get("imageHeight", 0) or 0) >= (hit.get("imageWidth", 0) or 0) else "landscape",
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
    existing_urls = {asset.remote_url for asset in existing if asset.remote_url}
    created: list[Asset] = []
    next_rank = len(existing)

    for result in fetched:
        remote_url = result["remote_url"]
        if remote_url in existing_urls:
            continue
        asset = Asset(
            story_id=story.id,
            type="image",
            remote_url=remote_url,
            source="remote",
            provider=result.get("provider"),
            provider_id=result.get("provider_id"),
            selected=False,
            rank=next_rank,
            orientation=result.get("orientation"),
            tags=result.get("tags"),
            width=result.get("width"),
            height=result.get("height"),
            attribution=result.get("attribution"),
        )
        session.add(asset)
        created.append(asset)
        existing_urls.add(remote_url)
        next_rank += 1

    if created:
        session.commit()
        for asset in created:
            session.refresh(asset)

    return _list_existing_story_images(session, story.id)


def _estimate_seconds(text: str) -> int:
    return max(1, int(round(len(text) / CHARS_PER_SECOND)))


def _ordered_part_asset_map(parts: list[StoryPart], asset_ids: list[int]) -> list[dict[str, int]]:
    if not parts or not asset_ids:
        return []
    mapped: list[dict[str, int]] = []
    fallback_asset_id = asset_ids[0]
    for index, part in enumerate(parts):
        asset_id = asset_ids[index] if index < len(asset_ids) else fallback_asset_id
        mapped.append({"story_part_id": part.id, "asset_id": asset_id})
    return mapped


def _normalize_part_asset_map(raw_map: list[dict[str, int]] | None) -> list[dict[str, int]]:
    if not raw_map:
        return []
    normalized: list[dict[str, int]] = []
    for row in raw_map:
        story_part_id = int(row["story_part_id"])
        asset_id = int(row["asset_id"])
        normalized.append({"story_part_id": story_part_id, "asset_id": asset_id})
    return normalized


def _resolve_bundle_part_asset_map(bundle: AssetBundle, parts: list[StoryPart]) -> list[dict[str, int]]:
    part_asset_map = _normalize_part_asset_map(bundle.part_asset_map)
    if part_asset_map:
        return part_asset_map
    return _ordered_part_asset_map(parts, bundle.asset_ids)


def _validate_bundle_payload(
    story: Story,
    parts: list[StoryPart],
    assets: list[Asset],
    *,
    asset_ids: list[int],
    part_asset_map: list[dict[str, int]] | None,
) -> tuple[list[int], list[dict[str, int]]]:
    asset_ids = [int(asset_id) for asset_id in asset_ids]
    assets_by_id = {asset.id: asset for asset in assets}
    if len(assets_by_id) != len(asset_ids):
        raise HTTPException(status_code=400, detail="Unknown asset id in bundle")
    if any(asset.story_id not in {None, story.id} for asset in assets):
        raise HTTPException(status_code=400, detail="Asset does not belong to story")

    parts_by_id = {part.id: part for part in parts}
    normalized_map = _normalize_part_asset_map(part_asset_map)
    if not normalized_map:
        normalized_map = _ordered_part_asset_map(parts, asset_ids)
    if parts and not normalized_map:
        raise HTTPException(status_code=400, detail="Bundle must assign an asset to each part")

    seen_parts: set[int] = set()
    for row in normalized_map:
        story_part_id = row["story_part_id"]
        asset_id = row["asset_id"]
        if story_part_id in seen_parts:
            raise HTTPException(status_code=400, detail="Duplicate story part in part_asset_map")
        if story_part_id not in parts_by_id:
            raise HTTPException(status_code=400, detail="Unknown story part in part_asset_map")
        if asset_id not in assets_by_id:
            raise HTTPException(status_code=400, detail="Unknown asset id in part_asset_map")
        seen_parts.add(story_part_id)

    if len(seen_parts) != len(parts_by_id):
        raise HTTPException(status_code=400, detail="Bundle must cover every story part")

    normalized_asset_ids = list(dict.fromkeys([row["asset_id"] for row in normalized_map]))
    if not normalized_asset_ids:
        raise HTTPException(status_code=400, detail="Bundle must include at least one asset")
    return normalized_asset_ids, normalized_map


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


@router.post("/stories/{story_id}/script", response_model=ScriptVersionRead)
def generate_script(story_id: int, session: Session = Depends(get_session)) -> ScriptVersion:
    story = _get_story(session, story_id)
    script = upsert_script(session, story)
    session.commit()
    session.refresh(script)
    return script


@router.get("/stories/{story_id}/parts", response_model=list[StoryPartRead])
def list_parts(story_id: int, session: Session = Depends(get_session)) -> list[StoryPart]:
    _get_story(session, story_id)
    return session.exec(
        select(StoryPart)
        .where(StoryPart.story_id == story_id)
        .order_by(StoryPart.index)
    ).all()


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
        script = upsert_script(session, story)
    for existing in session.exec(select(StoryPart).where(StoryPart.story_id == story_id)).all():
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


@router.post("/stories/{story_id}/assets/index", response_model=list[AssetRead])
def index_story_assets(story_id: int, session: Session = Depends(get_session)) -> list[Asset]:
    story = _get_story(session, story_id)
    return _fetch_and_store_story_images(session, story)


@router.get("/stories/{story_id}/assets", response_model=list[AssetRead])
def list_story_assets(story_id: int, session: Session = Depends(get_session)) -> list[Asset]:
    story = _get_story(session, story_id)
    existing = _list_existing_story_images(session, story_id)
    if existing:
        return existing
    return _fetch_and_store_story_images(session, story)


@router.get("/stories/{story_id}/asset-bundles", response_model=list[AssetBundleRead])
def list_asset_bundles(story_id: int, session: Session = Depends(get_session)) -> list[AssetBundle]:
    _get_story(session, story_id)
    parts = session.exec(
        select(StoryPart)
        .where(StoryPart.story_id == story_id)
        .order_by(StoryPart.index)
    ).all()
    bundles = session.exec(
        select(AssetBundle)
        .where(AssetBundle.story_id == story_id)
        .order_by(AssetBundle.id.desc())
    ).all()
    for bundle in bundles:
        bundle.part_asset_map = _resolve_bundle_part_asset_map(bundle, parts)
    return bundles


@router.post("/stories/{story_id}/asset-bundles", response_model=AssetBundleRead)
def create_bundle(
    story_id: int,
    bundle_in: AssetBundleCreate,
    session: Session = Depends(get_session),
) -> AssetBundle:
    story = _get_story(session, story_id)
    parts = session.exec(
        select(StoryPart)
        .where(StoryPart.story_id == story_id)
        .order_by(StoryPart.index)
    ).all()
    requested_asset_ids = bundle_in.asset_ids or [
        int(row["asset_id"]) for row in (bundle_in.part_asset_map or [])
    ]
    assets = session.exec(select(Asset).where(Asset.id.in_(requested_asset_ids))).all()
    asset_ids, part_asset_map = _validate_bundle_payload(
        story,
        parts,
        assets,
        asset_ids=requested_asset_ids,
        part_asset_map=bundle_in.part_asset_map,
    )
    bundle = create_asset_bundle(
        session,
        story,
        name=bundle_in.name,
        asset_ids=asset_ids,
        part_asset_map=part_asset_map,
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
) -> list[Release]:
    story = _get_story(session, story_id)
    ensure_default_presets(session)
    preset = session.exec(select(RenderPreset).where(RenderPreset.slug == payload.preset_slug)).first()
    if not preset:
        raise HTTPException(status_code=404, detail="Render preset not found")
    bundle_id = payload.asset_bundle_id or story.active_asset_bundle_id
    if not bundle_id:
        raise HTTPException(status_code=400, detail="Active asset bundle required")
    bundle = session.get(AssetBundle, bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Asset bundle not found")
    parts = session.exec(
        select(StoryPart)
        .where(StoryPart.story_id == story_id)
        .order_by(StoryPart.index)
    ).all()
    bundle.part_asset_map = _resolve_bundle_part_asset_map(bundle, parts)
    if parts and len(bundle.part_asset_map) != len(parts):
        raise HTTPException(status_code=400, detail="Asset bundle must cover every story part")
    releases, _jobs = create_short_releases(
        session,
        story,
        platforms=payload.platforms,
        preset=preset,
        asset_bundle=bundle,
    )
    session.commit()
    return releases


@router.get("/stories/{story_id}/releases", response_model=list[ReleaseRead])
def list_releases(story_id: int, session: Session = Depends(get_session)) -> list[Release]:
    _get_story(session, story_id)
    return session.exec(
        select(Release)
        .where(Release.story_id == story_id)
        .order_by(Release.id.desc())
    ).all()


@router.get("/releases/queue", response_model=list[ReleaseRead])
def release_queue(session: Session = Depends(get_session)) -> list[Release]:
    return session.exec(
        select(Release)
        .where(Release.status == ReleaseStatus.READY.value)
        .order_by(Release.id.asc())
    ).all()


@router.post("/releases/{release_id}/publish", response_model=ReleaseRead)
def publish_release(
    release_id: int,
    payload: PublishUpdate,
    session: Session = Depends(get_session),
) -> Release:
    release = session.get(Release, release_id)
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    release.status = ReleaseStatus.PUBLISHED.value
    release.published_at = datetime.now(timezone.utc)
    if payload.platform_video_id:
        release.description = f"{release.description}\n\nPlatform video id: {payload.platform_video_id}".strip()
    session.add(release)
    story = session.get(Story, release.story_id)
    if story:
        story.status = StoryStatus.PUBLISHED.value
        session.add(story)
    session.commit()
    session.refresh(release)
    return release


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
    compilation, _job = create_weekly_compilation(session, story, preset=preset)
    release = Release(
        story_id=story.id,
        compilation_id=compilation.id,
        platform=payload.platforms[0] if payload.platforms else "youtube",
        variant=RenderVariant.WEEKLY.value,
        title=compilation.title,
        description=f"Weekly full story cut for {story.title}",
        hashtags=["weekly", "scarystories", "youtube"],
        status=ReleaseStatus.DRAFT.value,
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
        .where(StoryPart.story_id == story_id)
        .order_by(StoryPart.index)
    ).all()
    bundles = session.exec(
        select(AssetBundle)
        .where(AssetBundle.story_id == story_id)
        .order_by(AssetBundle.id.desc())
    ).all()
    for bundle in bundles:
        bundle.part_asset_map = _resolve_bundle_part_asset_map(bundle, parts)
    releases = session.exec(
        select(Release).where(Release.story_id == story_id).order_by(Release.id.desc())
    ).all()
    return {
        "story": StoryRead.model_validate(story).model_dump(),
        "active_script": ScriptVersionRead.model_validate(script).model_dump() if script else None,
        "parts": [StoryPartRead.model_validate(part).model_dump() for part in parts],
        "asset_bundles": [AssetBundleRead.model_validate(bundle).model_dump() for bundle in bundles],
        "releases": [ReleaseRead.model_validate(release).model_dump() for release in releases],
        "artifacts": [
            RenderArtifactRead.model_validate(artifact).model_dump()
            for artifact in session.exec(
                select(RenderArtifact)
                .where(RenderArtifact.story_id == story_id)
                .order_by(RenderArtifact.id.desc())
            ).all()
        ],
    }
