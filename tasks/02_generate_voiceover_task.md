# Task 02: Generate Voiceover

## Goal
Convert each Markdown Reddit story into an AI voiceover using ElevenLabs or another TTS provider.

## Requirements
- Create `scripts/generate_voiceover.py`
- Accept input from `content/stories/*.md`
- Output to `content/audio/voiceovers/*.mp3`
- Use environment variable for API key

## Options
Use `pyttsx3` as fallback if no API key is available
