import { NextResponse } from "next/server";
import { stories, nextStoryId, Story } from "../mock-data";

export async function GET() {
  const list = stories.map(({ id, title }) => ({ id, title }));
  return NextResponse.json(list);
}

export async function POST(req: Request) {
  const body = await req.json();
  const story: Story = {
    id: nextStoryId(),
    title: body.title ?? "Untitled story",
    body_md: body.body_md ?? "",
    status: "draft",
    images: [],
  };
  stories.push(story);
  return NextResponse.json(story, { status: 201 });
}
