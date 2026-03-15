import type { JobStatus } from "@dark-life/shared-types";
import { listJobs, type Job } from "./stories";

export { listJobs };
export type { Job };

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
