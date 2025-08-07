# AGENT.md

## 🎯 Project Goal

Automate the creation of short-form dark storytelling videos sourced from Reddit posts using TTS, public domain images, spooky music, and auto-generated subtitles. The system should be fully automated with minimal human involvement — no more than 1 hour per week of manual image and story selection.

## 🧱 Architecture Summary

- **Input**: Reddit threads (`r/nosleep`, `r/confession`, etc.)
- **Voiceover**: ElevenLabs or Whisper-compatible TTS
- **Visuals**: Public domain assets dropped manually into `content/visuals/`
- **Music**: Supplied by user (`content/audio/music/`)
- **Video**: Created using `ffmpeg` (no MoviePy)
- **Subtitles**: Auto-generated via Whisper, burned in with FFmpeg
- **Dashboard**: Static web UI for video pipeline monitoring

## ⚙️ Project Structure

```
dark-story-pipeline/
├── content/
│   ├── stories/         # Markdown Reddit threads
│   ├── visuals/         # User-supplied stills
│   └── audio/
│       ├── voiceovers/
│       └── music/
├── output/
│   └── videos/
├── scripts/
│   ├── fetch_reddit.py
│   ├── generate_voiceover.py
│   ├── generate_subtitles.py
│   ├── create_video.py
│   ├── schedule_post.py
│   └── update_dashboard.py
├── dashboard/
│   └── index.html
├── tasks/
│   └── <codex-tasks here>
├── run_pipeline.py
└── AGENT.md
```

## 🧠 Codex Instructions

Codex should work through each task in the `/tasks` folder and update the respective files under `/scripts`, `/dashboard`, or `run_pipeline.py`. After each task, the project should be functional and independently testable via `make`, `run_pipeline.py`, or direct CLI execution.

## ✅ Dependencies

- `ffmpeg` (installed)
- `openai-whisper` or `whisper.cpp`
- `praw` (Reddit API)
- `requests`, `pydub`, `jinja2`, `typer`
- Optional: `instagrapi`, `sqlite`, `flask`

## ✅ Output Requirements

- Daily videos in `output/videos/` with:
  - Burned-in subtitles
  - User-supplied visuals
  - User-supplied background music
- Fully automated pipeline script
- Static dashboard in `dashboard/index.html` showing pipeline status

## 🔒 User Will Supply

- Weekly curated images: `content/visuals/storyXX_01.jpg`, etc.
- Background music: `content/audio/music/*.mp3`
- ElevenLabs API key (if voice synthesis used)
