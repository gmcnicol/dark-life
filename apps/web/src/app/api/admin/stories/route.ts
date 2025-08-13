import { NextRequest, NextResponse } from "next/server";
import { listStories } from "./data";

export function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const status = searchParams.get("status");
  let stories = listStories();
  if (status) {
    stories = stories.filter((s) => s.status === status);
  }
  return NextResponse.json(stories);
}
