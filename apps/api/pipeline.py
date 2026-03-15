"""Helpers for script generation, media indexing, and render job creation."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable

import requests
from sqlmodel import Session, select

from shared.config import settings
from shared.workflow import JobStatus, ReleaseStatus, RenderVariant, StoryStatus

from .models import (
    Asset,
    AssetBundle,
    Compilation,
    Job,
    Release,
    RenderPreset,
    ScriptVersion,
    Story,
    StoryPart,
)

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
WORDS_PER_SECOND = 2.6
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}


def estimate_seconds(text: str) -> int:
    words = len([word for word in text.split() if word.strip()])
    return max(1, round(words / WORDS_PER_SECOND))


def split_sentences(text: str, target_seconds: int = 55) -> list[tuple[str, int, int]]:
    sentences = [segment.strip() for segment in SENTENCE_RE.split(text.strip()) if segment.strip()]
    if not sentences:
        return []
    target_words = max(1, round(target_seconds * WORDS_PER_SECOND))
    parts: list[tuple[str, int, int]] = []
    current: list[str] = []
    current_words = 0
    index = 1
    for sentence in sentences:
        words = len(sentence.split())
        if current and current_words + words > target_words:
            body = " ".join(current).strip()
            parts.append((body, index, estimate_seconds(body)))
            index += 1
            current = [sentence]
            current_words = words
        else:
            current.append(sentence)
            current_words += words
    if current:
        body = " ".join(current).strip()
        parts.append((body, index, estimate_seconds(body)))
    return parts


def _cleanup_source(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"^\s*TL;DR:.*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _heuristic_first_person(text: str, title: str) -> dict[str, str]:
    body = _cleanup_source(text)
    sentences = [s.strip() for s in SENTENCE_RE.split(body) if s.strip()]
    if not sentences:
        sentences = [body]
    rewritten: list[str] = []
    for sentence in sentences:
        line = sentence
        if not re.match(r"^(I|My|We|Our)\b", line):
            line = f"I remember {line[0].lower() + line[1:]}" if line else line
        rewritten.append(line)
    narration = " ".join(rewritten).strip()
    hook = f"I should have left sooner. {title}".strip()
    outro = "If I ever tell this story again, it means I made it out."
    return {
        "hook": hook,
        "narration_text": narration,
        "outro": outro,
        "model_name": "rule_based",
    }


def generate_script_payload(story: Story) -> dict[str, str]:
    """Generate a first-person narration script for a story."""
    source_text = story.body_md or story.title
    if not source_text:
        return _heuristic_first_person("", story.title)

    if not settings.OPENAI_API_KEY:
        return _heuristic_first_person(source_text, story.title)

    prompt = (
        "Rewrite the Reddit story into a first-person creepy voiceover script. "
        "Return strict JSON with keys hook, narration_text, outro. "
        "Keep it concise, cinematic, and suitable for short-form narration."
    )
    payload = {
        "model": settings.OPENAI_SCRIPT_MODEL,
        "input": [
            {"role": "system", "content": [{"type": "text", "text": prompt}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "title": story.title,
                                "author": story.author,
                                "source_url": story.source_url,
                                "text": source_text,
                            }
                        ),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "story_script",
                "schema": {
                    "type": "object",
                    "properties": {
                        "hook": {"type": "string"},
                        "narration_text": {"type": "string"},
                        "outro": {"type": "string"},
                    },
                    "required": ["hook", "narration_text", "outro"],
                    "additionalProperties": False,
                },
            }
        },
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("output_text")
        if isinstance(text, str):
            parsed = json.loads(text)
            return {
                "hook": parsed.get("hook", ""),
                "narration_text": parsed.get("narration_text", ""),
                "outro": parsed.get("outro", ""),
                "model_name": settings.OPENAI_SCRIPT_MODEL,
            }
    except Exception:
        pass
    return _heuristic_first_person(source_text, story.title)


def upsert_script(session: Session, story: Story) -> ScriptVersion:
    payload = generate_script_payload(story)
    source_text = story.body_md or story.title
    for script in session.exec(
        select(ScriptVersion).where(ScriptVersion.story_id == story.id).order_by(ScriptVersion.id.desc())
    ).all():
        script.is_active = False
        session.add(script)
    script = ScriptVersion(
        story_id=story.id,
        source_text=source_text,
        hook=payload["hook"],
        narration_text=payload["narration_text"],
        outro=payload["outro"],
        model_name=payload["model_name"],
        prompt_version="v1",
        is_active=True,
    )
    session.add(script)
    session.flush()
    story.active_script_version_id = script.id
    story.status = StoryStatus.SCRIPTED.value
    session.add(story)
    session.flush()
    replace_parts_from_script(session, story, script)
    return script


def replace_parts_from_script(session: Session, story: Story, script: ScriptVersion) -> list[StoryPart]:
    for part in session.exec(select(StoryPart).where(StoryPart.story_id == story.id)).all():
        session.delete(part)
    composite = " ".join(filter(None, [script.hook, script.narration_text, script.outro])).strip()
    part_specs = split_sentences(composite, target_seconds=55)
    parts: list[StoryPart] = []
    cursor = 0
    for body, index, est_seconds in part_specs:
        start_char = composite.find(body, cursor)
        end_char = start_char + len(body) if start_char >= 0 else cursor + len(body)
        cursor = max(cursor, end_char)
        part = StoryPart(
            story_id=story.id,
            script_version_id=script.id,
            index=index,
            body_md=body,
            source_text=body,
            script_text=body,
            est_seconds=est_seconds,
            start_char=max(0, start_char),
            end_char=max(0, end_char),
            approved=True,
        )
        session.add(part)
        parts.append(part)
    session.flush()
    return parts


def ensure_default_presets(session: Session) -> None:
    existing = {
        preset.slug
        for preset in session.exec(select(RenderPreset)).all()
    }
    presets = [
        RenderPreset(
            slug="short-form",
            name="Short Form Vertical",
            variant=RenderVariant.SHORT.value,
            width=1080,
            height=1920,
            fps=30,
            burn_subtitles=True,
            target_min_seconds=45,
            target_max_seconds=60,
            music_enabled=True,
            music_gain_db=-3,
            ducking_db=-12,
            description="Instagram Reels, TikTok, and YouTube Shorts default preset.",
        ),
        RenderPreset(
            slug="weekly-full",
            name="Weekly Full Story",
            variant=RenderVariant.WEEKLY.value,
            width=1920,
            height=1080,
            fps=30,
            burn_subtitles=False,
            target_min_seconds=240,
            target_max_seconds=1800,
            music_enabled=True,
            music_gain_db=-8,
            ducking_db=-16,
            description="Horizontal YouTube compilation preset.",
        ),
    ]
    changed = False
    for preset in presets:
        if preset.slug not in existing:
            session.add(preset)
            changed = True
    if changed:
        session.commit()


def _ffprobe_json(path: Path) -> dict:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=width,height:format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except Exception:
        return {}


def _orientation(width: int | None, height: int | None) -> str | None:
    if not width or not height:
        return None
    if height > width:
        return "portrait"
    if width > height:
        return "landscape"
    return "square"


def index_local_assets(session: Session) -> list[Asset]:
    visuals_dir = Path(settings.VISUALS_DIR)
    visuals_dir.mkdir(parents=True, exist_ok=True)
    existing_hashes = {
        asset.file_hash
        for asset in session.exec(select(Asset).where(Asset.story_id.is_(None))).all()
        if asset.file_hash
    }
    added: list[Asset] = []
    for path in sorted(visuals_dir.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in IMAGE_EXTS | VIDEO_EXTS:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in existing_hashes:
            continue
        probe = _ffprobe_json(path)
        streams = probe.get("streams") or [{}]
        stream = streams[0] if streams else {}
        width = stream.get("width")
        height = stream.get("height")
        duration = probe.get("format", {}).get("duration")
        asset = Asset(
            story_id=None,
            type="video" if ext in VIDEO_EXTS else "image",
            local_path=str(path),
            source="local",
            provider="filesystem",
            provider_id=path.name,
            selected=False,
            duration_ms=int(float(duration) * 1000) if duration else None,
            width=int(width) if width else None,
            height=int(height) if height else None,
            orientation=_orientation(int(width), int(height)) if width and height else None,
            file_hash=digest,
            tags=[token for token in re.split(r"[_\-\s]+", path.stem.lower()) if token],
            attribution="local library",
        )
        session.add(asset)
        added.append(asset)
        existing_hashes.add(digest)
    session.commit()
    return session.exec(select(Asset).where(Asset.story_id.is_(None)).order_by(Asset.id)).all()


def best_assets_for_story(session: Session, story: Story, limit: int = 12) -> list[Asset]:
    tokens = {
        token.lower()
        for token in re.split(r"[^a-zA-Z0-9]+", f"{story.title} {story.body_md or ''}")
        if len(token) > 2
    }
    assets = session.exec(select(Asset).where(Asset.story_id.is_(None))).all()
    ranked = sorted(
        assets,
        key=lambda asset: sum(1 for tag in asset.tags or [] if tag in tokens),
        reverse=True,
    )
    return ranked[:limit]


def create_asset_bundle(
    session: Session,
    story: Story,
    *,
    name: str,
    asset_ids: list[int],
    variant: str = RenderVariant.SHORT.value,
    music_policy: str = "first",
    music_track: str | None = None,
) -> AssetBundle:
    bundle = AssetBundle(
        story_id=story.id,
        name=name,
        variant=variant,
        asset_ids=asset_ids,
        music_policy=music_policy,
        music_track=music_track,
    )
    session.add(bundle)
    session.flush()
    story.active_asset_bundle_id = bundle.id
    story.status = StoryStatus.MEDIA_READY.value
    session.add(story)
    return bundle


def create_short_releases(
    session: Session,
    story: Story,
    *,
    platforms: list[str],
    preset: RenderPreset,
    asset_bundle: AssetBundle,
) -> tuple[list[Release], list[Job]]:
    parts = session.exec(
        select(StoryPart)
        .where(StoryPart.story_id == story.id)
        .order_by(StoryPart.index)
    ).all()
    releases: list[Release] = []
    jobs: list[Job] = []
    for part in parts:
        for platform in platforms:
            release = Release(
                story_id=story.id,
                story_part_id=part.id,
                platform=platform,
                variant=RenderVariant.SHORT.value,
                title=f"{story.title} Part {part.index}",
                description=f"{story.title}\n\n#scarystories #nosleep #{platform}",
                hashtags=["scarystories", "nosleep", platform],
                status=ReleaseStatus.DRAFT.value,
            )
            session.add(release)
            releases.append(release)
        job = Job(
            story_id=story.id,
            story_part_id=part.id,
            script_version_id=part.script_version_id,
            asset_bundle_id=asset_bundle.id,
            render_preset_id=preset.id,
            kind="render_part",
            variant=RenderVariant.SHORT.value,
            status=JobStatus.QUEUED.value,
            correlation_id=f"story-{story.id}-part-{part.index}",
            payload={
                "story_id": story.id,
                "story_part_id": part.id,
                "variant": RenderVariant.SHORT.value,
                "asset_bundle_id": asset_bundle.id,
                "script_version_id": part.script_version_id,
                "render_preset_id": preset.id,
                "part_index": part.index,
                "platforms": platforms,
            },
        )
        session.add(job)
        jobs.append(job)
    story.status = StoryStatus.QUEUED.value
    session.add(story)
    return releases, jobs


def create_weekly_compilation(
    session: Session,
    story: Story,
    *,
    preset: RenderPreset,
) -> tuple[Compilation, Job]:
    compilation = Compilation(
        story_id=story.id,
        title=f"{story.title} Weekly Full Story",
        status=StoryStatus.APPROVED.value,
        script_version_id=story.active_script_version_id,
        render_preset_id=preset.id,
    )
    session.add(compilation)
    session.flush()
    job = Job(
        story_id=story.id,
        compilation_id=compilation.id,
        script_version_id=story.active_script_version_id,
        render_preset_id=preset.id,
        kind="render_compilation",
        variant=RenderVariant.WEEKLY.value,
        status=JobStatus.QUEUED.value,
        correlation_id=f"story-{story.id}-weekly",
        payload={
            "story_id": story.id,
            "compilation_id": compilation.id,
            "variant": RenderVariant.WEEKLY.value,
            "render_preset_id": preset.id,
        },
    )
    session.add(job)
    return compilation, job


def mark_publish_ready(session: Session, story: Story) -> None:
    story.status = StoryStatus.PUBLISH_READY.value
    session.add(story)


def release_for_artifact(
    session: Session,
    *,
    story_id: int,
    story_part_id: int | None,
    compilation_id: int | None,
) -> Iterable[Release]:
    query = select(Release).where(Release.story_id == story_id)
    if story_part_id is None:
        query = query.where(Release.story_part_id.is_(None))
    else:
        query = query.where(Release.story_part_id == story_part_id)
    if compilation_id is None:
        query = query.where(Release.compilation_id.is_(None))
    else:
        query = query.where(Release.compilation_id == compilation_id)
    return session.exec(query).all()
