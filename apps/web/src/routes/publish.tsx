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

function telemetryTimestampLabel(updatedAt: number): string {
  if (!updatedAt) {
    return "Awaiting sync";
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(updatedAt);
}

export default function PublishRoute() {
  const releasesQuery = useQuery({
    queryKey: ["release-queue"],
    queryFn: listReleaseQueue,
  });
  const [platformFilter, setPlatformFilter] = useState<string>("all");

  const releases = releasesQuery.data ?? [];
  const now = new Date();
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
      scheduledToday: filteredReleases.filter((item) => {
        if (!item.publish_at) {
          return false;
        }
        const date = new Date(item.publish_at);
        return (
          date.getUTCFullYear() === now.getUTCFullYear() &&
          date.getUTCMonth() === now.getUTCMonth() &&
          date.getUTCDate() === now.getUTCDate()
        );
      }).length,
      winners: filteredReleases.filter((item) => item.early_signal?.state === "winner").length,
      flats: filteredReleases.filter((item) => item.early_signal?.state === "flat").length,
    }),
    [filteredReleases, now],
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
        description="Operate a fixed daily shorts cadence, then use the first 4 hours to decide what to ignore and what to turn into a follow-up."
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
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          label="Scheduled today"
          value={releasesQuery.isLoading ? "…" : metrics.scheduledToday}
          detail="Shorts already placed into today’s fixed publish slots."
          timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)}
        />
        <MetricCard
          label="Ready to approve"
          value={releasesQuery.isLoading ? "…" : metrics.awaitingReview}
          detail="Rendered releases waiting for immediate upload or a future slot."
          timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)}
        />
        <MetricCard
          label="Early winners"
          value={releasesQuery.isLoading ? "…" : metrics.winners}
          detail="Recent posts worth extending into a rewrite, angle, or series."
          timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)}
        />
        <MetricCard
          label="Flat posts"
          value={releasesQuery.isLoading ? "…" : metrics.flats}
          detail="Recent posts to discard mentally instead of micro-tweaking."
          timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)}
        />
        <MetricCard
          label="Manual handoff"
          value={releasesQuery.isLoading ? "…" : metrics.manualHandoff}
          detail="Supervised posts in this platform view that still need a destination id."
          timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)}
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
