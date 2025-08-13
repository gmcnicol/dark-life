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

# prune dev dependencies
RUN pnpm prune --prod --filter web...

# Runner stage
FROM node:22-alpine AS runner
WORKDIR /app

# install pnpm for runtime scripts
RUN npm install -g pnpm
ENV NODE_ENV=production

# copy built application and production deps
COPY --from=builder /app/apps/web/.next ./.next
COPY --from=builder /app/apps/web/public ./public
COPY --from=builder /app/apps/web/next.config.ts ./next.config.ts
COPY --from=builder /app/apps/web/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules

# set runtime variables
ENV PORT=3000
EXPOSE 3000

CMD ["pnpm", "start"]
