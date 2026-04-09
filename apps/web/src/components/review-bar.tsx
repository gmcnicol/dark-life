"use client";

import { useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { StoryStatus } from "@dark-life/shared-types";
import { Link, useNavigate } from "react-router-dom";
import type { ScriptVersion, Story } from "@/lib/stories";
import { generateScript, listStories, updateStoryStatus } from "@/lib/stories";
import {
  canApproveStory,
  canGenerateScript,
  canRejectStory,
  findNextStoryWithStatus,
  STATUS_LABELS,
  statusTone,
} from "@/lib/workflow";
import { ActionButton, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

export default function ReviewBar({
  story,
  activeScript,
  scriptGenerationPending = false,
  compact = false,
}: {
  story: Story;
  activeScript: ScriptVersion | null;
  scriptGenerationPending?: boolean;
  compact?: boolean;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const canApproveScript = canApproveStory(story.status, Boolean(activeScript));
  const needsSourceApproval = !activeScript && canGenerateScript(story.status) && !scriptGenerationPending;
  const canGenerate = canGenerateScript(story.status) && !scriptGenerationPending;
  const canReject = canRejectStory(story.status);

  const run = (action: () => Promise<unknown>, successMessage?: string) => {
    startTransition(async () => {
      try {
        setError(null);
        setSuccess(null);
        await action();
        await queryClient.invalidateQueries();
        if (successMessage) {
          setSuccess(successMessage);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Action failed";
        if (message.includes("409")) {
          setError("Generate the script first, then approve the story.");
          return;
        }
        setError(message);
      }
    });
  };

  const changeStatus = (status: StoryStatus) => {
    run(() => updateStoryStatus(story.id, status), `Story moved to ${STATUS_LABELS[status].toLowerCase()}.`);
  };

  const rejectAndAdvance = () => {
    run(async () => {
      await updateStoryStatus(story.id, "rejected");
      const stories = await queryClient.fetchQuery({
        queryKey: ["stories", "review-next"],
        queryFn: () => listStories({ limit: 200 }),
      });
      const nextStoryId = findNextStoryWithStatus(stories, story.id, "ingested");
      navigate(nextStoryId ? `/story/${nextStoryId}/review` : "/inbox?status=ingested");
    });
  };

  const approveStoryAndAdvance = () => {
    run(async () => {
      await generateScript(story.id);
      const stories = await queryClient.fetchQuery({
        queryKey: ["stories", "review-next"],
        queryFn: () => listStories({ limit: 200 }),
      });
      const nextStoryId = findNextStoryWithStatus(stories, story.id, "ingested");
      navigate(nextStoryId ? `/story/${nextStoryId}/review` : "/inbox?status=ingested");
    }, "Story queued for script generation.");
  };

  return (
    <Panel className={compact ? "space-y-4 p-4" : "space-y-5"}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <SectionHeading
          eyebrow={compact ? "Decide" : "Decision point"}
          title={compact ? "Review actions" : "Review bar"}
          description={
            compact
              ? "Read the source, then generate, approve, or reject from here."
              : "This is the only place where review should mutate story state. Primary action first, destructive action explicit, and downstream navigation intentional."
          }
        />
        <div className={compact ? "space-y-2" : "space-y-2 text-right"}>
          <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
          <span
            data-testid="status"
            className="block text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-[var(--muted)]"
          >
            Current status: {STATUS_LABELS[story.status]}
          </span>
        </div>
      </div>

      <div className={compact ? "flex flex-col gap-3" : "flex flex-wrap items-center gap-3"}>
        {needsSourceApproval || scriptGenerationPending ? (
          <ActionButton
            onClick={approveStoryAndAdvance}
            disabled={isPending || !canGenerate}
            className={compact ? "w-full" : undefined}
          >
            {scriptGenerationPending ? "Generating script…" : "Approve story"}
          </ActionButton>
        ) : (
          <ActionButton
            onClick={() => changeStatus("approved")}
            disabled={isPending || !canApproveScript}
            className={compact ? "w-full" : undefined}
          >
            Approve script
          </ActionButton>
        )}
        <ActionButton
          onClick={rejectAndAdvance}
          tone="danger"
          disabled={isPending || !canReject}
          className={compact ? "w-full" : undefined}
        >
          Reject and next
        </ActionButton>
      </div>

      {compact ? (
        <div className="rounded-[1.2rem] border border-white/8 bg-black/15 p-4">
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">
            Next step
          </p>
          {activeScript ? (
            <div className="mt-3 space-y-3">
              <p className="text-sm leading-6 text-[var(--text-soft)]">
                If the generated draft is good, move forward into script. Use alternatives only when the draft quality is weak and you need another pass.
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                <Link
                  to={`/story/${story.id}/split`}
                  className="rounded-[1rem] border border-white/8 bg-white/[0.03] px-4 py-3 transition hover:border-white/14 hover:bg-white/[0.05]"
                >
                  <p className="text-sm font-semibold text-white">Open script</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Review blocks</p>
                </Link>
                <Link
                  to={`/story/${story.id}/refinement`}
                  className="rounded-[1rem] border border-white/8 bg-white/[0.03] px-4 py-3 transition hover:border-white/14 hover:bg-white/[0.05]"
                >
                  <p className="text-sm font-semibold text-white">Open lab</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Compare variants</p>
                </Link>
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm leading-6 text-[var(--text-soft)]">
              Generate the narration draft first. Script, media, and scheduling stay downstream from that gate.
            </p>
          )}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-5">
          <Link
            to={`/story/${story.id}/split`}
            className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-4 transition hover:border-white/14 hover:bg-white/[0.05]"
          >
            <p className="text-sm font-semibold text-white">Open script</p>
            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Primary blocks</p>
          </Link>
          <Link
            to={`/story/${story.id}/refinement`}
            className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-4 transition hover:border-white/14 hover:bg-white/[0.05]"
          >
            <p className="text-sm font-semibold text-white">Open refinement lab</p>
            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Variants and scoring</p>
          </Link>
          <Link
            to={`/story/${story.id}/media`}
            className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-4 transition hover:border-white/14 hover:bg-white/[0.05]"
          >
            <p className="text-sm font-semibold text-white">Choose media</p>
            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Asset bundle</p>
          </Link>
          <Link
            to={`/story/${story.id}/queue`}
            className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-4 transition hover:border-white/14 hover:bg-white/[0.05]"
          >
            <p className="text-sm font-semibold text-white">Queue renders</p>
            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Preset and platforms</p>
          </Link>
          <Link
            to={`/story/${story.id}/jobs`}
            className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-4 transition hover:border-white/14 hover:bg-white/[0.05]"
          >
            <p className="text-sm font-semibold text-white">Track jobs</p>
            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Queue telemetry</p>
          </Link>
        </div>
      )}

      {success ? <StatusBadge tone="success">{success}</StatusBadge> : null}
      {error ? <StatusBadge tone="danger">{error}</StatusBadge> : null}
      {scriptGenerationPending ? (
        <p className="text-sm text-[var(--text-soft)]">
          Script generation is running in the background. Stay on this page or move on; the draft will appear when the worker finishes.
        </p>
      ) : null}
      {!canGenerateScript(story.status) ? (
        <p className="text-sm text-[var(--text-soft)]">
          Script generation is disabled because this story has already moved beyond the editable review stages.
        </p>
      ) : null}
      {needsSourceApproval ? (
        <p className="text-sm text-[var(--text-soft)]">
          Approving this story queues script generation and moves you straight to the next ingested story.
        </p>
      ) : null}
      {!canApproveScript && activeScript && story.status !== "approved" ? (
        <p className="text-sm text-[var(--text-soft)]">
          Script approval unlocks after generation completes and the story is still in a reviewable state.
        </p>
      ) : null}
      {story.status === "approved" ? (
        <p className="text-sm text-[var(--text-soft)]">
          Script approved. Move into script and downstream production.
        </p>
      ) : null}
    </Panel>
  );
}
