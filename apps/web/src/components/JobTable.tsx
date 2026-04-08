"use client";

import { useTransition } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { canRequeueJob, isStaleJob, listJobs, mapJobKind, mapJobStatus, requeueJob, type Job } from "@/lib/jobs";
import { ActionButton, EmptyState, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

function toneForJob(status: Job["status"]): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "rendered" || status === "published" || status === "publish_ready") {
    return "success";
  }
  if (status === "rendering" || status === "claimed") {
    return "accent";
  }
  if (status === "errored") {
    return "danger";
  }
  return "warning";
}

function formatTimestamp(value?: string | null): string {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }
  return date.toLocaleString();
}

export default function JobTable({ storyId }: { storyId?: number }) {
  const queryClient = useQueryClient();
  const [isPending, startTransition] = useTransition();
  const { data, isLoading } = useQuery({
    queryKey: ["jobs", storyId],
    queryFn: () => listJobs(storyId ? { story_id: storyId } : {}),
    refetchInterval: 2000,
  });

  const jobs = data ?? [];

  const handleRequeue = (job: Job) => {
    startTransition(async () => {
      await requeueJob(job.id);
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    });
  };

  return (
    <Panel className="space-y-5">
      <SectionHeading
        eyebrow="Worker telemetry"
        title={storyId ? `Jobs for story #${storyId}` : "All render jobs"}
        description="Watch queue state, active work, and artifact output without leaving the operator surface."
      />

      {isLoading ? (
        <p className="text-sm text-[var(--text-soft)]">Loading jobs…</p>
      ) : jobs.length === 0 ? (
        <EmptyState
          title="No jobs yet"
          description="Queued renders and downstream publish jobs will appear here once the story enters the worker pipeline."
        />
      ) : (
        <div className="space-y-3">
          {jobs.map((job: Job) => (
            <div
              key={job.id}
              data-testid="job-row"
              className="grid gap-3 rounded-[1.4rem] border border-white/8 bg-white/[0.03] p-4 md:grid-cols-[6rem_1fr_1.2fr_auto]"
            >
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Job
                </p>
                <p className="mt-1 text-lg font-semibold text-white">{job.id}</p>
              </div>
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Task
                </p>
                <p className="mt-1 text-sm font-semibold text-white">{mapJobKind(job.kind)}</p>
                {describeJobTarget(job) ? (
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                    {describeJobTarget(job)}
                  </p>
                ) : null}
                <p className="mt-2 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                  Format {job.variant}
                </p>
              </div>
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Output
                </p>
                <p className="mt-1 text-sm text-[var(--text-soft)]">
                  {typeof job.result?.artifact_path === "string" ? job.result.artifact_path : "Pending"}
                </p>
                <p className="mt-2 text-xs text-[var(--muted)]">Updated {formatTimestamp(job.updated_at)}</p>
                {job.error_message ? (
                  <p className="mt-2 text-xs text-rose-100/80">{job.error_message}</p>
                ) : isStaleJob(job) ? (
                  <p className="mt-2 text-xs text-amber-100/80">Lease looks stale. Safe to requeue from here.</p>
                ) : null}
              </div>
              <div className="flex flex-col items-end gap-2">
                <StatusBadge tone={toneForJob(job.status)}>{mapJobStatus(job.status)}</StatusBadge>
                {canRequeueJob(job) ? (
                  <ActionButton
                    type="button"
                    tone={job.status === "errored" ? "danger" : "secondary"}
                    disabled={isPending}
                    onClick={() => handleRequeue(job)}
                  >
                    Requeue
                  </ActionButton>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function describeJobTarget(job: Job): string | null {
  if (job.kind === "render_part") {
    const partIndex = typeof job.payload?.part_index === "number" ? job.payload.part_index : null;
    return partIndex ? `Part ${partIndex} short` : "Short episode";
  }
  if (job.kind === "render_compilation") {
    return "Weekly/full-story cut";
  }
  if (job.story_part_id) {
    return `Part #${job.story_part_id}`;
  }
  if (job.compilation_id) {
    return `Compilation #${job.compilation_id}`;
  }
  return null;
}
