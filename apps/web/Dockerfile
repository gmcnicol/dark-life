FROM node:20-alpine

WORKDIR /app

COPY package.json pnpm-lock.yaml ./
RUN npm install

COPY . .

ENV NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
    NODE_ENV=development

EXPOSE 3000

CMD ["npm", "run", "dev"]

HEALTHCHECK CMD wget -qO- http://localhost:3000 || exit 1
