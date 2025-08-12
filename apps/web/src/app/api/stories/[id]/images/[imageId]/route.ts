import { NextResponse } from "next/server";
import { stories } from "../../../../mock-data";

export async function PATCH(
  req: Request,
  { params }: { params: { id: string; imageId: string } }
) {
  const story = stories.find((s) => s.id === Number(params.id));
  if (!story) {
    return NextResponse.json({ message: "Not found" }, { status: 404 });
  }
  const image = story.images.find((i) => i.id === Number(params.imageId));
  if (!image) {
    return NextResponse.json({ message: "Not found" }, { status: 404 });
  }
  const patch = await req.json();
  Object.assign(image, patch);
  return NextResponse.json(image);
}
