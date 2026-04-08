import type { JobStatus } from "@dark-life/shared-types";
import { adminFetch } from "./api";
import { listJobs, type Job } from "./stories";

export { listJobs };
export type { Job };

export const STALE_JOB_MS = 10 * 60 * 1000;

const statusMap: Record<JobStatus, string> = {
  queued: "Queued",
  claimed: "Claimed",
  rendering: "Rendering",
  rendered: "Rendered",
  publish_ready: "Publish Ready",
  published: "Published",
  errored: "Errored",
};

export function mapJobStatus(status: JobStatus): string {
  return statusMap[status] ?? status;
}

export function mapJobKind(kind: string): string {
  const kindMap: Record<string, string> = {
    render_part: "Render story part",
    render_compilation: "Render full compilation",
    reddit_backfill: "Backfill subreddit stories",
    refine_extract_concept: "Extract story concept",
    refine_generate_batch: "Generate script alternatives",
    refine_run_critic: "Score script alternatives",
    refine_collect_metrics: "Collect performance metrics",
    refine_analyze_batch: "Analyze batch performance",
  };

  return kindMap[kind] ?? humanizeKind(kind);
}

function humanizeKind(kind: string): string {
  return kind
    .split("_")
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

export function isStaleJob(job: Pick<Job, "status" | "updated_at">, now = Date.now()): boolean {
  if (!["claimed", "rendering"].includes(job.status) || !job.updated_at) {
    return false;
  }
  const updatedAt = Date.parse(job.updated_at);
  if (Number.isNaN(updatedAt)) {
    return false;
  }
  return now - updatedAt >= STALE_JOB_MS;
}

export function canRequeueJob(job: Pick<Job, "status" | "updated_at">, now = Date.now()): boolean {
  return job.status === "errored" || isStaleJob(job, now);
}

export async function requeueJob(jobId: number): Promise<Job> {
  return adminFetch<Job>(`/api/admin/render-jobs/${jobId}/requeue`, {
    method: "POST",
  });
}
