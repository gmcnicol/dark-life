"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { Story } from "@/lib/stories";

export default function InboxList({ stories }: { stories: Story[] }) {
  const [index, setIndex] = useState(0);
  const router = useRouter();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "j") {
        setIndex((i) => Math.min(i + 1, stories.length - 1));
      } else if (e.key === "k") {
        setIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        const story = stories[index];
        if (story) {
          router.push(`/story/${story.id}/review`);
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [index, stories, router]);

  return (
    <ul>
      {stories.map((story, i) => (
        <li
          key={story.id}
          data-selected={i === index || undefined}
          className={i === index ? "bg-gray-200" : undefined}
        >
          <Link href={`/story/${story.id}/review`}>{story.title}</Link>
        </li>
      ))}
    </ul>
  );
}
