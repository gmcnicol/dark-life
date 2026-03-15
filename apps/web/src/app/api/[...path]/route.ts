import { NextRequest, NextResponse } from "next/server";
import { adminApiFetch } from "../admin/fetch";

async function proxy(req: NextRequest, path: string[]) {
  const search = req.nextUrl.search || "";
  const pathname = `/${path.join("/")}${search}`;
  const init: RequestInit = {
    method: req.method,
    headers: req.headers,
  };
  if (!["GET", "HEAD"].includes(req.method)) {
    init.body = await req.text();
  }
  const res = await adminApiFetch(pathname, init);
  const body = await res.text();
  return new NextResponse(body, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("Content-Type") || "application/json",
    },
  });
}

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  return proxy(req, path);
}

export async function POST(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  return proxy(req, path);
}

export async function PUT(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  return proxy(req, path);
}

export async function PATCH(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  return proxy(req, path);
}

export async function DELETE(
  req: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  return proxy(req, path);
}
