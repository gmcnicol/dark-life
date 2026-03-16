import { useQuery } from "@tanstack/react-query";
import PublishQueue from "@/components/publish-queue";
import { LoadingState, MetricCard, PageHeader } from "@/components/ui-surfaces";
import { listReleaseQueue } from "@/lib/stories";

export default function PublishRoute() {
  const releasesQuery = useQuery({
    queryKey: ["release-queue"],
    queryFn: listReleaseQueue,
  });

  const releases = releasesQuery.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Publishing ops"
        title="Publish queue"
        description="Review rendered releases, approve or schedule automated delivery, and finish manual handoffs without leaving the operator surface."
      />
      <section className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Queue depth" value={releasesQuery.isLoading ? "…" : releases.length} detail="Releases currently active in review, schedule, publish, or manual handoff lanes." />
        <MetricCard label="Awaiting review" value={releasesQuery.isLoading ? "…" : releases.filter((item) => item.status === "ready").length} detail="Items waiting on approval or a schedule." />
        <MetricCard label="Manual handoff" value={releasesQuery.isLoading ? "…" : releases.filter((item) => item.status === "manual_handoff").length} detail="Supervised posts that still need a destination id." />
      </section>
      {releasesQuery.isLoading ? <LoadingState label="Loading release queue…" className="min-h-56" /> : <PublishQueue releases={releases} />}
    </div>
  );
}
