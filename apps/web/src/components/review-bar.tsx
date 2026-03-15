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
  findNextReviewStoryId,
  STATUS_LABELS,
  statusTone,
} from "@/lib/workflow";
import { ActionButton, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

export default function ReviewBar({
  story,
  activeScript,
}: {
  story: Story;
  activeScript: ScriptVersion | null;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const canApprove = canApproveStory(story.status, Boolean(activeScript));
  const canGenerate = canGenerateScript(story.status);
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
      const nextStoryId = findNextReviewStoryId(stories, story.id);
      navigate(nextStoryId ? `/story/${nextStoryId}/review` : "/inbox");
    });
  };

  return (
    <Panel className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <SectionHeading
          eyebrow="Decision point"
          title="Review bar"
          description="This is the only place where review should mutate story state. Primary action first, destructive action explicit, and downstream navigation intentional."
        />
        <div className="space-y-2 text-right">
          <span
            data-testid="status"
            className="inline-flex rounded-full border border-white/10 px-3 py-1.5 text-sm font-semibold text-white"
          >
            Status: {story.status}
          </span>
          <div>
            <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <ActionButton
          onClick={() => run(() => generateScript(story.id), activeScript ? "Script regenerated." : "Script generated.")}
          disabled={isPending || !canGenerate}
        >
          {activeScript ? "Regenerate script" : "Generate script"}
        </ActionButton>
        <ActionButton onClick={() => changeStatus("approved")} tone="secondary" disabled={isPending || !canApprove}>
          Approve story
        </ActionButton>
        <ActionButton onClick={rejectAndAdvance} tone="danger" disabled={isPending || !canReject}>
          Reject and next
        </ActionButton>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <Link to={`/story/${story.id}/split`} className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-4 transition hover:border-white/14 hover:bg-white/[0.05]">
          <p className="text-sm font-semibold text-white">Edit parts</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Timing and sections</p>
        </Link>
        <Link to={`/story/${story.id}/media`} className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-4 transition hover:border-white/14 hover:bg-white/[0.05]">
          <p className="text-sm font-semibold text-white">Choose media</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Asset bundle</p>
        </Link>
        <Link to={`/story/${story.id}/queue`} className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-4 transition hover:border-white/14 hover:bg-white/[0.05]">
          <p className="text-sm font-semibold text-white">Queue renders</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Preset and platforms</p>
        </Link>
        <Link to={`/story/${story.id}/jobs`} className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] px-4 py-4 transition hover:border-white/14 hover:bg-white/[0.05]">
          <p className="text-sm font-semibold text-white">Track jobs</p>
          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">Queue telemetry</p>
        </Link>
      </div>

      {success ? <StatusBadge tone="success">{success}</StatusBadge> : null}
      {error ? <StatusBadge tone="danger">{error}</StatusBadge> : null}
      {!canGenerate ? (
        <p className="text-sm text-[var(--text-soft)]">
          Script generation is disabled because this story has already moved beyond the editable review stages.
        </p>
      ) : null}
      {!canApprove && !activeScript ? (
        <p className="text-sm text-[var(--text-soft)]">
          Approval stays locked until a narrator-ready script exists for the current story.
        </p>
      ) : null}
      {story.status === "approved" ? (
        <p className="text-sm text-[var(--text-soft)]">
          Story approved. Move into parts or media to continue downstream production.
        </p>
      ) : null}
    </Panel>
  );
}
