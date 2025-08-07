# Task 03: Generate Subtitles with Whisper

## Goal
Use Whisper to transcribe the `.mp3` voiceovers into `.srt` or `.ass` subtitle files.

## Requirements
- Create `scripts/generate_subtitles.py`
- Input: `content/audio/voiceovers/*.mp3`
- Output: `.srt` or `.ass` files with same basename
- CLI configurable: `--format srt|ass`
- Support batching (transcribe all voiceovers at once)
