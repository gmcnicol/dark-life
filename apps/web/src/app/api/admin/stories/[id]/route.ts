import { NextRequest, NextResponse } from "next/server";
import { adminApiFetch } from "../../fetch";

export async function GET(
  _req: NextRequest,
  { params }: any, // eslint-disable-line @typescript-eslint/no-explicit-any
) {
  const res = await adminApiFetch(`/admin/stories/${params.id}`);
  if (res.status === 404) {
    return new NextResponse("Not found", { status: 404 });
  }
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function PATCH(
  req: NextRequest,
  { params }: any, // eslint-disable-line @typescript-eslint/no-explicit-any
) {
  const res = await adminApiFetch(`/admin/stories/${params.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
