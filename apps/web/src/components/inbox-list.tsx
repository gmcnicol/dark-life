"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { Story } from "@/lib/stories";

export default function InboxList({ stories }: { stories: Story[] }) {
  const [index, setIndex] = useState(0);
  const router = useRouter();

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "j") {
        setIndex((current) => Math.min(current + 1, stories.length - 1));
      } else if (event.key === "k") {
        setIndex((current) => Math.max(current - 1, 0));
      } else if (event.key === "Enter") {
        const story = stories[index];
        if (story) {
          router.push(`/story/${story.id}/review`);
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [index, router, stories]);

  return (
    <ul className="space-y-3">
      {stories.map((story, storyIndex) => (
        <li
          key={story.id}
          data-selected={storyIndex === index || undefined}
          className={`rounded-3xl border p-4 ${
            storyIndex === index ? "border-amber-300 bg-amber-100/10" : "border-zinc-800 bg-zinc-950/70"
          }`}
        >
          <Link href={`/story/${story.id}/review`} className="flex items-center justify-between gap-4">
            <span className="text-lg font-medium text-zinc-100">{story.title}</span>
            <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs text-zinc-300">{story.status}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
