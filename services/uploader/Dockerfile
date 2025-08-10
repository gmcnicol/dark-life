FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir google-api-python-client google-auth-oauthlib typer

COPY services/uploader /app/services/uploader
COPY video_uploader /app/video_uploader
COPY apps/api /app/apps/api
COPY shared /app/shared

ENV OUTPUT_DIR=/output \
    YOUTUBE_CLIENT_SECRETS= \
    YOUTUBE_TOKEN=

VOLUME ["/output"]

CMD ["python", "video_uploader/cron_upload.py", "--once"]

HEALTHCHECK CMD python -c "exit(0)"
