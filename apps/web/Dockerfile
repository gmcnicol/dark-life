FROM node:20-alpine
WORKDIR /app

# copy manifest(s). This pattern copies package.json and, if present, package-lock.json
COPY package*.json ./

# install deps (prefer lockfile if present)
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# copy the rest of the app
COPY . .

EXPOSE 3000
CMD ["npm","run","dev"]
