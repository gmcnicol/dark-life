import { useQuery } from "@tanstack/react-query";
import JobTable from "@/components/JobTable";
import { listJobs } from "@/lib/jobs";
import { LoadingState, PageHeader, PageStatusBar, StatusBadge } from "@/components/ui-surfaces";

export default function JobsRoute() {
  const jobsQuery = useQuery({
    queryKey: ["jobs", "overview"],
    queryFn: () => listJobs(),
    refetchInterval: 2000,
  });
  const jobs = jobsQuery.data ?? [];
  const active = jobs.filter((job) => ["rendering", "claimed"].includes(job.status)).length;
  const errored = jobs.filter((job) => job.status === "errored").length;

  if (jobsQuery.isLoading) {
    return <LoadingState label="Loading render queue…" className="min-h-56" />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Render telemetry"
        title="Jobs"
        description="Watch the worker queue, requeue stale or errored jobs, and keep output visibility in the same operator pattern used elsewhere."
        aside={
          <div className="space-y-3">
            <div className="rounded-[1.1rem] border border-white/8 bg-white/[0.04] px-4 py-3">
              <p className="text-sm text-[var(--text-soft)]">Visible jobs</p>
              <p className="mt-2 font-display text-3xl text-white">{jobs.length}</p>
            </div>
          </div>
        }
      />

      <PageStatusBar>
        <StatusBadge tone="accent">{active} active</StatusBadge>
        <StatusBadge tone="danger">{errored} errored</StatusBadge>
        <StatusBadge tone="neutral">{jobs.length - active - errored} idle or complete</StatusBadge>
      </PageStatusBar>

      <JobTable />
    </div>
  );
}
