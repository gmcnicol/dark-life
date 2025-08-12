import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "";

async function handler(
  req: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  let path = params.path?.join("/") ?? "";
  if (path.endsWith("/enqueue-render")) {
    path = path.replace(/\/enqueue-render$/, "/enqueue-series");
  }
  const url = `${API_BASE_URL}/api/stories/${path}${req.nextUrl.search}`;
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await req.text();
  const res = await fetch(url, {
    method: req.method,
    headers: {
      ...(req.headers.get("content-type")
        ? { "Content-Type": req.headers.get("content-type") as string }
        : {}),
    },
    body,
  });
  const text = await res.text();
  return new NextResponse(text, { status: res.status, headers: res.headers });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
