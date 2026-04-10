"use client";

import { useMemo, useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { BionicText } from "@/components/bionic-text";
import { useReaderPreferences } from "@/lib/reader-preferences";
import type { Story, StoryPart } from "@/lib/stories";
import { listStories, updateStoryStatus } from "@/lib/stories";
import { canRejectStory, canTransitionStory, findNextStoryWithStatus, STATUS_LABELS, statusTone } from "@/lib/workflow";
import {
  ActionButton,
  HintPanel,
  PageActions,
  PageStatusBar,
  Panel,
  ReaderControls,
  SectionHeading,
  StatusBadge,
  SurfaceRail,
  readerStyleVars,
} from "./ui-surfaces";

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
  const { size, setSize, preset } = useReaderPreferences();
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
        const stories = await queryClient.fetchQuery({
          queryKey: ["stories", "script-next"],
          queryFn: () => listStories({ limit: 200 }),
        });
        const nextStoryId = findNextStoryWithStatus(stories, story.id, "scripted");
        setSuccess("Script approved and queued for media.");
        navigate(nextStoryId ? `/story/${nextStoryId}/split` : "/inbox?status=scripted");
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
        const stories = await queryClient.fetchQuery({
          queryKey: ["stories", "script-next"],
          queryFn: () => listStories({ limit: 200 }),
        });
        const nextStoryId = findNextStoryWithStatus(stories, story.id, "scripted");
        setSuccess("Story rejected.");
        navigate(nextStoryId ? `/story/${nextStoryId}/split` : "/inbox?status=scripted");
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
          <div className="rounded-[1.2rem] border border-white/8 bg-black/15 p-4">
            <ReaderControls size={size} onSizeChange={setSize} compact />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
            <StatusBadge tone="neutral">{rows.length} blocks</StatusBadge>
            <StatusBadge tone="neutral">{totalSeconds}s total</StatusBadge>
          </div>
        </Panel>

        <PageStatusBar>
          {success ? <StatusBadge tone="success">{success}</StatusBadge> : null}
          {error ? <StatusBadge tone="danger">{error}</StatusBadge> : null}
          {!canApproveForMedia ? (
            <StatusBadge tone="warning">Needs active draft and reviewable status</StatusBadge>
          ) : (
            <StatusBadge tone="accent">Ready for media handoff</StatusBadge>
          )}
        </PageStatusBar>

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
                  <div style={readerStyleVars(preset.fontSize, preset.lineHeight)}>
                    <BionicText text={row} className="reader-copy text-[var(--text-soft)]" />
                  </div>
                </div>
              </div>
            );
          })}
        </Panel>
      </div>

      <SurfaceRail>
        <HintPanel
          eyebrow="Primary action"
          title="Script decisions"
          description="Approve from the same rail used across the workspace. Secondary routes stay below the forward action so the next move is always obvious."
        >
          <PageActions>
            <ActionButton onClick={handleApproveForMedia} disabled={isPending || !canApproveForMedia}>
              {isPending ? "Approving…" : "Approve for media"}
            </ActionButton>
            <Link
              to={`/story/${story.id}/refinement`}
              className="inline-flex items-center justify-center rounded-[1rem] border border-white/8 bg-white/[0.03] px-4 py-2.5 text-sm font-semibold text-white transition hover:border-white/14 hover:bg-white/[0.05]"
            >
              Open alternatives
            </Link>
            <ActionButton onClick={handleReject} tone="danger" disabled={isPending || !canReject}>
              Reject story
            </ActionButton>
          </PageActions>
        </HintPanel>

        <HintPanel
          eyebrow="What happens next"
          title="Workflow hint"
          description="Keep the main column for reading. Use the rail for what to do next and why something may be unavailable."
        >
          {!canApproveForMedia ? (
            <p className="text-sm text-[var(--text-soft)]">
              This script cannot move to media until it has an active draft and is still in a reviewable stage.
            </p>
          ) : (
            <p className="text-sm text-[var(--text-soft)]">
              Once approved, this story moves cleanly into media selection and the next scripted story becomes the active workspace.
            </p>
          )}
        </HintPanel>
      </SurfaceRail>
    </div>
  );
}
