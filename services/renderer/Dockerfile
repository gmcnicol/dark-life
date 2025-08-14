FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# Install required Python packages for the renderer service.
# Include config dependencies (pydantic & pydantic-settings) and
# networking library `requests` used by the poller.
RUN pip install --no-cache-dir \
    faster-whisper \
    pydub \
    typer \
    requests \
    pydantic \
    pydantic-settings

COPY services/renderer /app/services/renderer
COPY apps/api /app/apps/api
COPY shared /app/shared
COPY video_renderer /app/video_renderer

# Ensure project packages like "shared" are importable when running
# the poller as a script.
ENV PYTHONPATH=/app \
    WHISPER_MODEL=base \
    OUTPUT_DIR=/output \
    TMPDIR=/tmp/render \
    PYTHONUNBUFFERED=1

VOLUME ["/output"]

CMD ["python", "-u", "services/renderer/poller.py"]

HEALTHCHECK CMD ["python", "-m", "services.renderer.healthcheck"]
