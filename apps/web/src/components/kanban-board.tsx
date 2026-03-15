"use client";

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { StoryStatus } from "@dark-life/shared-types";
import { listStories } from "@/lib/stories";
import { STATUS_LABELS, nextWorkspaceRoute, statusTone } from "@/lib/workflow";
import { EmptyState, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

const STATUSES: StoryStatus[] = [
  "ingested",
  "scripted",
  "approved",
  "media_ready",
  "queued",
  "publish_ready",
];

export default function KanbanBoard() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["stories"],
    queryFn: () => listStories({ limit: 200 }),
  });

  if (isLoading) {
    return (
      <Panel className="min-h-48">
        <p className="text-sm text-[var(--text-soft)]">Loading pipeline board…</p>
      </Panel>
    );
  }

  if (isError) {
    return (
      <Panel className="min-h-48">
        <p className="text-sm text-rose-200">The board could not load the latest story state.</p>
      </Panel>
    );
  }

  const stories = data ?? [];

  return (
    <div className="space-y-5" data-testid="kanban-board">
      <SectionHeading
        eyebrow="Pipeline view"
        title="Current stage pressure"
        description="Each column reflects a real workflow stage. Open any story directly at its next valid workspace step."
      />
      <div className="grid gap-4 xl:grid-cols-3 2xl:grid-cols-6">
        {STATUSES.map((status) => {
          const columnStories = stories.filter((story) => story.status === status);
          return (
            <Panel key={status} className="min-h-[18rem] space-y-4 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                    Stage
                  </p>
                  <h3 className="mt-1 text-lg font-semibold text-white">{STATUS_LABELS[status]}</h3>
                </div>
                <StatusBadge tone={statusTone(status)}>{columnStories.length}</StatusBadge>
              </div>

              {columnStories.length === 0 ? (
                <EmptyState
                  title={`Nothing in ${STATUS_LABELS[status].toLowerCase()}`}
                  description="When stories reach this stage, they will appear here with direct workspace links."
                />
              ) : (
                <div className="space-y-3">
                  {columnStories.map((story) => (
                    <Link
                      key={story.id}
                      to={nextWorkspaceRoute(story.status, story.id, Boolean(story.active_asset_bundle_id))}
                      className="block rounded-[1.25rem] border border-white/8 bg-white/[0.03] p-4 transition hover:-translate-y-0.5 hover:border-white/14 hover:bg-white/[0.05]"
                    >
                      <p className="text-sm font-semibold text-white">{story.title}</p>
                      <p className="mt-2 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                        #{story.id} · {story.author || "Unknown"}
                      </p>
                    </Link>
                  ))}
                </div>
              )}
            </Panel>
          );
        })}
      </div>
    </div>
  );
}
