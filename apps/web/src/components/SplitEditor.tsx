"use client";

import { useMemo, useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { BionicReadingToggle, BionicText } from "@/components/bionic-text";
import type { Story, StoryPart } from "@/lib/stories";
import { updateStoryStatus } from "@/lib/stories";
import { canRejectStory, canTransitionStory, STATUS_LABELS, statusTone } from "@/lib/workflow";
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
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const rows = parts.length > 0 ? parts.map((part) => part.body_md) : [story.body_md || ""];
  const canApproveForMedia =
    Boolean(story.active_script_version_id) &&
    (story.status === "approved" || canTransitionStory(story.status, "approved"));
  const canReject = canRejectStory(story.status);

  const totalSeconds = useMemo(
    () =>
      rows.reduce((sum, row) => {
        const words = row.split(/\s+/).filter(Boolean).length;
        return sum + Math.max(1, Math.round(words / 2.6));
      }, 0),
    [rows],
  );

  const handleApproveForMedia = () => {
    startTransition(async () => {
      try {
        setError(null);
        setSuccess(null);
        if (story.status !== "approved" && canTransitionStory(story.status, "approved")) {
          await updateStoryStatus(story.id, "approved");
          await queryClient.invalidateQueries({ queryKey: ["story-overview", story.id] });
          await queryClient.invalidateQueries({ queryKey: ["story", story.id] });
          await queryClient.invalidateQueries({ queryKey: ["stories"] });
        }
        setSuccess("Script approved. Moving to media.");
        navigate(`/story/${story.id}/media`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to approve script");
      }
    });
  };

  const handleReject = () => {
    startTransition(async () => {
      try {
        setError(null);
        setSuccess(null);
        await updateStoryStatus(story.id, "rejected");
        await queryClient.invalidateQueries({ queryKey: ["story-overview", story.id] });
        await queryClient.invalidateQueries({ queryKey: ["story", story.id] });
        await queryClient.invalidateQueries({ queryKey: ["stories"] });
        setSuccess("Story rejected.");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to reject story");
      }
    });
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_24rem]">
      <div className="space-y-4">
        <Panel className="space-y-5">
          <SectionHeading
            eyebrow="Primary draft"
            title="Script blocks"
            description="Review the live script in reading order. Keep the vertical stack aligned with alternatives so block order is obvious without re-scanning the screen."
          />

          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
            <StatusBadge tone="neutral">{rows.length} blocks</StatusBadge>
            <StatusBadge tone="neutral">{totalSeconds}s total</StatusBadge>
          </div>
        </Panel>

        <Panel className="space-y-5">
          {rows.map((row, index) => {
            const seconds = Math.max(1, Math.round(row.split(/\s+/).filter(Boolean).length / 2.6));
            return (
              <div key={index} className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] p-4">
                <div className="flex items-center justify-between gap-4 border-b border-white/8 pb-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cyan-300/20 bg-cyan-300/[0.1] text-sm font-semibold text-cyan-100">
                      {index + 1}
                    </div>
                    <div className="min-w-0">
                      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                        Script block
                      </p>
                      <p className="mt-1 text-sm font-semibold leading-6 text-white">Approx. {seconds} seconds</p>
                    </div>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">
                    Script block
                  </p>
                  <BionicText text={row} className="text-[1.08rem] leading-9 text-[var(--text-soft)]" />
                </div>
              </div>
            );
          })}
        </Panel>
      </div>

      <div className="space-y-4 lg:sticky lg:top-4 lg:self-start">
        <Panel className="space-y-4 p-4">
          <SectionHeading
            eyebrow="Action rail"
            title="Script decisions"
            description="Keep the primary action in the same place as review so you can scan, decide, and move on without hunting for controls."
          />
          <div className="flex flex-col gap-3">
            <ActionButton onClick={handleApproveForMedia} disabled={isPending || !canApproveForMedia}>
              {isPending ? "Approving…" : "Approve for media"}
            </ActionButton>
            <Link
              to={`/story/${story.id}/refinement`}
              className="inline-flex items-center justify-center rounded-[1rem] border border-white/8 bg-white/[0.03] px-4 py-2.5 text-sm font-semibold text-white transition hover:border-white/14 hover:bg-white/[0.05]"
            >
              Generate alternatives
            </Link>
            <ActionButton onClick={handleReject} tone="danger" disabled={isPending || !canReject}>
              Reject story
            </ActionButton>
          </div>
        </Panel>

        <Panel className="space-y-3 p-4">
          <BionicReadingToggle />
          {success ? <StatusBadge tone="success">{success}</StatusBadge> : null}
          {error ? <StatusBadge tone="danger">{error}</StatusBadge> : null}
          {!canApproveForMedia ? (
            <p className="text-sm text-[var(--text-soft)]">
              This script cannot move to media until it has an active draft and is still in a reviewable stage.
            </p>
          ) : null}
        </Panel>
      </div>
    </div>
  );
}
