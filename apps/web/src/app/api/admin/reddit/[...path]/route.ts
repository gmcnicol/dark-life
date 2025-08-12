import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "";
const ADMIN_TOKEN = process.env.ADMIN_API_TOKEN || "";

async function handler(
  req: NextRequest,
  { params }: { params: { path?: string[] } }
) {
  const path = params.path?.join("/") ?? "";
  const url = `${API_BASE_URL}/api/admin/reddit/${path}${req.nextUrl.search}`;
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await req.text();
  const res = await fetch(url, {
    method: req.method,
    headers: {
      ...(req.headers.get("content-type")
        ? { "Content-Type": req.headers.get("content-type") as string }
        : {}),
      "X-Admin-Token": ADMIN_TOKEN,
    },
    body,
  });
  const text = await res.text();
  return new NextResponse(text, { status: res.status, headers: res.headers });
}

export { handler as GET, handler as POST };
