"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Release } from "@/lib/stories";
import { publishRelease } from "@/lib/stories";

export default function PublishQueue({ releases }: { releases: Release[] }) {
  const router = useRouter();
  const [videoIds, setVideoIds] = useState<Record<number, string>>({});
  const [isPending, startTransition] = useTransition();

  const submit = (releaseId: number) => {
    startTransition(async () => {
      await publishRelease(releaseId, videoIds[releaseId]);
      router.refresh();
    });
  };

  if (releases.length === 0) {
    return <p className="text-sm text-zinc-400">Nothing is publish-ready yet.</p>;
  }

  return (
    <div className="space-y-4">
      {releases.map((release) => (
        <div key={release.id} className="rounded-3xl border border-zinc-800 bg-zinc-950/70 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">{release.title}</h2>
              <p className="mt-1 text-xs uppercase tracking-[0.25em] text-zinc-500">
                {release.platform} · {release.variant}
              </p>
            </div>
            <button
              onClick={() => submit(release.id)}
              disabled={isPending}
              className="rounded-full bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950"
            >
              Mark Published
            </button>
          </div>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-zinc-300">
            {release.description}
          </p>
          <input
            value={videoIds[release.id] ?? ""}
            onChange={(event) =>
              setVideoIds((current) => ({ ...current, [release.id]: event.target.value }))
            }
            placeholder="Platform video id (optional)"
            className="mt-4 w-full rounded-2xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-100"
          />
        </div>
      ))}
    </div>
  );
}
