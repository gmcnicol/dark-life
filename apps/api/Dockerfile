FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY alembic.ini /app/alembic.ini
COPY apps/api /app/apps/api
COPY services/reddit_ingestor /app/services/reddit_ingestor
COPY shared /app/shared

ENV PYTHONPATH=/app

ENV PORT=8000 \
    DATABASE_URL= \
    REDIS_URL= \
    PEXELS_API_KEY= \
    PIXABAY_API_KEY= \
    ADMIN_API_TOKEN=

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
