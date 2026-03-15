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
        eyebrow="Release handoff"
        title="Publish queue"
        description="This is the last human checkpoint. Each item here has already cleared render and only needs platform metadata plus a manual publish confirmation."
      />
      <section className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Ready releases" value={releasesQuery.isLoading ? "…" : releases.length} detail="Items currently waiting on manual publish." />
        <MetricCard label="Primary platform" value={releasesQuery.isLoading ? "…" : releases.filter((item) => item.platform === "youtube").length} detail="YouTube-ready releases in the queue." />
        <MetricCard label="Short-form items" value={releasesQuery.isLoading ? "…" : releases.filter((item) => item.variant === "short").length} detail="Short releases staged for platform-specific posting." />
      </section>
      {releasesQuery.isLoading ? <LoadingState label="Loading release queue…" className="min-h-56" /> : <PublishQueue releases={releases} />}
    </div>
  );
}
