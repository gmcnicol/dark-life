import { NextRequest, NextResponse } from "next/server";
import { findStory, updateStory } from "../../data";

const WORDS_PER_MINUTE = 160;
const WORDS_PER_SECOND = WORDS_PER_MINUTE / 60;

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const story = findStory(Number(params.id));
  if (!story) {
    return new NextResponse("Not found", { status: 404 });
  }
  const body = await req.json();
  const parts: string[] = Array.isArray(body.parts) ? body.parts : [];
  const resp = parts.map((text, idx) => {
    const words = text.trim().split(/\s+/).filter(Boolean).length;
    const est_seconds = Math.round(words / WORDS_PER_SECOND);
    return { index: idx + 1, body_md: text, est_seconds };
  });
  updateStory(story.id, { status: "split" });
  return NextResponse.json(resp);
}
