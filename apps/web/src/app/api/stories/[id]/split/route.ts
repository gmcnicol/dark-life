import { NextResponse } from "next/server";
import { stories } from "../../../../mock-data";

export async function POST(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const story = stories.find((s) => s.id === Number(params.id));
  if (!story) {
    return NextResponse.json([], { status: 404 });
  }
  const part = {
    id: 1,
    index: 0,
    body_md: story.body_md,
    est_seconds: Math.ceil(story.body_md.length / 5),
  };
  return NextResponse.json([part]);
}
