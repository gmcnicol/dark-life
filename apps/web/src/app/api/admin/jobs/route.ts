import { NextRequest, NextResponse } from "next/server";
import { adminApiFetch } from "../fetch";

export async function GET(req: NextRequest) {
  const res = await adminApiFetch(`/admin/jobs${req.nextUrl.search}`);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
