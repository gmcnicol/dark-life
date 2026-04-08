# syntax=docker/dockerfile:1

# Builder stage
FROM node:22-alpine AS builder
WORKDIR /app

ARG VITE_CLERK_ENABLED=false
ARG VITE_CLERK_PUBLISHABLE_KEY=
ENV VITE_CLERK_ENABLED=${VITE_CLERK_ENABLED}
ENV VITE_CLERK_PUBLISHABLE_KEY=${VITE_CLERK_PUBLISHABLE_KEY}

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
WORKDIR /app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/apps/web/node_modules ./apps/web/node_modules

WORKDIR /app/apps/web

ENV NODE_ENV=production

# copy built application and runtime deps
COPY --from=builder /app/apps/web/dist ./dist
COPY --from=builder /app/apps/web/server.mjs ./server.mjs
COPY --from=builder /app/apps/web/server ./server

ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.mjs"]
