import { NextRequest, NextResponse } from "next/server";
import { findStory, updateStory } from "../data";

export function GET(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  const story = findStory(Number(params.id));
  if (!story) {
    return new NextResponse("Not found", { status: 404 });
  }
  return NextResponse.json(story);
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const body = await req.json();
  const story = updateStory(Number(params.id), body);
  return NextResponse.json(story);
}
