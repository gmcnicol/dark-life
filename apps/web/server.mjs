import { createReadStream, existsSync } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.join(__dirname, "dist");
const indexPath = path.join(distDir, "index.html");
const port = Number(process.env.PORT || "3000");
const apiBase = (process.env.API_BASE_URL || "http://api:8000").replace(/\/$/, "");

const contentTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".ico", "image/x-icon"],
  [".woff2", "font/woff2"],
]);

function send(res, status, body, headers = {}) {
  res.writeHead(status, headers);
  res.end(body);
}

async function serveFile(res, filePath) {
  const ext = path.extname(filePath);
  const fileStat = await stat(filePath);
  res.writeHead(200, {
    "Content-Type": contentTypes.get(ext) || "application/octet-stream",
    "Content-Length": fileStat.size,
    "Cache-Control": ext === ".html" ? "no-cache" : "public, max-age=31536000, immutable",
  });
  createReadStream(filePath).pipe(res);
}

async function proxyApi(req, res) {
  const upstreamUrl = `${apiBase}${req.url.replace(/^\/api/, "")}`;
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (Array.isArray(value)) {
      headers.set(key, value.join(", "));
    } else if (value) {
      headers.set(key, value);
    }
  }
  headers.set("host", new URL(apiBase).host);

  const method = req.method || "GET";
  const canHaveBody = !["GET", "HEAD"].includes(method);
  const upstream = await fetch(upstreamUrl, {
    method,
    headers,
    body: canHaveBody ? req : undefined,
    duplex: canHaveBody ? "half" : undefined,
  });

  const responseHeaders = {};
  upstream.headers.forEach((value, key) => {
    if (key.toLowerCase() !== "transfer-encoding") {
      responseHeaders[key] = value;
    }
  });

  res.writeHead(upstream.status, responseHeaders);
  if (upstream.body) {
    for await (const chunk of upstream.body) {
      res.write(chunk);
    }
  }
  res.end();
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host}`);
    if (url.pathname.startsWith("/api/") || url.pathname === "/api") {
      await proxyApi(req, res);
      return;
    }

    const requestedPath =
      url.pathname === "/" ? indexPath : path.join(distDir, decodeURIComponent(url.pathname));
    const safePath = path.normalize(requestedPath);

    if (!safePath.startsWith(distDir)) {
      send(res, 403, "Forbidden");
      return;
    }

    if (existsSync(safePath) && (await stat(safePath)).isFile()) {
      await serveFile(res, safePath);
      return;
    }

    const index = await readFile(indexPath);
    send(res, 200, index, { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache" });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown server error";
    send(res, 500, message, { "Content-Type": "text/plain; charset=utf-8" });
  }
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Dark Life web listening on http://0.0.0.0:${port}`);
});
