FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cargo \
    ffmpeg \
    rustc \
    && rm -rf /var/lib/apt/lists/*

# Use the official CPU-only PyTorch wheel channel so the renderer does not pull
# hundreds of megabytes of unused CUDA packages.
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.10.0 \
    torchaudio==2.10.0

# Install required Python packages for the renderer service.
# Include config dependencies (pydantic & pydantic-settings) and
# networking library `requests` used by the poller.
RUN pip install --no-cache-dir \
    "TTS==0.22.0" \
    "trainer>=0.0.36" \
    "transformers==4.41.2" \
    faster-whisper \
    pydub \
    soundfile \
    typer \
    requests \
    pydantic \
    pydantic-settings

COPY services/renderer /app/services/renderer
COPY services/scheduler /app/services/scheduler
COPY apps/api /app/apps/api
COPY shared /app/shared

# Ensure project packages like "shared" are importable when running
# the poller as a script.
ENV PYTHONPATH=/app \
    WHISPER_MODEL=base \
    WHISPER_PROVIDER=local \
    OUTPUT_DIR=/output \
    REMOTE_ASSET_CACHE_DIR=/content/cache/remote-assets \
    TMP_DIR=/tmp/renderer \
    PYTHONUNBUFFERED=1

VOLUME ["/output"]

CMD ["python", "-u", "-m", "services.renderer.poller"]

HEALTHCHECK CMD ["python", "-m", "services.renderer.healthcheck"]
