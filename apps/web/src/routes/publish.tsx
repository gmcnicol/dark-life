import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import PublishQueue from "@/components/publish-queue";
import { ActionButton, LoadingState, PageHeader, PageStatusBar, StatusBadge } from "@/components/ui-surfaces";
import { getInsightsSummary, listReleaseQueue, rescheduleReleaseQueue } from "@/lib/stories";
import { formatLocalDateTime, isSameLocalDay } from "@/lib/utils";

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
  return formatLocalDateTime(updatedAt, "Awaiting sync");
}

export default function PublishRoute() {
  const queryClient = useQueryClient();
  const releasesQuery = useQuery({
    queryKey: ["release-queue"],
    queryFn: listReleaseQueue,
  });
  const insightsSummaryQuery = useQuery({
    queryKey: ["insights-summary"],
    queryFn: () => getInsightsSummary(30),
  });
  const [platformFilter, setPlatformFilter] = useState<string>("all");
  const rescheduleMutation = useMutation({
    mutationFn: rescheduleReleaseQueue,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["release-queue"] });
    },
  });

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
      scheduledToday: filteredReleases.filter((item) => isSameLocalDay(item.publish_at, now)).length,
      winners: filteredReleases.filter((item) => item.early_signal?.state === "winner").length,
      flats: filteredReleases.filter((item) => item.early_signal?.state === "flat").length,
    }),
    [filteredReleases, now],
  );
  const selectedPlatformCount = platformFilter === "all" ? releases.length : filteredReleases.length;

  const platformActions = (
    <div className="flex flex-wrap items-center gap-2">
      <ActionButton
        tone="secondary"
        onClick={() => rescheduleMutation.mutate()}
        disabled={rescheduleMutation.isPending}
      >
        {rescheduleMutation.isPending ? "Rescheduling…" : "Reschedule to cadence"}
      </ActionButton>
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
          <div className="space-y-3">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
              Target filter
            </p>
            <p className="text-lg font-semibold text-white">
              {platformFilter === "all" ? "All destinations" : platformLabel(platformFilter)}
            </p>
            <p className="text-sm leading-6 text-[var(--text-soft)]">
              {selectedPlatformCount} release{selectedPlatformCount === 1 ? "" : "s"} in the current platform view.
            </p>
            <div className="flex flex-wrap gap-2">
              <StatusBadge tone="success">{insightsSummaryQuery.data?.winners ?? 0} winners</StatusBadge>
              <StatusBadge tone="warning">{insightsSummaryQuery.data?.monitor ?? 0} monitor</StatusBadge>
              <StatusBadge tone="danger">{insightsSummaryQuery.data?.flat ?? 0} flat</StatusBadge>
            </div>
            <Link to="/insights" className="inline-flex text-sm font-semibold text-cyan-100 transition hover:text-white">
              Open insights →
            </Link>
          </div>
        }
      />
      <PageStatusBar
        description={
          <>
            Run the queue as a grid: scan by status first, then open one selected release at a time for edits and
            actions. Use `Reschedule to cadence` to snap the current short queue onto the active daily slots.
          </>
        }
      >
        <StatusBadge tone="neutral">Updated {telemetryTimestampLabel(releasesQuery.dataUpdatedAt)}</StatusBadge>
        <StatusBadge tone="accent">{metrics.scheduledToday} scheduled today</StatusBadge>
        <StatusBadge tone="warning">{metrics.awaitingReview} ready to approve</StatusBadge>
        <StatusBadge tone="success">{metrics.winners} winners</StatusBadge>
        <StatusBadge tone="danger">{metrics.flats} flat</StatusBadge>
        <StatusBadge tone="warning">{metrics.manualHandoff} manual handoff</StatusBadge>
        {rescheduleMutation.isSuccess ? (
          <StatusBadge tone="success">
            {rescheduleMutation.data.total_rescheduled} rescheduled
          </StatusBadge>
        ) : null}
        {rescheduleMutation.isError ? (
          <StatusBadge tone="danger">
            {rescheduleMutation.error instanceof Error ? rescheduleMutation.error.message : "Reschedule failed"}
          </StatusBadge>
        ) : null}
      </PageStatusBar>
      {releasesQuery.isLoading ? (
        <LoadingState label="Loading release queue…" className="min-h-56" />
      ) : (
        <PublishQueue releases={filteredReleases} />
      )}
    </div>
  );
}
