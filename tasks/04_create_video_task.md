# Task 04: Create Final Video with FFmpeg

## Goal
Create a complete video with image sequence, narration, background music, and burned-in subtitles using only FFmpeg.

## Requirements
- Create `scripts/create_video.py`
- Input:
  - 1+ images (`content/visuals/story01_*.jpg`)
  - 1x voiceover
  - 1x music loop
  - 1x subtitle (`.srt` or `.ass`)
- Output:
  - `output/videos/story01_final.mp4`
- Optional:
  - Pan/zoom on stills
  - Crossfade or dark filters

## CLI Example
```bash
python create_video.py --story_id story01
```
