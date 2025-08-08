# dark-life

Monorepo for automating short-form dark storytelling videos.

## Services

- **webapp/** – Flask UI for fetching and preparing stories. Generates render jobs in `render_queue/`.
- **video_renderer/** – Polls render jobs and builds final videos and manifests.
- **video_uploader/** – Cron-style uploader that reads manifests and posts videos to social platforms.
- **shared/** – Common utilities and configuration.

## Development

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
make init
```

Run individual services:

```bash
make run-webapp      # start the Flask app
make run-renderer    # process queued render jobs
make run-uploader    # upload finished videos
```

## Configuration

Copy `sample.env` to `.env` and fill in required API keys for services like Reddit and Instagram.
