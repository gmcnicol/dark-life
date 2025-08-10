FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir praw requests typer langdetect

COPY services/reddit_ingestor /app/services/reddit_ingestor
COPY apps/api /app/apps/api
COPY shared /app/shared

ENV REDDIT_CLIENT_ID= \
    REDDIT_CLIENT_SECRET= \
    REDDIT_USER_AGENT=darklife/1.0 \
    REDDIT_DEFAULT_SUBREDDITS=

CMD ["python", "services/reddit_ingestor/cli.py", "incremental", "--subreddits", "$REDDIT_DEFAULT_SUBREDDITS"]

HEALTHCHECK CMD python -c "exit(0)"
