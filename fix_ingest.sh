#!/usr/bin/env bash
set -euo pipefail

# fix_ingestor_setup.sh — patch reddit_ingestor so it builds cleanly (no run)
# - Ensures services/reddit_ingestor/requirements.txt has required deps
# - Adds shared/ package with config (if missing)
# - Rewrites services/reddit_ingestor/Dockerfile to include shared/ and set PYTHONPATH
# - Normalizes .env DATABASE_URL for Docker
# - Rebuilds ONLY the reddit_ingestor image
#
# Run from repo root: ./infra/docker-compose.yml must exist.

ROOT_REQ="services/reddit_ingestor/requirements.txt"
DF_PATH="services/reddit_ingestor/Dockerfile"
ENV_PATH=".env"

# sanity
[[ -f "infra/docker-compose.yml" ]] || { echo "Run from repo root (infra/docker-compose.yml missing)"; exit 1; }
[[ -d "services/reddit_ingestor" ]] || { echo "services/reddit_ingestor not found"; exit 1; }
[[ -f "services/reddit_ingestor/cli.py" ]] || { echo "services/reddit_ingestor/cli.py not found"; exit 1; }

echo ">> Ensuring shared/ package exists"
mkdir -p shared
[[ -f shared/__init__.py ]] || : > shared/__init__.py
if [[ ! -f shared/config.py ]]; then
  cat > shared/config.py <<'PY'
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@postgres:5432/darklife"
    REDIS_URL: str = "redis://redis:6379/0"

    ADMIN_API_TOKEN: Optional[str] = None

    PEXELS_API_KEY: Optional[str] = None
    PIXABAY_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ELEVENLABS_API_KEY: Optional[str] = None
    WHISPER_MODEL: str = "base"

    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None
    REDDIT_USER_AGENT: str = "darklife/1.0"
    REDDIT_DEFAULT_SUBREDDITS: str = "nosleep,confession"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
PY
  echo "   created shared/config.py"
else
  echo "   shared/config.py already present"
fi

echo ">> Ensuring reddit_ingestor requirements"
mkdir -p "$(dirname "$ROOT_REQ")"
if [[ ! -f "$ROOT_REQ" ]]; then
  cat > "$ROOT_REQ" <<'REQS'
sqlalchemy>=2.0
psycopg[binary]>=3.1
praw>=7.7
requests>=2.31
typer>=0.12
pydantic>=2.6
pydantic-settings>=2.4
python-dotenv>=1.0
langdetect>=1.0.9
prometheus_client>=0.20
REQS
  echo "   created $ROOT_REQ"
else
  # append missing essentials if not already listed
  ensure() { grep -q "^[[:space:]]*$1\(\>|[[:space:]]\|$\)" "$ROOT_REQ" || echo "$1" >> "$ROOT_REQ"; }
  ensure 'sqlalchemy>=2.0'
  ensure 'psycopg[binary]>=3.1'
  ensure 'praw>=7.7'
  ensure 'typer>=0.12'
  ensure 'pydantic>=2.6'
  ensure 'pydantic-settings>=2.4'
  ensure 'prometheus_client>=0.20'
  echo "   updated $ROOT_REQ if needed"
fi

echo ">> Writing reddit_ingestor Dockerfile (backup if exists)"
[[ -f "$DF_PATH" ]] && cp "$DF_PATH" "${DF_PATH}.bak.$(date +%s)" || true
cat > "$DF_PATH" <<'DOCKERFILE'
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# optional build tools (safer for wheels/source builds)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# dependencies first (cache layer)
COPY services/reddit_ingestor/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# shared package for imports like "from shared.config import settings"
COPY shared/ ./shared/

# service code
COPY services/reddit_ingestor/ ./services/reddit_ingestor/

# if ingestor imports other repo code, copy here (uncomment if needed)
# COPY apps/api/ ./apps/api/
# COPY services/shared_lib/ ./services/shared_lib/

ENTRYPOINT ["python", "-m", "services.reddit_ingestor.cli"]
CMD ["--help"]
DOCKERFILE
echo "   wrote $DF_PATH"

echo ">> Normalizing .env for Docker compose"
if [[ ! -f "$ENV_PATH" ]]; then
  cat > "$ENV_PATH" <<'ENVF'
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/darklife
REDIS_URL=redis://redis:6379/0
ENVF
  echo "   created .env with defaults"
else
  # force host=postgres (service name) for compose
  if grep -q '^DATABASE_URL=' "$ENV_PATH"; then
    sed -i.bak 's#^DATABASE_URL=.*#DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/darklife#' "$ENV_PATH"
  else
    echo 'DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/darklife' >> "$ENV_PATH"
  fi
  if ! grep -q '^REDIS_URL=' "$ENV_PATH"; then
    echo 'REDIS_URL=redis://redis:6379/0' >> "$ENV_PATH"
  fi
  echo "   updated .env"
fi

echo ">> Rebuilding reddit_ingestor image (no cache)"
docker compose -f infra/docker-compose.yml build --no-cache reddit_ingestor

echo
echo "All set. reddit_ingestor now builds with shared/ and required deps."
echo "Next steps:"
echo "  - Set REDDIT_DEFAULT_SUBREDDITS in .env"
echo "  - To run incremental: docker compose -f infra/docker-compose.yml --profile ops run --rm reddit_ingestor incremental"
echo "  - To run backfill:    docker compose -f infra/docker-compose.yml --profile ops run --rm reddit_ingestor backfill"
