import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "";

export async function GET(req: NextRequest) {
  const url = `${API_BASE_URL}/stories${req.nextUrl.search}`;
  const res = await fetch(url);
  const text = await res.text();
  return new NextResponse(text, { status: res.status, headers: res.headers });
}

export async function POST(req: NextRequest) {
  const body = await req.text();
  const res = await fetch(`${API_BASE_URL}/stories`, {
    method: "POST",
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
