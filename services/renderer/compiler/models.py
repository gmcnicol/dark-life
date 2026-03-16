"""Pure planning models for compile-first renderer execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CommandSpec:
    label: str
    binary: str
    args: list[str]
    env: dict[str, str] | None = None
    cwd: str | None = None
    expected_outputs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArtifactSpec:
    video_path: Path
    subtitle_path: Path
    mixed_audio_path: Path | None = None
    staged_visual_path: Path | None = None


@dataclass(frozen=True)
class RenderInput:
    job_id: int
    story_id: int
    part_id: int
    correlation_id: str | None
    voice_path: Path
    subtitle_path: Path
    visual_path: Path
    music_path: Path | None
    output_root: Path
    job_dir: Path
    duration_ms: int
    subtitle_format: str
    asset: dict
    preset: dict
    burn_subtitles: bool
    music_policy: str | None = None


@dataclass(frozen=True)
class RenderPlan:
    commands: list[CommandSpec]
    artifacts: ArtifactSpec
    metadata: dict[str, object]


__all__ = ["ArtifactSpec", "CommandSpec", "RenderInput", "RenderPlan"]
