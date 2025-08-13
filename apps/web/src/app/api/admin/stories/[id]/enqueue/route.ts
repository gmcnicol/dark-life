import { NextRequest, NextResponse } from "next/server";
import { addJobs } from "../../../jobs/data";

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  const jobs = addJobs([
    { story_id: Number(params.id), kind: "render", status: "queued" },
  ]);
  return NextResponse.json({ jobs });
}
