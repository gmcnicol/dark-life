"use client";

import { useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Release } from "@/lib/stories";
import { publishRelease } from "@/lib/stories";
import { ActionButton, EmptyState, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

export default function PublishQueue({ releases }: { releases: Release[] }) {
  const queryClient = useQueryClient();
  const [videoIds, setVideoIds] = useState<Record<number, string>>({});
  const [isPending, startTransition] = useTransition();

  const submit = (releaseId: number) => {
    startTransition(async () => {
      await publishRelease(releaseId, videoIds[releaseId]);
      await queryClient.invalidateQueries();
    });
  };

  if (releases.length === 0) {
    return (
      <EmptyState
        title="Nothing is publish-ready"
        description="Rendered releases will land here once the pipeline clears them for manual posting."
      />
    );
  }

  return (
    <div className="space-y-4">
      {releases.map((release) => (
        <Panel key={release.id} className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold text-white">{release.title}</h2>
              <p className="mt-2 text-sm text-[var(--text-soft)]">
                {release.platform} · {release.variant}
              </p>
            </div>
            <StatusBadge tone="success">Ready</StatusBadge>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--text-soft)]">
            {release.description}
          </p>
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
            <input
              value={videoIds[release.id] ?? ""}
              onChange={(event) =>
                setVideoIds((current) => ({ ...current, [release.id]: event.target.value }))
              }
              placeholder="Platform video id (optional)"
              className="w-full rounded-[1.2rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
            />
            <ActionButton onClick={() => submit(release.id)} disabled={isPending}>
              Mark published
            </ActionButton>
          </div>
        </Panel>
      ))}
    </div>
  );
}
