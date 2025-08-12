import { NextResponse } from "next/server";

export async function POST() {
  return NextResponse.json({ id: "mock-job", status: "queued" });
}
