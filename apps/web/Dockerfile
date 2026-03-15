# syntax=docker/dockerfile:1

# Builder stage
FROM node:22-alpine AS builder
WORKDIR /app

# install pnpm
RUN npm install -g pnpm

# copy dependency manifests
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web/package.json apps/web/package.json

# install dependencies for web workspace
RUN pnpm install --frozen-lockfile --filter web...

# copy source and build
COPY . .
RUN pnpm --filter web build

# Runner stage
FROM node:22-alpine AS runner
WORKDIR /app/apps/web

ENV NODE_ENV=production

# install pnpm for runtime scripts
RUN npm install -g pnpm

# copy built application and runtime deps
COPY --from=builder /app/node_modules /app/node_modules
COPY --from=builder /app/apps/web/dist ./dist
COPY --from=builder /app/apps/web/package.json ./package.json
COPY --from=builder /app/apps/web/node_modules ./node_modules

ENV PORT=3000
EXPOSE 3000

CMD ["./node_modules/.bin/vite", "preview", "--host", "0.0.0.0", "--port", "3000"]
