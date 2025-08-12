/* eslint-disable @typescript-eslint/no-explicit-any */
import { NextRequest, NextResponse } from "next/server";
import { stories } from "../../mock-data";

export async function GET(
  _req: NextRequest,
  { params }: any
) {
  const story = stories.find((s) => s.id === Number(params.id));
  if (!story) {
    return NextResponse.json({ message: "Not found" }, { status: 404 });
  }
  return NextResponse.json(story);
}

export async function PATCH(
  req: NextRequest,
  { params }: any
) {
  const story = stories.find((s) => s.id === Number(params.id));
  if (!story) {
    return NextResponse.json({ message: "Not found" }, { status: 404 });
  }
  const patch = await req.json();
  Object.assign(story, patch);
  return NextResponse.json(story);
}

export async function DELETE(
  _req: NextRequest,
  { params }: any
) {
  const index = stories.findIndex((s) => s.id === Number(params.id));
  if (index === -1) {
    return NextResponse.json({ message: "Not found" }, { status: 404 });
  }
  stories.splice(index, 1);
  return NextResponse.json({});
}
