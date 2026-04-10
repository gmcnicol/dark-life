"""Script refinement helpers shared by API routes and workers."""

from __future__ import annotations

import json
import math
import random
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

import requests
from sqlmodel import Session, select

from shared.config import settings
from shared.logging import log_error, log_info

from .models import (
    AnalysisReport,
    MetricsSnapshot,
    PromptVersion,
    Release,
    ScriptBatch,
    ScriptVersion,
    Story,
    StoryConcept,
    StoryPart,
)

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
WORD_RE = re.compile(r"[A-Za-z']+")
OBJECT_CANDIDATES = (
    "mirror",
    "phone",
    "door",
    "shadow",
    "window",
    "hallway",
    "basement",
    "stairs",
    "bed",
    "closet",
)
HOOK_PATTERNS = {
    "contradiction": ("should not", "was empty", "nobody", "impossible", "never"),
    "proof": ("saw", "recorded", "photo", "video", "proof"),
    "threat": ("coming for", "outside my", "under my", "would kill", "waiting"),
    "anomaly": ("wrong", "moved", "opened", "whisper", "watching", "footsteps"),
}
EPISODE_TYPES = ["entry", "escalation", "escalation", "twist", "perspective"]
PROMPT_DEFAULTS: dict[str, dict[str, Any]] = {
    "generator": {
        "version_label": "gen_prompt_v1",
        "body": (
            "Generate first-person horror serial candidates for short-form vertical video. "
            "Return strict JSON. Each candidate must include hook, narration_text, outro, and episodes. "
            "Use the minimum number of episodes needed to tell the full story cleanly and completely. "
            "Each episode needs: episode_type, body_md, hook, lines, loop_line. Use plain, detached tone."
        ),
        "config": {"candidate_count": settings.REFINEMENT_DEFAULT_BATCH_SIZE},
    },
    "critic": {
        "version_label": "critic_v1",
        "body": (
            "Score each script for hook strength, curiosity gap, escalation quality, clarity, loop strength, "
            "standalone value, and voice match on a 0-5 scale. Return strict JSON."
        ),
        "config": {"shortlist_size": settings.REFINEMENT_DEFAULT_SHORTLIST_SIZE},
    },
    "analyst": {
        "version_label": "analyst_v1",
        "body": (
            "Compare top and bottom performers, identify winning patterns and failure modes, and propose draft "
            "prompt, template, or rubric updates without activating them."
        ),
        "config": {"metrics_window_hours": 72},
    },
    "template": {
        "version_label": "template_v1",
        "body": "HOOK -> ESCALATION -> SHIFT -> REVEAL/CLIFFHANGER, extended only when the story needs extra beats, with a loop line in every episode.",
        "config": {"episodes": "dynamic"},
    },
    "selection_policy": {
        "version_label": "selection_policy_v1",
        "body": "Use critic total score for shortlist ranking and retention-heavy performance score after publish.",
        "config": {"weights": {"retention": 0.55, "engagement": 0.25, "completion": 0.2}},
    },
}


class OpenAIRefinementError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
        response_summary: str | None = None,
        attempt_count: int = 1,
        last_error_class: str | None = None,
        last_error_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.response_summary = response_summary
        self.attempt_count = attempt_count
        self.last_error_class = last_error_class
        self.last_error_message = last_error_message


def _response_summary(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    response_id = payload.get("id")
    status = payload.get("status")
    if response_id:
        parts.append(f"id={response_id}")
    if status:
        parts.append(f"status={status}")
    error = payload.get("error")
    if isinstance(error, dict):
        err_type = error.get("type")
        err_msg = error.get("message")
        if err_type:
            parts.append(f"error_type={err_type}")
        if err_msg:
            parts.append(f"error={_clip(str(err_msg), 80)}")
    output_text = _responses_output_text(payload)
    if output_text:
        parts.append(f"output={_clip(output_text, 80)}")
    return "; ".join(parts) or "no_summary"


def _classify_openai_request_error(
    exc: Exception,
    *,
    stage: str,
    story_id: int | None,
) -> OpenAIRefinementError:
    if isinstance(exc, OpenAIRefinementError):
        return exc
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return OpenAIRefinementError(
            f"OpenAI {stage} failed for story {story_id}: {exc}",
            retryable=True,
            last_error_class=exc.__class__.__name__,
            last_error_message=str(exc),
        )
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        status_code = response.status_code if response is not None else None
        response_summary = None
        if response is not None:
            try:
                response_summary = _response_summary(response.json())
            except Exception:
                response_summary = _clip(getattr(response, "text", "") or "", 120)
        retryable = bool(status_code == 429 or (status_code is not None and status_code >= 500))
        return OpenAIRefinementError(
            f"OpenAI {stage} failed for story {story_id}: HTTP {status_code or 'error'}",
            retryable=retryable,
            status_code=status_code,
            response_summary=response_summary,
            last_error_class=exc.__class__.__name__,
            last_error_message=str(exc),
        )
    if isinstance(exc, requests.RequestException):
        return OpenAIRefinementError(
            f"OpenAI {stage} failed for story {story_id}: {exc}",
            retryable=False,
            last_error_class=exc.__class__.__name__,
            last_error_message=str(exc),
        )
    if isinstance(exc, json.JSONDecodeError):
        return OpenAIRefinementError(
            f"OpenAI {stage} returned invalid JSON for story {story_id}",
            retryable=False,
            last_error_class=exc.__class__.__name__,
            last_error_message=str(exc),
        )
    return OpenAIRefinementError(
        f"OpenAI {stage} failed for story {story_id}: {exc}",
        retryable=False,
        last_error_class=exc.__class__.__name__,
        last_error_message=str(exc),
    )


def _retry_delay(attempt: int) -> float:
    base = max(float(settings.REFINEMENT_OPENAI_BACKOFF_BASE_SEC), 0.0)
    maximum = max(float(settings.REFINEMENT_OPENAI_BACKOFF_MAX_SEC), base or 0.0)
    delay = min(maximum, base * (2 ** max(attempt - 1, 0)))
    return delay + random.uniform(0.0, 1.0)


def _run_openai_operation(
    *,
    stage: str,
    story_id: int | None,
    operation,
) -> tuple[Any, dict[str, Any]]:
    max_attempts = max(int(settings.REFINEMENT_OPENAI_MAX_ATTEMPTS), 1)
    last_error: OpenAIRefinementError | None = None
    for attempt in range(1, max_attempts + 1):
        started_at = time.monotonic()
        log_info("openai_attempt", stage=stage, story_id=story_id, attempt=attempt, max_attempts=max_attempts)
        try:
            result = operation()
            metadata: dict[str, Any] = {"attempt_count": attempt}
            if last_error is not None:
                metadata["last_error_class"] = last_error.last_error_class or last_error.__class__.__name__
                metadata["last_error_message"] = last_error.last_error_message or str(last_error)
            return result, metadata
        except Exception as exc:
            error = _classify_openai_request_error(exc, stage=stage, story_id=story_id)
            error.attempt_count = attempt
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            if not error.retryable or attempt >= max_attempts:
                log_error(
                    "openai_retry_exhausted",
                    stage=stage,
                    story_id=story_id,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    elapsed_ms=elapsed_ms,
                    status_code=error.status_code,
                    error_class=error.last_error_class or error.__class__.__name__,
                    error_message=error.last_error_message or str(error),
                    response_summary=error.response_summary,
                )
                raise error
            delay = _retry_delay(attempt)
            log_info(
                "openai_retry_scheduled",
                stage=stage,
                story_id=story_id,
                attempt=attempt,
                max_attempts=max_attempts,
                elapsed_ms=elapsed_ms,
                delay_sec=round(delay, 3),
                status_code=error.status_code,
                error_class=error.last_error_class or error.__class__.__name__,
                error_message=error.last_error_message or str(error),
                response_summary=error.response_summary,
            )
            last_error = error
            time.sleep(delay)
    raise AssertionError("unreachable")


def ensure_default_prompt_versions(session: Session) -> None:
    changed = False
    for kind, payload in PROMPT_DEFAULTS.items():
        existing = session.exec(
            select(PromptVersion).where(
                PromptVersion.kind == kind,
                PromptVersion.version_label == payload["version_label"],
            )
        ).first()
        if existing:
            continue
        session.add(
            PromptVersion(
                kind=kind,
                version_label=payload["version_label"],
                status="active",
                body=payload["body"],
                config=payload.get("config"),
            )
        )
        changed = True
    if changed:
        session.commit()


def active_prompt(session: Session, kind: str) -> PromptVersion:
    prompt = session.exec(
        select(PromptVersion)
        .where(PromptVersion.kind == kind, PromptVersion.status == "active")
        .order_by(PromptVersion.id.desc())
    ).first()
    if prompt:
        return prompt
    ensure_default_prompt_versions(session)
    prompt = session.exec(
        select(PromptVersion)
        .where(PromptVersion.kind == kind, PromptVersion.status == "active")
        .order_by(PromptVersion.id.desc())
    ).first()
    if not prompt:
        raise RuntimeError(f"Missing active prompt for {kind}")
    return prompt


def _clip(text: str, limit: int = 160) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rsplit(" ", 1)[0] + "…"


def _sentences(text: str) -> list[str]:
    return [segment.strip() for segment in SENTENCE_RE.split((text or "").strip()) if segment.strip()]


def _object_focus(text: str) -> str:
    lower = text.lower()
    for candidate in OBJECT_CANDIDATES:
        if candidate in lower:
            return candidate
    words = [word.lower() for word in WORD_RE.findall(text)]
    return words[0] if words else "unknown"


def _responses_output_text(payload: dict[str, Any]) -> str | None:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    for item in payload.get("output") or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    return text
    return None


def _parse_candidate_payloads(parsed: dict[str, Any], *, candidate_offset: int, candidate_limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, candidate in enumerate((parsed.get("candidates") or [])[:candidate_limit], start=1):
        episodes = []
        for episode_index, episode in enumerate((candidate.get("episodes") or [])[:5], start=1):
            lines = [str(line).strip() for line in episode.get("lines") or [] if str(line).strip()]
            hook = str(episode.get("hook") or (lines[0] if lines else ""))
            loop_line = str(episode.get("loop_line") or (lines[-1] if lines else ""))
            episodes.append(
                {
                    "episode_type": str(episode.get("episode_type") or EPISODE_TYPES[min(episode_index - 1, len(EPISODE_TYPES) - 1)]),
                    "body_md": str(episode.get("body_md") or "").strip(),
                    "hook": hook,
                    "lines": lines,
                    "loop_line": loop_line,
                    "features": _feature_map(hook, lines, loop_line),
                }
            )
        if len(episodes) == 5:
            candidates.append(
                {
                    "hook": str(candidate.get("hook") or "").strip(),
                    "narration_text": str(candidate.get("narration_text") or "\n\n".join(item["body_md"] for item in episodes)).strip(),
                    "outro": str(candidate.get("outro") or "").strip(),
                    "episodes": episodes,
                    "generation_metadata": {"source": "openai", "candidate_index": candidate_offset + index},
                }
            )
    return candidates


def extract_concept_payload(
    story: Story,
    *,
    session: Session | None = None,
    include_retry_metadata: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], dict[str, Any]]:
    source_text = story.body_md or story.title
    fallback = {
        "concept_key": re.sub(r"[^a-z0-9]+", "-", _object_focus(f"{story.title} {source_text}").lower()).strip("-") or f"story-{story.id}",
        "concept_label": _clip(story.title or "Untitled concept", 90),
        "anomaly_type": "anomaly",
        "object_focus": _object_focus(f"{story.title} {source_text}"),
        "specificity": "concrete" if len(_object_focus(source_text)) > 3 else "mixed",
        "extraction_metadata": {"source": "heuristic"},
    }
    if not settings.OPENAI_API_KEY:
        metadata = {"attempt_count": 0}
        return (fallback, metadata) if include_retry_metadata else fallback
    prompt = active_prompt(session, "generator").body if session else PROMPT_DEFAULTS["generator"]["body"]
    payload = {
        "model": settings.OPENAI_SCRIPT_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Extract a reusable horror concept from the source story. "
                            "Return strict JSON with concept_key, concept_label, anomaly_type, object_focus, specificity."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps({"title": story.title, "text": source_text, "prompt": prompt})}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "story_concept",
                "schema": {
                    "type": "object",
                    "properties": {
                        "concept_key": {"type": "string"},
                        "concept_label": {"type": "string"},
                        "anomaly_type": {"type": "string"},
                        "object_focus": {"type": "string"},
                        "specificity": {"type": "string"},
                    },
                    "required": ["concept_key", "concept_label", "anomaly_type", "object_focus", "specificity"],
                    "additionalProperties": False,
                },
            }
        },
    }
    def _operation() -> dict[str, Any]:
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
        response_payload = response.json()
        output_text = _responses_output_text(response_payload)
        if not isinstance(output_text, str):
            raise OpenAIRefinementError(
                f"OpenAI extract returned no output text for story {story.id}",
                retryable=False,
                response_summary=_response_summary(response_payload),
            )
        parsed = json.loads(output_text)
        return {
            "concept_key": _clip(str(parsed.get("concept_key") or fallback["concept_key"]), 80).lower().replace(" ", "-"),
            "concept_label": str(parsed.get("concept_label") or fallback["concept_label"]),
            "anomaly_type": str(parsed.get("anomaly_type") or fallback["anomaly_type"]),
            "object_focus": str(parsed.get("object_focus") or fallback["object_focus"]),
            "specificity": str(parsed.get("specificity") or fallback["specificity"]),
            "extraction_metadata": {"source": "openai"},
        }

    try:
        concept_payload, retry_metadata = _run_openai_operation(
            stage="extract",
            story_id=story.id,
            operation=_operation,
        )
        return (concept_payload, retry_metadata) if include_retry_metadata else concept_payload
    except OpenAIRefinementError as exc:
        log_error(
            "refinement_extract_concept_openai_error",
            story_id=story.id,
            model=settings.OPENAI_SCRIPT_MODEL,
            error=str(exc),
            attempt_count=exc.attempt_count,
            status_code=exc.status_code,
            response_summary=exc.response_summary,
        )
        raise


def upsert_story_concept(session: Session, story: Story, payload: dict[str, Any]) -> StoryConcept:
    existing = session.exec(
        select(StoryConcept)
        .where(StoryConcept.story_id == story.id, StoryConcept.concept_key == payload["concept_key"])
        .order_by(StoryConcept.id.desc())
    ).first()
    if existing:
        for concept in session.exec(select(StoryConcept).where(StoryConcept.story_id == story.id)).all():
            concept.is_active = concept.id == existing.id
            session.add(concept)
        existing.concept_label = payload["concept_label"]
        existing.anomaly_type = payload["anomaly_type"]
        existing.object_focus = payload["object_focus"]
        existing.specificity = payload["specificity"]
        existing.extraction_metadata = payload.get("extraction_metadata")
        existing.is_active = True
        session.add(existing)
        session.flush()
        return existing
    for concept in session.exec(select(StoryConcept).where(StoryConcept.story_id == story.id)).all():
        concept.is_active = False
        session.add(concept)
    concept = StoryConcept(story_id=story.id, **payload, is_active=True)
    session.add(concept)
    session.flush()
    return concept


def _chunk_sentences(text: str, count: int = 5) -> list[str]:
    sentences = _sentences(text)
    if not sentences:
        sentences = [_clip(text or "Something was already wrong.", 120)]
    size = max(1, math.ceil(len(sentences) / count))
    chunks: list[str] = []
    for index in range(count):
        chunk = sentences[index * size : (index + 1) * size]
        chunks.append((" ".join(chunk).strip()) or (chunks[-1] if chunks else sentences[0]))
    return chunks[:count]


def _lineate(text: str) -> list[str]:
    lines: list[str] = []
    for sentence in _sentences(text):
        words = sentence.split()
        if len(words) <= 12:
            lines.append(_clip(sentence, 120))
            continue
        midpoint = max(6, min(12, len(words) // 2))
        lines.append(" ".join(words[:midpoint]))
        lines.append(" ".join(words[midpoint:midpoint + 12]))
    return [line for line in lines if line][:6]


def _feature_map(hook: str, lines: list[str], loop_line: str) -> dict[str, Any]:
    joined = " ".join([hook, *lines, loop_line]).strip()
    words_per_line = [len(line.split()) for line in lines if line.strip()]
    hook_type = "anomaly"
    lower = joined.lower()
    for name, patterns in HOOK_PATTERNS.items():
        if any(pattern in lower for pattern in patterns):
            hook_type = name
            break
    specificity = "abstract"
    concrete_hits = sum(1 for candidate in OBJECT_CANDIDATES if candidate in lower)
    if concrete_hits >= 2:
        specificity = "concrete"
    elif concrete_hits == 1:
        specificity = "mixed"
    reveal_type = "implication" if any(token in lower for token in ("if", "because", "meant")) else "entity"
    ending_type = "loop" if loop_line else "cliffhanger"
    return {
        "line_count": len(lines),
        "avg_words_per_line": round(mean(words_per_line), 2) if words_per_line else 0,
        "hook_type": hook_type,
        "reveal_type": reveal_type,
        "ending_type": ending_type,
        "object_focus": _object_focus(joined),
        "specificity": specificity,
    }


def _fallback_candidates(story: Story, concept: StoryConcept | None, candidate_count: int) -> list[dict[str, Any]]:
    source_text = story.body_md or story.title
    chunks = _chunk_sentences(source_text, count=5)
    modifiers = [
        "The proof gets worse every night.",
        "Nobody believes me when it starts moving.",
        "I keep hearing it before I see it.",
        "The room changes when the lights go out.",
        "I should have left the first time it happened.",
    ]
    object_focus = concept.object_focus if concept else _object_focus(source_text)
    candidates: list[dict[str, Any]] = []
    for candidate_index in range(candidate_count):
        episodes: list[dict[str, Any]] = []
        for part_index, chunk in enumerate(chunks, start=1):
            modifier = modifiers[(candidate_index + part_index - 1) % len(modifiers)]
            body = _clip(f"{chunk} {modifier}", 220)
            lines = _lineate(body)
            loop_line = _clip(lines[-1] if lines else modifier, 90)
            hook = _clip(lines[0] if lines else body, 90)
            episodes.append(
                {
                    "episode_type": EPISODE_TYPES[min(part_index - 1, len(EPISODE_TYPES) - 1)],
                    "body_md": body,
                    "hook": hook,
                    "lines": lines,
                    "loop_line": loop_line,
                    "features": _feature_map(hook, lines, loop_line),
                }
            )
        narration_text = "\n\n".join(episode["body_md"] for episode in episodes)
        hook = _clip(f"I knew the {object_focus} was wrong the first night.", 110)
        outro = _clip(f"I still hear the {object_focus} when the house goes quiet.", 110)
        candidates.append(
            {
                "hook": hook,
                "narration_text": narration_text,
                "outro": outro,
                "episodes": episodes,
                "generation_metadata": {"source": "heuristic", "candidate_index": candidate_index + 1},
            }
        )
    return candidates


def generate_candidate_payloads(
    story: Story,
    *,
    concept: StoryConcept | None,
    candidate_count: int,
    session: Session | None = None,
    include_retry_metadata: bool = False,
) -> list[dict[str, Any]] | tuple[list[dict[str, Any]], dict[str, Any]]:
    if not settings.OPENAI_API_KEY:
        candidates = _fallback_candidates(story, concept, candidate_count)
        metadata = {
            "attempt_count": 0,
            "fallback_used": True,
            "fallback_reason": "missing_openai_api_key",
        }
        return (candidates, metadata) if include_retry_metadata else candidates
    generator_prompt = active_prompt(session, "generator").body if session else PROMPT_DEFAULTS["generator"]["body"]
    template_prompt = active_prompt(session, "template").body if session else PROMPT_DEFAULTS["template"]["body"]
    schema = {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hook": {"type": "string"},
                        "narration_text": {"type": "string"},
                        "outro": {"type": "string"},
                        "episodes": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "episode_type": {"type": "string"},
                                    "body_md": {"type": "string"},
                                    "hook": {"type": "string"},
                                    "lines": {"type": "array", "items": {"type": "string"}},
                                    "loop_line": {"type": "string"},
                                },
                                "required": ["episode_type", "body_md", "hook", "lines", "loop_line"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["hook", "narration_text", "outro", "episodes"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["candidates"],
        "additionalProperties": False,
    }
    source_story = {
        "title": story.title,
        "author": story.author,
        "source_url": story.source_url,
        "body_md": story.body_md,
    }
    concept_payload = (
        {
            "concept_key": concept.concept_key,
            "concept_label": concept.concept_label,
            "anomaly_type": concept.anomaly_type,
            "object_focus": concept.object_focus,
            "specificity": concept.specificity,
        }
        if concept
        else None
    )
    chunk_size = min(3, max(1, candidate_count))
    candidates: list[dict[str, Any]] = []
    retry_metadata: dict[str, Any] = {"attempt_count": 0}

    def _run_chunk(chunk_start: int, chunk_count: int, existing_hooks: list[str]) -> list[dict[str, Any]]:
        payload = {
            "model": settings.OPENAI_SCRIPT_MODEL,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "story": source_story,
                                    "concept": concept_payload,
                                    "template": template_prompt,
                                    "candidate_count": chunk_count,
                                    "candidate_offset": chunk_start,
                                    "avoid_hooks": existing_hooks,
                                    "notes": "Each candidate must stand on its own and should not reuse the same hook, outro, or episode arc ordering as earlier candidates.",
                                }
                            ),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "script_batch",
                    "schema": schema,
                }
            },
        }
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        response_payload = response.json()
        output_text = _responses_output_text(response_payload)
        if not isinstance(output_text, str):
            raise OpenAIRefinementError(
                f"OpenAI candidate generation returned no output text for story {story.id}",
                retryable=True,
                response_summary=_response_summary(response_payload),
            )
        parsed = json.loads(output_text)
        chunk_candidates = _parse_candidate_payloads(parsed, candidate_offset=chunk_start, candidate_limit=chunk_count)
        if not chunk_candidates:
            raise OpenAIRefinementError(
                f"OpenAI candidate generation returned no candidates for story {story.id}",
                retryable=True,
                response_summary=_response_summary(response_payload),
            )
        return chunk_candidates

    try:
        for chunk_start in range(0, candidate_count, chunk_size):
            chunk_count = min(chunk_size, candidate_count - chunk_start)
            existing_hooks = [candidate["hook"] for candidate in candidates[-8:] if candidate.get("hook")]
            system_prompt = (
                f"{generator_prompt} "
                "Return materially different candidates, not near-duplicates. "
                "Vary the framing, pacing, reveal order, threat interpretation, and ending loop line across candidates."
            )
            chunk_candidates, chunk_retry_metadata = _run_openai_operation(
                stage="generate",
                story_id=story.id,
                operation=lambda chunk_start=chunk_start, chunk_count=chunk_count, existing_hooks=existing_hooks: _run_chunk(
                    chunk_start,
                    chunk_count,
                    existing_hooks,
                ),
            )
            retry_metadata["attempt_count"] = max(
                int(retry_metadata.get("attempt_count") or 0),
                int(chunk_retry_metadata.get("attempt_count") or 0),
            )
            if chunk_retry_metadata.get("last_error_class"):
                retry_metadata["last_error_class"] = chunk_retry_metadata["last_error_class"]
            if chunk_retry_metadata.get("last_error_message"):
                retry_metadata["last_error_message"] = chunk_retry_metadata["last_error_message"]
            candidates.extend(chunk_candidates)
        if candidates:
            result = candidates[:candidate_count]
            return (result, retry_metadata) if include_retry_metadata else result
    except OpenAIRefinementError as exc:
        error_text = str(exc).lower()
        if exc.retryable and ("no candidates" in error_text or "no output text" in error_text):
            fallback = _fallback_candidates(story, concept, candidate_count)
            if fallback:
                metadata = {
                    "attempt_count": exc.attempt_count,
                    "last_error_class": exc.last_error_class or exc.__class__.__name__,
                    "last_error_message": exc.last_error_message or str(exc),
                    "fallback_used": True,
                    "fallback_reason": "openai_empty_response",
                }
                log_info(
                    "refinement_fallback_used",
                    stage="generate",
                    story_id=story.id,
                    attempt_count=exc.attempt_count,
                    fallback_reason=metadata["fallback_reason"],
                )
                return (fallback, metadata) if include_retry_metadata else fallback
        log_error(
            "refinement_generate_candidates_openai_error",
            story_id=story.id,
            model=settings.OPENAI_SCRIPT_MODEL,
            error=str(exc),
            attempt_count=exc.attempt_count,
            status_code=exc.status_code,
            response_summary=exc.response_summary,
        )
        raise
    raise OpenAIRefinementError(
        f"OpenAI candidate generation returned invalid JSON for story {story.id}",
        retryable=False,
    )


def persist_candidates(
    session: Session,
    *,
    story: Story,
    batch: ScriptBatch,
    concept: StoryConcept | None,
    candidates: list[dict[str, Any]],
) -> list[ScriptVersion]:
    generator_prompt = active_prompt(session, "generator")
    critic_prompt = active_prompt(session, "critic")
    selection_prompt = active_prompt(session, "selection_policy")
    scripts: list[ScriptVersion] = []
    for candidate in candidates:
        script = ScriptVersion(
            story_id=story.id,
            batch_id=batch.id,
            concept_id=concept.id if concept else None,
            source_text=story.body_md or story.title,
            hook=candidate["hook"],
            narration_text=candidate["narration_text"],
            outro=candidate["outro"],
            model_name=settings.OPENAI_SCRIPT_MODEL if candidate.get("generation_metadata", {}).get("source") == "openai" else "rule_based",
            prompt_version=generator_prompt.version_label,
            template_version=active_prompt(session, "template").version_label,
            critic_version=critic_prompt.version_label,
            selection_policy_version=selection_prompt.version_label,
            temperature=batch.temperature,
            selection_state="draft",
            generation_metadata=candidate.get("generation_metadata"),
            is_active=False,
        )
        session.add(script)
        session.flush()
        for existing in session.exec(select(StoryPart).where(StoryPart.script_version_id == script.id)).all():
            session.delete(existing)
        for index, episode in enumerate(candidate["episodes"], start=1):
            session.add(
                StoryPart(
                    story_id=story.id,
                    script_version_id=script.id,
                    index=index,
                    body_md=episode["body_md"],
                    source_text=episode["body_md"],
                    script_text=episode["body_md"],
                    est_seconds=max(1, round(len(episode["body_md"].split()) / 2.6)),
                    approved=True,
                    episode_type=episode["episode_type"],
                    hook=episode["hook"],
                    lines=episode["lines"],
                    loop_line=episode["loop_line"],
                    features=episode.get("features") or _feature_map(
                        str(episode.get("hook") or ""),
                        list(episode.get("lines") or []),
                        str(episode.get("loop_line") or ""),
                    ),
                    start_char=0,
                    end_char=0,
                )
            )
        scripts.append(script)
    session.flush()
    return scripts


def _heuristic_episode_scores(part: StoryPart) -> dict[str, float]:
    features = part.features or {}
    line_count = int(features.get("line_count") or len(part.lines or []))
    hook_strength = 5.0 if part.hook and len(part.hook.split()) <= 12 else 3.5
    curiosity_gap = 4.5 if "?" in (part.loop_line or "") or any(token in (part.hook or "").lower() for token in ("wrong", "saw", "heard", "opened")) else 3.0
    escalation_quality = min(5.0, 3.0 + (line_count / 4))
    clarity = 4.5 if line_count >= 3 else 3.0
    loop_strength = 4.5 if part.loop_line else 2.5
    standalone_value = 4.0 if len((part.body_md or "").split()) >= 8 else 3.0
    voice_match = 4.0 if "i " in f"{part.hook.lower()} {part.body_md.lower()}" else 2.5
    total_score = round(
        hook_strength * 0.2
        + curiosity_gap * 0.15
        + escalation_quality * 0.2
        + clarity * 0.15
        + loop_strength * 0.15
        + standalone_value * 0.1
        + voice_match * 0.05,
        2,
    )
    return {
        "hook_strength": round(hook_strength, 2),
        "curiosity_gap": round(curiosity_gap, 2),
        "escalation_quality": round(escalation_quality, 2),
        "clarity": round(clarity, 2),
        "loop_strength": round(loop_strength, 2),
        "standalone_value": round(standalone_value, 2),
        "voice_match": round(voice_match, 2),
        "total_score": total_score,
    }


def score_script_versions(session: Session, scripts: list[ScriptVersion], shortlist_size: int) -> list[ScriptVersion]:
    ranked: list[tuple[float, ScriptVersion]] = []
    for script in scripts:
        parts = session.exec(
            select(StoryPart)
            .where(StoryPart.script_version_id == script.id)
            .order_by(StoryPart.index)
        ).all()
        totals: list[float] = []
        for index, part in enumerate(parts, start=1):
            scores = _heuristic_episode_scores(part)
            part.critic_scores = scores
            part.critic_rank = index
            session.add(part)
            totals.append(float(scores["total_score"]))
        aggregate = round(mean(totals), 2) if totals else 0.0
        script.critic_scores = {
            "part_scores": totals,
            "total_score": aggregate,
            "part_count": len(parts),
        }
        ranked.append((aggregate, script))
        session.add(script)
    ranked.sort(key=lambda item: item[0], reverse=True)
    for index, (_score, script) in enumerate(ranked, start=1):
        script.critic_rank = index
        script.selection_state = "shortlisted" if index <= shortlist_size else "draft"
        session.add(script)
    session.flush()
    return [script for _score, script in ranked]


def activate_script_version(session: Session, script: ScriptVersion) -> ScriptVersion:
    story = session.get(Story, script.story_id)
    if not story:
        raise RuntimeError("Story not found")
    for sibling in session.exec(select(ScriptVersion).where(ScriptVersion.story_id == script.story_id)).all():
        sibling.is_active = sibling.id == script.id
        if sibling.id == script.id:
            sibling.selection_state = "active"
        session.add(sibling)
    story.active_script_version_id = script.id
    session.add(story)
    session.flush()
    return script


def metric_windows_due(session: Session, *, now: datetime | None = None) -> list[tuple[ScriptBatch, int]]:
    current = now or datetime.now(timezone.utc)
    due: list[tuple[ScriptBatch, int]] = []
    batches = session.exec(select(ScriptBatch).where(ScriptBatch.status.in_(["ready_for_review", "published", "metrics_pending", "metrics_ready"]))).all()
    for batch in batches:
        scripts = session.exec(select(ScriptVersion).where(ScriptVersion.batch_id == batch.id)).all()
        if not scripts:
            continue
        script_ids = {script.id for script in scripts if script.id is not None}
        releases = session.exec(
            select(Release)
            .where(Release.script_version_id.in_(script_ids), Release.platform == "youtube", Release.published_at.is_not(None))
        ).all()
        if not releases:
            continue
        earliest = min(release.published_at for release in releases if release.published_at)
        if not earliest:
            continue
        elapsed_hours = (current - earliest.astimezone(timezone.utc)).total_seconds() / 3600
        for window in (24, 72):
            if elapsed_hours < window:
                continue
            existing = session.exec(
                select(MetricsSnapshot).where(
                    MetricsSnapshot.script_version_id.in_(script_ids),
                    MetricsSnapshot.window_hours == window,
                )
            ).first()
            if not existing:
                due.append((batch, window))
    return due


def _part_ratios(metrics_by_index: dict[int, dict[str, float]]) -> dict[str, float]:
    first_views = float(metrics_by_index.get(1, {}).get("views") or 0.0)
    if first_views <= 0:
        return {}
    ratios: dict[str, float] = {}
    for index in sorted(metrics_by_index):
        if index == 1:
            continue
        ratios[f"part_{index}_views_ratio"] = round(float(metrics_by_index[index].get("views") or 0.0) / first_views, 4)
    return ratios


def compute_derived_metrics(metrics: dict[str, float], *, policy_weights: dict[str, float] | None = None) -> dict[str, float]:
    impressions = float(metrics.get("impressions") or 0.0)
    views = float(metrics.get("views") or 0.0)
    avg_view_duration = float(metrics.get("avg_view_duration") or 0.0)
    percent_viewed = float(metrics.get("percent_viewed") or 0.0)
    completion_rate = float(metrics.get("completion_rate") or 0.0)
    likes = float(metrics.get("likes") or 0.0)
    comments = float(metrics.get("comments") or 0.0)
    shares = float(metrics.get("shares") or 0.0)
    subs_gained = float(metrics.get("subs_gained") or 0.0)
    retention_score = round((percent_viewed * 0.6) + (completion_rate * 0.4), 4)
    engagement_base = views or impressions or 1.0
    engagement_score = round(((likes + comments * 2 + shares * 3 + subs_gained * 4) / engagement_base) * 100, 4)
    weights = policy_weights or {"retention": 0.55, "engagement": 0.25, "completion": 0.2}
    performance_score = round(
        retention_score * float(weights.get("retention", 0.55))
        + engagement_score * float(weights.get("engagement", 0.25))
        + completion_rate * float(weights.get("completion", 0.2)),
        4,
    )
    return {
        "retention_score": retention_score,
        "engagement_score": engagement_score,
        "performance_score": performance_score,
        "avg_view_duration": round(avg_view_duration, 4),
    }


def build_analysis(
    session: Session,
    batch: ScriptBatch,
    *,
    metrics_window_hours: int = 72,
) -> AnalysisReport:
    scripts = session.exec(
        select(ScriptVersion)
        .where(ScriptVersion.batch_id == batch.id)
        .order_by(ScriptVersion.performance_rank.is_(None), ScriptVersion.performance_rank, ScriptVersion.critic_rank)
    ).all()
    if not scripts:
        raise RuntimeError("Batch has no scripts")
    sorted_by_perf = sorted(
        scripts,
        key=lambda script: float((script.derived_metrics or {}).get("performance_score") or -1),
        reverse=True,
    )
    top = sorted_by_perf[: min(3, len(sorted_by_perf))]
    bottom = sorted_by_perf[-min(3, len(sorted_by_perf)) :]
    top_hooks = Counter((part.features or {}).get("hook_type", "unknown") for script in top for part in session.exec(select(StoryPart).where(StoryPart.script_version_id == script.id)).all())
    bottom_hooks = Counter((part.features or {}).get("hook_type", "unknown") for script in bottom for part in session.exec(select(StoryPart).where(StoryPart.script_version_id == script.id)).all())
    top_hook = top_hooks.most_common(1)[0][0] if top_hooks else "unknown"
    weak_hook = bottom_hooks.most_common(1)[0][0] if bottom_hooks else "unknown"
    summary = (
        f"Top performers in batch {batch.id} skewed toward {top_hook} hooks, while weaker variants over-indexed on {weak_hook}. "
        f"Retention-heavy scoring was evaluated at {metrics_window_hours}h."
    )
    report = AnalysisReport(
        batch_id=batch.id,
        story_id=batch.story_id,
        concept_id=batch.concept_id,
        analyst_version=batch.analyst_version,
        status="draft",
        summary=summary,
        insights={
            "winning_hook_type": top_hook,
            "weak_hook_type": weak_hook,
            "top_script_ids": [script.id for script in top],
            "bottom_script_ids": [script.id for script in bottom],
        },
        recommendations={
            "prompt_changes": [f"Favor {top_hook} hooks in early lines."],
            "banned_patterns": [f"Deprioritize {weak_hook} hooks when they do not create immediate tension."],
            "scoring_adjustments": ["Keep retention-heavy weighting and compare critic score drift weekly."],
        },
        prompt_proposals={
            "generator": {
                "kind": "generator",
                "version_label": f"gen_prompt_v{batch.id}",
                "status": "draft",
                "body": f"{PROMPT_DEFAULTS['generator']['body']} Favor {top_hook} hooks and concrete objects early.",
            }
        },
        metrics_window_hours=metrics_window_hours,
    )
    session.add(report)
    session.flush()
    return report


def release_metrics_payload(release: Release) -> dict[str, float]:
    metadata = release.provider_metadata or {}
    mock_metrics = metadata.get("mock_metrics")
    if isinstance(mock_metrics, dict):
        return {
            "impressions": float(mock_metrics.get("impressions") or 0.0),
            "views": float(mock_metrics.get("views") or 0.0),
            "avg_view_duration": float(mock_metrics.get("avg_view_duration") or 0.0),
            "percent_viewed": float(mock_metrics.get("percent_viewed") or 0.0),
            "completion_rate": float(mock_metrics.get("completion_rate") or 0.0),
            "likes": float(mock_metrics.get("likes") or 0.0),
            "comments": float(mock_metrics.get("comments") or 0.0),
            "shares": float(mock_metrics.get("shares") or 0.0),
            "subs_gained": float(mock_metrics.get("subs_gained") or 0.0),
        }
    views = float(metadata.get("views") or 0.0)
    likes = float(metadata.get("likes") or 0.0)
    comments = float(metadata.get("comments") or 0.0)
    return {
        "impressions": float(metadata.get("impressions") or views),
        "views": views,
        "avg_view_duration": float(metadata.get("avg_view_duration") or 0.0),
        "percent_viewed": float(metadata.get("percent_viewed") or 0.0),
        "completion_rate": float(metadata.get("completion_rate") or 0.0),
        "likes": likes,
        "comments": comments,
        "shares": float(metadata.get("shares") or 0.0),
        "subs_gained": float(metadata.get("subs_gained") or 0.0),
    }


__all__ = [
    "active_prompt",
    "activate_script_version",
    "build_analysis",
    "compute_derived_metrics",
    "ensure_default_prompt_versions",
    "extract_concept_payload",
    "generate_candidate_payloads",
    "metric_windows_due",
    "persist_candidates",
    "release_metrics_payload",
    "score_script_versions",
    "upsert_story_concept",
]
