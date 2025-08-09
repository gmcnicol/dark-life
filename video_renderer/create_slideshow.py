"""Create a video slideshow with crossfades, audio mix and subtitles using ffmpeg.

The script searches for assets based on a story identifier and assembles a
simple video containing:

* Still images displayed as a slideshow with 5s per image and 1s crossfades.
* Optional dark overlay and gentle zoom.
* Mixed voiceover and background music.
* Burned-in subtitles.

Only built-in Python modules are used and ``ffmpeg`` is invoked through
:func:`subprocess.run`.
"""

from __future__ import annotations

import argparse
import logging
import shlex
import subprocess
from pathlib import Path

IMAGE_DURATION = 5
TRANSITION_DURATION = 1


def build_video_filters(
    image_count: int,
    subtitle: Path | None,
    dark_overlay: bool,
    zoom: bool,
) -> tuple[list[str], str]:
    """Return filter graph parts and final video label.

    ``image_count`` specifies number of image inputs already provided to
    ffmpeg. ``subtitle`` is an optional subtitle file. If ``dark_overlay`` is
    True, a translucent black layer is drawn over the video for a spooky
    aesthetic. ``zoom`` enables a subtle zoom effect on each slide.
    """

    filters: list[str] = []
    # Prepare each image stream
    for idx in range(image_count):
        label = f"v{idx}"
        src = f"[{idx}:v]"
        if zoom:
            # zoompan generates frames from a still image with slight zoom
            zoom_filter = (
                "zoompan=z='min(zoom+0.0005,1.1)':" f"d={IMAGE_DURATION * 25}:s=1280x720"
            )
            filters.append(f"{src}{zoom_filter}[{label}]")
        else:
            filters.append(f"{src}scale=1280:720,setsar=1[{label}]")

    last = "[v0]"
    step = IMAGE_DURATION - TRANSITION_DURATION
    for i in range(1, image_count):
        offset = step * i
        out_label = f"vx{i}"
        filters.append(
            f"{last}[v{i}]xfade=transition=fade:duration={TRANSITION_DURATION}:offset={offset}[{out_label}]"
        )
        last = f"[{out_label}]"

    if dark_overlay:
        filters.append(f"{last}drawbox=t=fill:color=black@0.4[v_dark]")
        last = "[v_dark]"

    if subtitle:
        # Quote the subtitle path to allow for spaces in directories
        filters.append(f"{last}subtitles='{subtitle.as_posix()}'[v_final]")
        last = "[v_final]"

    return filters, last


def run_ffmpeg(cmd: list[str]) -> int:
    """Run ffmpeg command and return its exit status."""

    logging.debug("Running ffmpeg: %s", " ".join(shlex.quote(c) for c in cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        logging.error("ffmpeg failed: %s", proc.stderr.decode(errors="ignore"))
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a video slideshow")
    parser.add_argument("--story_id", required=True, help="Story identifier")
    parser.add_argument(
        "--visuals-dir", type=Path, default=Path("content/visuals"), help="Image directory"
    )
    parser.add_argument(
        "--voice-dir", type=Path, default=Path("content/audio/voiceovers"), help="Voiceover directory"
    )
    parser.add_argument(
        "--music-dir", type=Path, default=Path("content/audio/music"), help="Background music directory"
    )
    parser.add_argument(
        "--subtitles-dir", type=Path, default=Path("content/subtitles"), help="Subtitle directory"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output/videos"), help="Output directory"
    )
    parser.add_argument("--dark-overlay", action="store_true", help="Apply dark overlay")
    parser.add_argument("--zoom", action="store_true", help="Apply subtle zoom")
    parser.add_argument(
        "--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING)"
    )

    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    images = sorted(args.visuals_dir.glob(f"{args.story_id}_*.jpg"))
    if not images:
        logging.error("No images found for %s", args.story_id)
        return 1

    voice = args.voice_dir / f"{args.story_id}.mp3"
    if not voice.exists():
        logging.warning("Voiceover not found: %s", voice)
        voice = None

    music_candidates = sorted(args.music_dir.glob("*.mp3"))
    music = music_candidates[0] if music_candidates else None
    if music is None:
        logging.warning("No background music found in %s", args.music_dir)

    subtitle = args.subtitles_dir / f"{args.story_id}.srt"
    if not subtitle.exists():
        logging.warning("Subtitle file not found: %s", subtitle)
        subtitle = None

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_file = args.output_dir / f"{args.story_id}_final.mp4"

    cmd: list[str] = ["ffmpeg", "-y"]
    for img in images:
        cmd += ["-loop", "1", "-t", str(IMAGE_DURATION), "-i", str(img)]

    audio_indices: list[int] = []
    current_idx = len(images)
    if voice:
        cmd += ["-i", str(voice)]
        audio_indices.append(current_idx)
        current_idx += 1
    if music:
        cmd += ["-i", str(music)]
        audio_indices.append(current_idx)
        current_idx += 1
    if not audio_indices:
        # generate silent audio so ffmpeg succeeds
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        audio_indices.append(current_idx)
        current_idx += 1

    video_filters, video_label = build_video_filters(
        len(images), subtitle, args.dark_overlay, args.zoom
    )
    filter_parts = video_filters
    audio_map: str
    if len(audio_indices) > 1:
        streams = "".join(f"[{i}:a]" for i in audio_indices)
        filter_parts.append(
            f"{streams}amix=inputs={len(audio_indices)}:duration=shortest[aout]"
        )
        audio_map = "[aout]"
    else:
        audio_map = f"{audio_indices[0]}:a"

    cmd += ["-filter_complex", "; ".join(filter_parts), "-map", video_label, "-map", audio_map]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", str(output_file)]

    return run_ffmpeg(cmd)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
