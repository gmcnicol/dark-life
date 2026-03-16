FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir requests google-api-python-client google-auth-oauthlib pydantic pydantic-settings python-dotenv

COPY services/publisher /app/services/publisher
COPY shared /app/shared

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=publisher

CMD ["python", "-u", "-m", "services.publisher.poller"]

HEALTHCHECK CMD python -m services.publisher.healthcheck
