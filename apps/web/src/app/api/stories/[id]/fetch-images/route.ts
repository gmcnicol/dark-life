/* eslint-disable @typescript-eslint/no-explicit-any */
import { NextRequest, NextResponse } from "next/server";
import { stories, nextImageId } from "../../../mock-data";

export async function POST(
  _req: NextRequest,
  { params }: any
) {
  const story = stories.find((s) => s.id === Number(params.id));
  if (!story) {
    return NextResponse.json({ message: "Not found" }, { status: 404 });
  }
  if (story.images.length === 0) {
    const first = nextImageId(story);
    story.images.push(
      {
        id: first,
        remote_url: "https://placekitten.com/200/200",
        selected: false,
        rank: 0,
      },
      {
        id: first + 1,
        remote_url: "https://placekitten.com/210/200",
        selected: false,
        rank: 1,
      }
    );
  }
  return NextResponse.json(story.images);
}
