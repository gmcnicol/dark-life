"""Helpers for script generation, media indexing, and render job creation."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import requests
from sqlmodel import Session, select

from shared.config import settings
from shared.workflow import JobStatus, PublishApprovalStatus, ReleaseStatus, RenderVariant, StoryStatus

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
from .publishing import delivery_mode_for_platform, short_release_schedule

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
CHAPTER_BREAK_RE = re.compile(r"\n\s*\n+")
WORDS_PER_SECOND = 2.6
SHORT_TARGET_SECONDS = 55
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
STOPWORDS = {
    "a",
    "about",
    "after",
    "and",
    "been",
    "before",
    "from",
    "have",
    "into",
    "just",
    "like",
    "over",
    "that",
    "their",
    "there",
    "they",
    "this",
    "with",
    "would",
}


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
        sentences = [title.strip()] if title.strip() else [body]
    opening = sentences[0] if sentences else title.strip()
    narration = " ".join(sentences).strip()
    hook = _clip_text(opening or title.strip() or "Something was wrong from the start.", 140)
    outro = "And I still can't explain what followed."
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
        "You are the head writer for Dark Life Stories, creating premium horror narration for short-form vertical video. "
        "Rewrite the source into an aggressive, highly engaging first-person narrative built to serialize across as few shorts/reels as needed while still telling the complete story. "
        "Return strict JSON with keys hook, narration_text, outro. "
        "Requirements: "
        "hook must be 1 to 2 sentences and hit immediately with tension, curiosity, and danger. "
        "narration_text must be split into paragraphs separated by a blank line, with each paragraph functioning as one short-form chapter. "
        "Use the minimum number of chapters that keeps the full story coherent, complete, and easy to follow. "
        "The full story must stay coherent, logically consistent, and emotionally readable from beginning to end. "
        "Each chapter should escalate the situation, feel easy to narrate aloud, and ideally close on a reveal, reversal, question, or forward pull that makes people want the next part, but never at the expense of clarity or coherence. "
        "Preserve the core plot and emotional truth, but sharpen pacing, imagery, and suspense so it feels cinematic and addictive. "
        "Use clean first-person voice, vivid sensory detail, sharp sentence variety, and constant forward momentum. "
        "If the source is thin, expand tension and interiority without contradicting the story. "
        "Avoid repetitive filler and banned phrases such as 'I remember', 'it all started when', 'little did I know', 'if you're hearing this', 'I never thought', and 'to this day'. "
        "Do not add labels like Chapter 1, bullet points, markdown, or commentary outside the JSON."
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


def _script_part_specs(script: ScriptVersion, target_seconds: int = SHORT_TARGET_SECONDS) -> list[tuple[str, int, int]]:
    chapters = [
        segment.strip()
        for segment in CHAPTER_BREAK_RE.split((script.narration_text or "").strip())
        if segment.strip()
    ]
    if len(chapters) > 1:
        if script.hook.strip():
            chapters[0] = f"{script.hook.strip()} {chapters[0]}".strip()
        if script.outro.strip():
            chapters[-1] = f"{chapters[-1]} {script.outro.strip()}".strip()
        return [
            (body, index, estimate_seconds(body))
            for index, body in enumerate(chapters, start=1)
        ]

    composite = " ".join(filter(None, [script.hook, script.narration_text, script.outro])).strip()
    return split_sentences(composite, target_seconds=target_seconds)


def _clip_text(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= limit:
        return cleaned
    clipped = cleaned[: limit - 1].rsplit(" ", 1)[0].strip()
    return f"{clipped}…"


def _first_sentence(text: str) -> str:
    sentences = [segment.strip() for segment in SENTENCE_RE.split(text.strip()) if segment.strip()]
    return sentences[0] if sentences else text.strip()


def _keyword_candidates(*parts: str) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for token in re.findall(r"[a-zA-Z]{4,}", part.lower()):
            if token in STOPWORDS or token in seen:
                continue
            seen.add(token)
            keywords.append(token)
    return keywords


def _source_credit(story: Story) -> str | None:
    author = (story.author or "").strip()
    subreddit = (story.subreddit or "").strip()
    source_url = (story.source_url or "").strip()
    credit_bits: list[str] = []
    if author:
        credit_bits.append(f"u/{author}")
    if subreddit:
        credit_bits.append(f"r/{subreddit}")
    if credit_bits and source_url:
        return f"Original post: {' in '.join(credit_bits)}\n{source_url}"
    if credit_bits:
        return f"Original post: {' in '.join(credit_bits)}"
    if source_url:
        return f"Original post:\n{source_url}"
    return None


def _heuristic_release_metadata(
    story: Story,
    *,
    part: StoryPart | None,
    variant: str,
) -> dict[str, object]:
    base_title = story.title.strip()
    if variant == RenderVariant.WEEKLY.value:
        title = _clip_text(f"{base_title} | Full Story", 90)
        excerpt_source = story.body_md or base_title
        base_tags = ["darklifestories", "scarystories", "horrorstories", "fullstory"]
    else:
        part_index = part.index if part else 1
        title = _clip_text(f"{base_title} | Part {part_index}", 90)
        excerpt_source = (part.script_text or part.body_md) if part else (story.body_md or base_title)
        base_tags = ["darklifestories", "scarystories", "horrorstories", "shorts"]
    excerpt = _clip_text(_first_sentence(excerpt_source or base_title), 140)
    keywords = _keyword_candidates(story.title, story.body_md or "", excerpt_source or "")[:2]
    hashtags = list(dict.fromkeys([*base_tags, *keywords]))[:6]
    description_parts = [title, excerpt]
    credit = _source_credit(story)
    if credit:
        description_parts.append(credit)
    description_parts.append(" ".join(f"#{tag}" for tag in hashtags))
    description = "\n\n".join(description_parts)
    return {
        "title": title,
        "description": description.strip(),
        "hashtags": hashtags,
    }


def generate_release_metadata(
    story: Story,
    *,
    part: StoryPart | None = None,
    variant: str = RenderVariant.SHORT.value,
) -> dict[str, object]:
    fallback = _heuristic_release_metadata(story, part=part, variant=variant)
    if not settings.OPENAI_API_KEY:
        return fallback

    context = {
        "channel": "Dark Life Stories",
        "story_title": story.title,
        "story_author": story.author,
        "story_subreddit": story.subreddit,
        "story_source_url": story.source_url,
        "variant": variant,
        "story_excerpt": _clip_text(story.body_md or story.title, 500),
        "part_index": part.index if part else None,
        "part_excerpt": _clip_text((part.script_text or part.body_md) if part else "", 350),
        "fallback": fallback,
    }
    payload = {
        "model": settings.OPENAI_SCRIPT_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Generate publish metadata for a premium horror storytelling channel named Dark Life Stories. "
                            "Return strict JSON with keys title, description, hashtags. "
                            "Title must be under 90 characters, sharp and clickable but not spammy. "
                            "Description should be concise, include a clear original-post credit when author, subreddit, or source_url are provided, and end with hashtags. "
                            "Hashtags must be lowercase strings without '#', 4 to 6 items."
                        ),
                    }
                ],
            },
            {"role": "user", "content": [{"type": "text", "text": json.dumps(context)}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "release_metadata",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "hashtags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 4,
                            "maxItems": 6,
                        },
                    },
                    "required": ["title", "description", "hashtags"],
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
            timeout=25,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("output_text")
        if not isinstance(text, str):
            return fallback
        parsed = json.loads(text)
        title = _clip_text(str(parsed.get("title") or fallback["title"]), 90)
        hashtags = [
            re.sub(r"[^a-z0-9]", "", str(tag).lower().lstrip("#"))
            for tag in parsed.get("hashtags", [])
        ]
        hashtags = [tag for tag in hashtags if tag]
        if len(hashtags) < 4:
            hashtags = list(dict.fromkeys([*hashtags, *fallback["hashtags"]]))[:6]
        description = str(parsed.get("description") or fallback["description"]).strip()
        credit = _source_credit(story)
        if credit and credit.lower() not in description.lower():
            description = f"{description}\n\n{credit}"
        if "#" not in description:
            description = f"{description}\n\n" + " ".join(f"#{tag}" for tag in hashtags)
        return {
            "title": title,
            "description": description.strip(),
            "hashtags": hashtags[:6],
        }
    except Exception:
        return fallback


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
        prompt_version="v2",
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
    for part in session.exec(select(StoryPart).where(StoryPart.script_version_id == script.id)).all():
        session.delete(part)
    composite = " ".join(filter(None, [script.hook, script.narration_text, script.outro])).strip()
    part_specs = _script_part_specs(script)
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
    asset_refs: list[dict[str, object]],
    part_asset_map: list[dict[str, object]] | None = None,
    variant: str = RenderVariant.SHORT.value,
    music_policy: str = "first",
    music_track: str | None = None,
) -> AssetBundle:
    bundle = AssetBundle(
        story_id=story.id,
        name=name,
        variant=variant,
        asset_refs=asset_refs,
        part_asset_map=part_asset_map or [],
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
    script_version: ScriptVersion | None = None,
) -> tuple[list[Release], list[Job]]:
    target_script_version_id = script_version.id if script_version else story.active_script_version_id
    parts = session.exec(
        select(StoryPart)
        .where(
            StoryPart.story_id == story.id,
            StoryPart.script_version_id == target_script_version_id,
        )
        .order_by(StoryPart.index)
    ).all()
    publish_slots = short_release_schedule(session, count=len(parts))
    approved_at = datetime.now(timezone.utc)
    releases: list[Release] = []
    jobs: list[Job] = []
    for index, part in enumerate(parts):
        metadata = generate_release_metadata(
            story,
            part=part,
            variant=RenderVariant.SHORT.value,
        )
        publish_at = publish_slots[index] if index < len(publish_slots) else None
        for platform in platforms:
            release = Release(
                story_id=story.id,
                story_part_id=part.id,
                script_version_id=part.script_version_id,
                platform=platform,
                variant=RenderVariant.SHORT.value,
                title=str(metadata["title"]),
                description=str(metadata["description"]),
                hashtags=list(metadata["hashtags"]),
                status=ReleaseStatus.DRAFT.value,
                publish_status=ReleaseStatus.DRAFT.value,
                approval_status=PublishApprovalStatus.APPROVED.value,
                delivery_mode=delivery_mode_for_platform(platform),
                publish_at=publish_at,
                approved_at=approved_at,
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
            correlation_id=f"story-{story.id}-script-{part.script_version_id or 'active'}-part-{part.index}",
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
    script_version_id: int | None = None,
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
    if script_version_id is None:
        query = query.where(Release.script_version_id.is_(None))
    else:
        query = query.where(Release.script_version_id == script_version_id)
    return session.exec(query).all()
