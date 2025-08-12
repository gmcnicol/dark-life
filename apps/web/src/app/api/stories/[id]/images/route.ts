import { NextResponse } from "next/server";
import { stories } from "../../../mock-data";

export async function GET(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const story = stories.find((s) => s.id === Number(params.id));
  if (!story) {
    return NextResponse.json({ message: "Not found" }, { status: 404 });
  }
  return NextResponse.json(story.images);
}
