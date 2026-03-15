"use client";

import { useMemo, useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import type { Story, StoryPart } from "@/lib/stories";
import { replaceStoryParts } from "@/lib/stories";
import { canEditParts, STATUS_LABELS } from "@/lib/workflow";
import { ActionButton, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

export default function SplitEditor({
  story,
  parts,
}: {
  story: Story;
  parts: StoryPart[];
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [rows, setRows] = useState(() =>
    parts.length > 0 ? parts.map((part) => part.body_md) : [story.body_md || ""],
  );
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const canEdit = canEditParts(story.status, Boolean(story.active_script_version_id));

  const totalSeconds = useMemo(
    () =>
      rows.reduce((sum, row) => {
        const words = row.split(/\s+/).filter(Boolean).length;
        return sum + Math.max(1, Math.round(words / 2.6));
      }, 0),
    [rows],
  );

  const updateRow = (index: number, value: string) => {
    setRows((current) => current.map((row, i) => (i === index ? value : row)));
  };

  const addPart = () => setRows((current) => [...current, ""]);
  const removePart = (index: number) =>
    setRows((current) => current.filter((_, i) => i !== index));

  const handleSave = () => {
    startTransition(async () => {
      try {
        setError(null);
        await replaceStoryParts(
          story.id,
          rows
            .map((body_md) => body_md.trim())
            .filter(Boolean)
            .map((body_md) => ({ body_md, approved: true })),
        );
        await queryClient.invalidateQueries({ queryKey: ["story-overview", story.id] });
        await queryClient.invalidateQueries({ queryKey: ["story", story.id] });
        await queryClient.invalidateQueries({ queryKey: ["stories"] });
        navigate(`/story/${story.id}/review?saved=parts`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save parts");
      }
    });
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_19rem]">
      <div className="space-y-4">
        <Panel className="space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <SectionHeading
              eyebrow="Part timing"
              title="Split editor"
              description="Break the narration into clean sections before media assignment. Keep the pacing legible and the approximate runtime inside short-form bounds."
            />
            <div className="space-y-2 text-right">
              <span data-testid="status" className="inline-flex rounded-full border border-white/10 px-3 py-1.5 text-sm font-semibold text-white">
                Status: {story.status}
              </span>
              <div>
                <StatusBadge tone="neutral">{STATUS_LABELS[story.status]}</StatusBadge>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <ActionButton onClick={addPart} tone="secondary" disabled={!canEdit}>
              Add part
            </ActionButton>
            <ActionButton onClick={handleSave} disabled={isPending || !canEdit}>
              {isPending ? "Saving parts…" : "Save parts"}
            </ActionButton>
          </div>
          {error ? <StatusBadge tone="danger">{error}</StatusBadge> : null}
          {!canEdit ? (
            <p className="text-sm text-[var(--text-soft)]">
              Part editing stays available only after script generation and before downstream media work has started.
            </p>
          ) : null}
        </Panel>

        <div className="space-y-4">
          {rows.map((row, index) => {
            const seconds = Math.max(1, Math.round(row.split(/\s+/).filter(Boolean).length / 2.6));
            return (
              <Panel key={index} className="space-y-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                      Part {index + 1}
                    </p>
                    <p className="mt-1 text-sm text-[var(--text-soft)]">Approx. {seconds} seconds</p>
                  </div>
                  {rows.length > 1 ? (
                    <ActionButton onClick={() => removePart(index)} tone="ghost" disabled={!canEdit}>
                      Remove
                    </ActionButton>
                  ) : null}
                </div>
                <textarea
                  className="min-h-52 w-full rounded-[1.4rem] border border-white/10 bg-black/15 p-4 text-sm leading-7 text-white outline-none transition focus:border-cyan-300/35 focus:ring-2 focus:ring-cyan-300/20"
                  value={row}
                  disabled={!canEdit}
                  onChange={(event) => updateRow(index, event.target.value)}
                />
              </Panel>
            );
          })}
        </div>
      </div>

      <Panel className="h-fit space-y-4">
        <SectionHeading
          eyebrow="Runtime check"
          title="Split summary"
          description="Keep the part count and estimated runtime obvious while editing."
        />
        <div className="rounded-[1.4rem] border border-white/8 bg-white/[0.03] p-4">
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
            Parts
          </p>
          <p className="mt-2 font-display text-4xl text-white">{rows.length}</p>
        </div>
        <div className="rounded-[1.4rem] border border-white/8 bg-white/[0.03] p-4">
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
            Estimated total
          </p>
          <p className="mt-2 font-display text-4xl text-white">{totalSeconds}s</p>
        </div>
      </Panel>
    </div>
  );
}
