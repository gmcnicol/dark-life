"use client";

import { useQuery } from "@tanstack/react-query";
import { listJobs, mapJobStatus, type Job } from "@/lib/jobs";
import { EmptyState, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

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

export default function JobTable({ storyId }: { storyId?: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["jobs", storyId],
    queryFn: () => listJobs(storyId ? { story_id: storyId } : {}),
    refetchInterval: 2000,
  });

  const jobs = data ?? [];

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
              className="grid gap-3 rounded-[1.4rem] border border-white/8 bg-white/[0.03] p-4 md:grid-cols-[6rem_1fr_1fr_auto]"
            >
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Job
                </p>
                <p className="mt-1 text-lg font-semibold text-white">{job.id}</p>
              </div>
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Kind
                </p>
                <p className="mt-1 text-sm text-white">{job.kind}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                  {job.variant}
                </p>
              </div>
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Artifact
                </p>
                <p className="mt-1 text-sm text-[var(--text-soft)]">
                  {typeof job.result?.artifact_path === "string" ? job.result.artifact_path : "Pending"}
                </p>
              </div>
              <div className="flex items-start justify-end">
                <StatusBadge tone={toneForJob(job.status)}>{mapJobStatus(job.status)}</StatusBadge>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
