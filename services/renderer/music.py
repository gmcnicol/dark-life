"""Background music selection and mixing utilities."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from shared.config import settings
from shared.logging import log_error, log_info


def _list_tracks() -> list[Path]:
    """Return sorted list of available mp3 tracks."""
    music_dir = Path(settings.MUSIC_DIR)
    return sorted(music_dir.glob("*.mp3"))


def select_track(selection: str | None = None, *, required: bool = False) -> Path | None:
    """Select a music track based on ``selection`` policy.

    ``selection`` may be ``"named:<filename>"`` to choose a specific file or
    ``None``/``"first"`` to return the first sorted ``*.mp3`` file. When
    ``required`` is True, a missing track raises :class:`FileNotFoundError` and
    an error is logged.
    """

    tracks = _list_tracks()
    music_dir = Path(settings.MUSIC_DIR)
    if not tracks:
        if required:
            log_error("music_missing", music_dir=str(music_dir))
            raise FileNotFoundError(f"no .mp3 tracks in {music_dir}")
        return None

    chosen: Path | None = None
    if selection and selection.startswith("named:"):
        target = selection.split(":", 1)[1]
        for t in tracks:
            if t.name == target:
                chosen = t
                break
        if not chosen:
            log_error("music_named_missing", name=target, music_dir=str(music_dir))
            if required:
                raise FileNotFoundError(f"named track not found: {target}")
            return None
    else:
        chosen = tracks[0]

    log_info(
        "music_select",
        chosen_track=chosen.name,
        policy=selection or "first",
        music_dir=str(music_dir),
    )
    return chosen


def mix(voice: Path, music: Path | None, out_path: Path) -> Path:
    """Mix ``voice`` and ``music`` using ffmpeg with sidechain compression."""

    if music is None:
        shutil.copyfile(voice, out_path)
        return out_path

    threshold = 0.000976563
    filter_complex = (
        f"[1:a]volume={settings.MUSIC_GAIN_DB}dB[m];"
        f"[m][0:a]sidechaincompress=threshold={threshold}:ratio=20:attack=5:release=50[d];"
        f"[0:a][d]amix=inputs=2:duration=first:dropout_transition=2,volume=-1dB[out]"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(voice),
        "-i",
        str(music),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
        "-c:a",
        "pcm_s16le",
        str(out_path),
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as exc:  # pragma: no cover - ffmpeg missing
        log_error("ffmpeg", cmd=" ".join(cmd), error=str(exc))
        raise

    log_info("music_mix", voice=str(voice), music=str(music), out=str(out_path))
    return out_path


__all__ = ["select_track", "mix"]
