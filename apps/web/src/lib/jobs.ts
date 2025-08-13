import { z } from "zod";
import { apiFetch } from "./api";

export const JobSchema = z.object({
  id: z.number(),
  story_id: z.number().nullable(),
  kind: z.string(),
  status: z.string(),
});
export type Job = z.infer<typeof JobSchema>;

const JobListSchema = z.object({ jobs: z.array(JobSchema) });

export async function enqueueStory(
  id: number,
  preset: string,
  captions: boolean,
): Promise<Job[]> {
  const data = await apiFetch<unknown>(`/admin/stories/${id}/enqueue`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preset, captions }),
  });
  return JobListSchema.parse(data).jobs;
}

export async function listJobs(params: { story_id?: number } = {}): Promise<Job[]> {
  const search = new URLSearchParams();
  if (params.story_id) {
    search.set("story_id", String(params.story_id));
  }
  const qs = search.toString();
  const data = await apiFetch<unknown>(`/admin/jobs${qs ? `?${qs}` : ""}`);
  return z.array(JobSchema).parse(data);
}

const statusMap: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  done: "Done",
  error: "Error",
};

export function mapJobStatus(status: string): string {
  return statusMap[status] ?? "Unknown";
}
