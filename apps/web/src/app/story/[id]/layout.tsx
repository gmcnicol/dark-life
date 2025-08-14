import { ReactNode } from "react";
import { getStory } from "@/lib/stories";

export default async function StoryLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const story = await getStory(Number(id));
  return (
    <div>
      <h1>{story.title}</h1>
      {children}
    </div>
  );
}
