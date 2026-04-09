FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests google-api-python-client google-auth-oauthlib pydantic pydantic-settings python-dotenv

COPY services/insights /app/services/insights
COPY shared /app/shared

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=insights

CMD ["python", "-u", "-m", "services.insights.poller"]

HEALTHCHECK CMD python -m services.insights.healthcheck
