"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

interface Job {
  id: string;
  story_id: string;
  status: string;
  kind: string;
}

export default function JobsPage() {
  const { data } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => apiFetch<Job[]>("/jobs"),
  });

  if (!data) {
    return <p className="p-4">Loading...</p>;
  }

  return (
    <div className="p-4">
      <h1 className="text-xl mb-4">Jobs</h1>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            <th className="border p-2">Story</th>
            <th className="border p-2">Kind</th>
            <th className="border p-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {data.map((job) => (
            <tr key={job.id}>
              <td className="border p-2">
                <a href={`/stories/${job.story_id}`} className="underline">
                  {job.story_id}
                </a>
              </td>
              <td className="border p-2">{job.kind}</td>
              <td className="border p-2">{job.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
