import { NextRequest, NextResponse } from "next/server";
import { adminApiFetch } from "../../../fetch";

export async function POST(
  req: NextRequest,
  { params }: any, // eslint-disable-line @typescript-eslint/no-explicit-any
) {
  const res = await adminApiFetch(`/admin/stories/${params.id}/split`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
