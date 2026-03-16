import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import PublishQueue from "@/components/publish-queue";
import { ActionButton, LoadingState, MetricCard, PageHeader } from "@/components/ui-surfaces";
import { listReleaseQueue } from "@/lib/stories";

function platformLabel(platform: string): string {
  if (platform === "youtube") {
    return "YouTube";
  }
  if (platform === "instagram") {
    return "Instagram";
  }
  if (platform === "tiktok") {
    return "TikTok";
  }
  return platform;
}

export default function PublishRoute() {
  const releasesQuery = useQuery({
    queryKey: ["release-queue"],
    queryFn: listReleaseQueue,
  });
  const [platformFilter, setPlatformFilter] = useState<string>("all");

  const releases = releasesQuery.data ?? [];
  const platforms = useMemo(
    () => Array.from(new Set(releases.map((release) => release.platform))).sort(),
    [releases],
  );
  const filteredReleases = useMemo(
    () =>
      platformFilter === "all"
        ? releases
        : releases.filter((release) => release.platform === platformFilter),
    [platformFilter, releases],
  );
  const metrics = useMemo(
    () => ({
      queueDepth: filteredReleases.length,
      awaitingReview: filteredReleases.filter(
        (item) => item.status === "ready" || item.status === "approved",
      ).length,
      manualHandoff: filteredReleases.filter((item) => item.status === "manual_handoff").length,
    }),
    [filteredReleases],
  );
  const selectedPlatformCount = platformFilter === "all" ? releases.length : filteredReleases.length;

  const platformActions = (
    <div className="flex flex-wrap items-center gap-2">
      <ActionButton
        tone={platformFilter === "all" ? "primary" : "secondary"}
        onClick={() => setPlatformFilter("all")}
      >
        All platforms
      </ActionButton>
      {platforms.map((platform) => (
        <ActionButton
          key={platform}
          tone={platformFilter === platform ? "primary" : "secondary"}
          onClick={() => setPlatformFilter(platform)}
        >
          {platformLabel(platform)}
        </ActionButton>
      ))}
    </div>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Publishing ops"
        title="Publish queue"
        description="Review rendered releases, approve or schedule automated delivery, and finish manual handoffs without leaving the operator surface."
        actions={platformActions}
        aside={
          <div className="space-y-2">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
              Target filter
            </p>
            <p className="text-lg font-semibold text-white">
              {platformFilter === "all" ? "All destinations" : platformLabel(platformFilter)}
            </p>
            <p className="text-sm leading-6 text-[var(--text-soft)]">
              {selectedPlatformCount} release{selectedPlatformCount === 1 ? "" : "s"} in the current platform view.
            </p>
          </div>
        }
      />
      <section className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Queue depth"
          value={releasesQuery.isLoading ? "…" : metrics.queueDepth}
          detail="Releases currently active in review, schedule, publish, or manual handoff lanes for the selected destination."
        />
        <MetricCard
          label="Awaiting review"
          value={releasesQuery.isLoading ? "…" : metrics.awaitingReview}
          detail="Items in this platform view waiting on immediate upload or a schedule."
        />
        <MetricCard
          label="Manual handoff"
          value={releasesQuery.isLoading ? "…" : metrics.manualHandoff}
          detail="Supervised posts in this platform view that still need a destination id."
        />
      </section>
      {releasesQuery.isLoading ? (
        <LoadingState label="Loading release queue…" className="min-h-56" />
      ) : (
        <PublishQueue releases={filteredReleases} />
      )}
    </div>
  );
}
