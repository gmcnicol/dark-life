# Renderer Runbooks

## Fresh run
1. Build and start the renderer service:
   ```bash
   docker compose -f infra/docker-compose.yml up --build renderer
   ```
2. Follow logs to verify lifecycle events (`start` → `poll` → `preflight` → `rendering` → `done`):
   ```bash
   docker compose -f infra/docker-compose.yml logs -f --tail=0 renderer
   ```

## No output showing
- Confirm unbuffered execution (`PYTHONUNBUFFERED=1` and `python -u`).
- Run the renderer directly to surface stdout/stderr:
  ```bash
  docker compose -f infra/docker-compose.yml run --rm --no-deps renderer \
    python -u video_renderer/create_slideshow.py \
    --stories-path /content/stories \
    --output /output \
    --music-dir /content/audio/music
  ```
- Add `--debug` for verbose logs. Inspect the `FFREPORT` file path printed in logs for ffmpeg diagnostics.

## Audio missing
- Verify music directory contents:
  ```bash
  docker compose -f infra/docker-compose.yml run --rm --no-deps renderer ls -l /content/audio/music
  ```
- Preflight logs should display `chosen_track`. If the directory is empty, ensure `./content` on the host is mounted to `/content`.
- With multiple tracks, the first sorted file is chosen by default; set `--music-select=named:background.mp3` if a specific track is needed.

## Disk/space issues
- When `--debug` is enabled, preflight emits `df -h`. Rendering refuses to start when free space is below 2 GB.
- Clean up temp directories after runs:
  ```bash
  docker compose -f infra/docker-compose.yml run --rm --no-deps renderer rm -rf /tmp/renderer/*
  ```
- Inspect disk usage if jobs fail unexpectedly:
  ```bash
  docker compose -f infra/docker-compose.yml run --rm --no-deps renderer df -h /
  ```
