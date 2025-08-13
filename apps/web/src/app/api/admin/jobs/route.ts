import { NextRequest, NextResponse } from "next/server";
import { listJobs } from "./data";

export function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const storyId = searchParams.get("story_id");
  const jobs = listJobs(storyId ? Number(storyId) : undefined);
  return NextResponse.json(jobs);
}
