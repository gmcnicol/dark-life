import { ReactNode } from "react";
import { getStory } from "@/lib/stories";

export default async function StoryLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: { id: string };
}) {
  const story = await getStory(Number(params.id));
  return (
    <div>
      <h1>{story.title}</h1>
      {children}
    </div>
  );
}
