"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import type { StoryStatus } from "@dark-life/shared-types";
import type { ScriptVersion, Story } from "@/lib/stories";
import { generateScript, updateStoryStatus } from "@/lib/stories";

export default function ReviewBar({
  story,
  activeScript,
}: {
  story: Story;
  activeScript: ScriptVersion | null;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const run = (action: () => Promise<unknown>) => {
    startTransition(async () => {
      await action();
      router.refresh();
    });
  };

  const changeStatus = (status: StoryStatus) => {
    run(() => updateStoryStatus(story.id, status));
  };

  return (
    <div className="space-y-4 rounded-2xl border border-zinc-800 bg-zinc-950/70 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <span data-testid="status" className="rounded-full bg-zinc-800 px-3 py-1 text-sm">
          Status: {story.status}
        </span>
        <button
          onClick={() => run(() => generateScript(story.id))}
          className="rounded-full bg-amber-300 px-4 py-2 text-sm font-medium text-zinc-950"
          disabled={isPending}
        >
          {activeScript ? "Regenerate Script" : "Generate Script"}
        </button>
        <button
          onClick={() => changeStatus("approved")}
          className="rounded-full border border-emerald-400 px-4 py-2 text-sm text-emerald-200"
          disabled={isPending}
        >
          Approve Story
        </button>
        <button
          onClick={() => changeStatus("rejected")}
          className="rounded-full border border-red-400 px-4 py-2 text-sm text-red-200"
          disabled={isPending}
        >
          Reject
        </button>
      </div>
      <div className="flex flex-wrap gap-3 text-sm text-zinc-300">
        <Link href={`/story/${story.id}/split`} className="underline underline-offset-4">
          Edit Parts
        </Link>
        <Link href={`/story/${story.id}/media`} className="underline underline-offset-4">
          Choose Media
        </Link>
        <Link href={`/story/${story.id}/queue`} className="underline underline-offset-4">
          Queue Renders
        </Link>
        <Link href={`/story/${story.id}/jobs`} className="underline underline-offset-4">
          Track Jobs
        </Link>
      </div>
    </div>
  );
}
