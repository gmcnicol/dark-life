import { createClerkClient } from "@clerk/backend";

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function sendJson(res, status, payload) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

function clerkEnabled() {
  const value = process.env.CLERK_ENABLED ?? process.env.VITE_CLERK_ENABLED ?? "false";
  return value.toLowerCase() !== "false";
}

function parseCsv(value = "") {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function requestUrl(req) {
  const protoHeader = req.headers["x-forwarded-proto"];
  const proto = Array.isArray(protoHeader) ? protoHeader[0] : protoHeader || "http";
  const host = req.headers.host || "localhost";
  return new URL(req.url || "/", `${proto}://${host}`);
}

function copyHeaders(req, { includeCookies = true } = {}) {
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    const lower = key.toLowerCase();
    if (HOP_BY_HOP_HEADERS.has(lower)) {
      continue;
    }
    if (!includeCookies && lower === "cookie") {
      continue;
    }
    if (lower === "authorization") {
      continue;
    }
    if (Array.isArray(value)) {
      headers.set(key, value.join(", "));
    } else if (value) {
      headers.set(key, value);
    }
  }
  return headers;
}

function clerkClient() {
  const secretKey = process.env.CLERK_SECRET_KEY;
  if (!secretKey) {
    return null;
  }

  const publishableKey =
    process.env.CLERK_PUBLISHABLE_KEY || process.env.VITE_CLERK_PUBLISHABLE_KEY;

  return createClerkClient({
    secretKey,
    ...(publishableKey ? { publishableKey } : {}),
  });
}

async function requireClerkSession(req, res) {
  const client = clerkClient();
  if (!client) {
    sendJson(res, 500, { error: "Clerk is not configured on the web server" });
    return false;
  }

  const authOptions = {};
  const authorizedParties = parseCsv(process.env.CLERK_AUTHORIZED_PARTIES || "");
  if (authorizedParties.length) {
    authOptions.authorizedParties = authorizedParties;
  }
  if (process.env.CLERK_JWT_KEY) {
    authOptions.jwtKey = process.env.CLERK_JWT_KEY;
  }

  const authRequest = new Request(requestUrl(req), {
    method: req.method || "GET",
    headers: copyHeaders(req),
  });
  const { isAuthenticated } = await client.authenticateRequest(authRequest, authOptions);
  if (!isAuthenticated) {
    sendJson(res, 401, { error: "Unauthorized" });
    return false;
  }
  return true;
}

export function isAdminProxyRequest(url = "") {
  return url === "/api/admin" || url.startsWith("/api/admin/");
}

export async function handleAdminProxy(req, res, { apiBase }) {
  if (!isAdminProxyRequest(req.url || "")) {
    return false;
  }

  if (clerkEnabled() && !(await requireClerkSession(req, res))) {
    return true;
  }

  const adminToken = process.env.ADMIN_API_TOKEN || process.env.API_AUTH_TOKEN;
  if (!adminToken) {
    sendJson(res, 500, { error: "Admin API token is not configured" });
    return true;
  }

  const upstreamUrl = `${apiBase.replace(/\/$/, "")}${(req.url || "").replace(/^\/api/, "")}`;
  const headers = copyHeaders(req, { includeCookies: false });
  headers.set("authorization", `Bearer ${adminToken}`);
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
    if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
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
  return true;
}
