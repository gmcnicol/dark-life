# dark-life

Monorepo for automating short-form dark storytelling videos.

## Run the full stack

1. `cp .env.sample .env` and fill in API keys and secrets.
2. `docker compose -f infra/docker-compose.yml build`
3. `docker compose -f infra/docker-compose.yml up -d postgres redis`
4. `docker compose -f infra/docker-compose.yml up -d api web`
5. (optional) `docker compose -f infra/docker-compose.yml up -d renderer`
6. Visit <http://localhost:3000> for the web app and <http://localhost:8000/health> for the API.

## Renderer & Uploader

The renderer polls the database for jobs and writes videos to `./output`.

Run the uploader ad-hoc:

```bash
make uploader
```

Schedule uploads via cron or a CI system to run regularly.

## Reddit ingestion

Run incremental ingestion:

```bash
make ingest
```

Run a backfill with custom parameters:

```bash
make backfill EARLIEST=2008-01-01 SUBS="nosleep,confession"
```

An admin UI (if enabled) can also trigger ingestion jobs.

## Environment variables

See [`.env.sample`](.env.sample) for all configuration options.

## Troubleshooting

- Check container healthchecks with `docker compose ps`.
- Ensure the `./output` and `./secrets` directories have appropriate permissions.
- Image and Reddit providers enforce rate limits; retries may be required.
