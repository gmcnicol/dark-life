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
