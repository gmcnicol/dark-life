import Link from "next/link";
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
    <div className="space-y-6">
      <div className="rounded-3xl border border-zinc-800 bg-zinc-950/70 p-5">
        <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">Story Workspace</p>
        <h1 className="mt-2 text-3xl font-semibold text-zinc-50">{story.title}</h1>
        <div className="mt-4 flex flex-wrap gap-4 text-sm text-zinc-300">
          <Link href={`/story/${id}/review`} className="underline underline-offset-4">
            Review
          </Link>
          <Link href={`/story/${id}/split`} className="underline underline-offset-4">
            Parts
          </Link>
          <Link href={`/story/${id}/media`} className="underline underline-offset-4">
            Media
          </Link>
          <Link href={`/story/${id}/queue`} className="underline underline-offset-4">
            Queue
          </Link>
          <Link href={`/story/${id}/jobs`} className="underline underline-offset-4">
            Jobs
          </Link>
        </div>
      </div>
      {children}
    </div>
  );
}
