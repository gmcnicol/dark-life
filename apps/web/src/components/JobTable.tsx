"use client";

import { useQuery } from "@tanstack/react-query";
import { listJobs, mapJobStatus, type Job } from "@/lib/jobs";

export default function JobTable({ storyId }: { storyId?: number }) {
  const { data } = useQuery({
    queryKey: ["jobs", storyId],
    queryFn: () => listJobs(storyId ? { story_id: storyId } : {}),
    refetchInterval: 2000,
  });

  const jobs = data ?? [];
  return (
    <div className="overflow-hidden rounded-3xl border border-zinc-800 bg-zinc-950/70">
      <table data-testid="job-table" className="w-full text-left text-sm">
        <thead className="bg-zinc-900/70 text-zinc-400">
          <tr>
            <th className="px-4 py-3">ID</th>
            <th className="px-4 py-3">Kind</th>
            <th className="px-4 py-3">Variant</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Artifact</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job: Job) => (
            <tr key={job.id} data-testid="job-row" className="border-t border-zinc-900">
              <td className="px-4 py-3">{job.id}</td>
              <td className="px-4 py-3">{job.kind}</td>
              <td className="px-4 py-3">{job.variant}</td>
              <td className="px-4 py-3">{mapJobStatus(job.status)}</td>
              <td className="px-4 py-3 text-xs text-zinc-400">
                {typeof job.result?.artifact_path === "string" ? job.result.artifact_path : "Pending"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
