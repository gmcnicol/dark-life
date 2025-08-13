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
    <table data-testid="job-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Kind</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {jobs.map((job: Job) => (
          <tr key={job.id} data-testid="job-row">
            <td>{job.id}</td>
            <td>{job.kind}</td>
            <td>{mapJobStatus(job.status)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
