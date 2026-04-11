# Deploy

This project is deployed to the Intel NUC over SSH using the checked-out repo at:

- local: `/Users/gareth/src/dark-life`
- remote: `/home/gareth/src/dark-life`
- remote host: `ssh nuc`

## Standard deploy

1. Verify and test local changes.

```bash
cd /Users/gareth/src/dark-life
git status --short
pnpm --dir apps/web vitest run src/lib/utils.test.ts src/lib/jobs.test.ts
```

2. Commit and push from the local machine.

```bash
cd /Users/gareth/src/dark-life
git add <files>
git commit -m "Describe the change"
git push origin main
```

3. Pull and rebuild on the NUC.

```bash
ssh nuc '
  cd /home/gareth/src/dark-life &&
  git pull --ff-only origin main &&
  docker compose --env-file .env -f infra/docker-compose.yml \
    --profile renderer \
    --profile publisher \
    --profile scheduler \
    --profile insights \
    up -d --build \
    postgres api web renderer publisher scheduler insights refinement
'
```

4. If the change includes API schema or migration work, run migrations on the NUC before bringing the stack up.

```bash
ssh nuc '
  cd /home/gareth/src/dark-life &&
  git pull --ff-only origin main &&
  make migrate &&
  docker compose --env-file .env -f infra/docker-compose.yml \
    --profile renderer \
    --profile publisher \
    --profile scheduler \
    --profile insights \
    up -d --build \
    postgres api web renderer publisher scheduler insights refinement
'
```

5. Verify containers and health checks on the NUC.

```bash
ssh nuc '
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" &&
  curl -fsS http://localhost:8000/readyz &&
  curl -I http://localhost:3000
'
```

## Useful remote commands

Tail logs:

```bash
ssh nuc 'cd /home/gareth/src/dark-life && make logs'
```

Renderer logs only:

```bash
ssh nuc 'cd /home/gareth/src/dark-life && make renderer-logs'
```

Restart just the renderer:

```bash
ssh nuc 'cd /home/gareth/src/dark-life && make renderer'
```

Start only the partial app stack used by the existing Make target:

```bash
ssh nuc 'cd /home/gareth/src/dark-life && make up'
```

Start the full stack explicitly:

```bash
ssh nuc '
  cd /home/gareth/src/dark-life &&
  docker compose --env-file .env -f infra/docker-compose.yml \
    --profile renderer \
    --profile publisher \
    --profile scheduler \
    --profile insights \
    up -d --build \
    postgres api web renderer publisher scheduler insights refinement
'
```

Stop the stack:

```bash
ssh nuc 'cd /home/gareth/src/dark-life && make down'
```

## Notes

- The remote repo on the NUC is expected to stay on `main`.
- The deploy flow is `git push` locally, then `git pull --ff-only` on the NUC.
- `make up` is a partial stack only: `postgres api web renderer publisher`.
- `make all-up` adds `scheduler` but still does not start `insights` or `refinement`.
- For the full deployed stack on the NUC, use the explicit `docker compose ... up` command above.
- Do not commit local screenshots or scratch artifacts unless they are intentionally part of the release.
