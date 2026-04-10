import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { enqueueRedditIncremental, getInsightsSummary, getPublishPlatformSettings, listReleaseQueue, listStories } from "@/lib/stories";
import { buildQueueRunwaySummary } from "@/lib/publish-planning";
import { STATUS_LABELS, nextWorkspaceRoute, statusTone } from "@/lib/workflow";
import {
  ActionButton,
  EmptyState,
  PageHeader,
  PageStatusBar,
  Panel,
  SectionHeading,
  StatusBadge,
  LoadingState,
} from "@/components/ui-surfaces";

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

function isSameUtcDay(value: string | null | undefined, now: Date): boolean {
  if (!value) {
    return false;
  }
  const date = new Date(value);
  return (
    date.getUTCFullYear() === now.getUTCFullYear() &&
    date.getUTCMonth() === now.getUTCMonth() &&
    date.getUTCDate() === now.getUTCDate()
  );
}

export default function DashboardRoute() {
  const queryClient = useQueryClient();
  const [subredditInput, setSubredditInput] = useState("");
  const storiesQuery = useQuery({ queryKey: ["stories"], queryFn: () => listStories({ limit: 100 }) });
  const releasesQuery = useQuery({ queryKey: ["release-queue"], queryFn: listReleaseQueue });
  const insightsSummaryQuery = useQuery({
    queryKey: ["insights-summary"],
    queryFn: () => getInsightsSummary(30),
  });
  const publishSettingsQuery = useQuery({
    queryKey: ["publish-platform-settings"],
    queryFn: getPublishPlatformSettings,
  });
  const ingestMutation = useMutation({
    mutationFn: async () => {
      const subreddits = subredditInput
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
      return enqueueRedditIncremental(subreddits.length ? { subreddits } : {});
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["stories"] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const stories = storiesQuery.data ?? [];
  const releaseQueue = releasesQuery.data ?? [];
  const now = new Date();

  const activeStories = stories
    .filter((story) => !["published", "rejected"].includes(story.status))
    .sort((a, b) => a.id - b.id);

  const insightsSummary = insightsSummaryQuery.data;
  const scheduledToday = releaseQueue.filter((release) => isSameUtcDay(release.publish_at, now)).length;
  const winners = insightsSummary?.winners ?? 0;
  const flats = insightsSummary?.flat ?? 0;
  const pulseReleases = releaseQueue.filter((release) => Boolean(release.early_signal));
  const runway = buildQueueRunwaySummary(releaseQueue, stories, publishSettingsQuery.data);
  const configuredSlotsPerDay = publishSettingsQuery.data?.short_slots_utc?.length ?? 0;
  const cadenceKnown = configuredSlotsPerDay > 0;
  const displayedRunwayDays = cadenceKnown ? runway.queuedDays.toFixed(1) : "—";
  const topStories = activeStories.slice(0, 5);
  const queueDepth = releaseQueue.length;
  const readyToApprove = releaseQueue.filter((release) => release.status === "ready" || release.status === "approved").length;
  const awaitingMetrics = insightsSummary?.awaiting_metrics ?? 0;
  const staleSync = insightsSummary?.stale_sync ?? 0;
  const trackedReleases = insightsSummary?.tracked_releases ?? 0;
  const analyticsLinks = [
    {
      to: "/insights",
      label: "Tracked releases",
      value: insightsSummaryQuery.isLoading ? "…" : trackedReleases,
      detail: "30d window",
    },
    {
      to: "/insights",
      label: "Signal split",
      value: insightsSummaryQuery.isLoading ? "…" : `${winners}/${flats}`,
      detail: "win / flat",
    },
    {
      to: "/insights",
      label: "Awaiting metrics",
      value: insightsSummaryQuery.isLoading ? "…" : awaitingMetrics,
      detail: "insights lag",
    },
    {
      to: "/insights",
      label: "Stale sync",
      value: insightsSummaryQuery.isLoading ? "…" : staleSync,
      detail: "needs refresh",
    },
    {
      to: "/publish",
      label: "Scheduled today",
      value: releasesQuery.isLoading ? "…" : scheduledToday,
      detail: "publish queue",
    },
    {
      to: cadenceKnown ? "/publish" : "/settings",
      label: "Runway",
      value: `${displayedRunwayDays}${cadenceKnown ? "d" : ""}`,
      detail: cadenceKnown ? `${configuredSlotsPerDay}/day` : "set cadence",
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Studio control room"
        title="Overview"
        description="See queue pressure, publishing health, and the next stories to move without jumping between separate operator surfaces."
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <ActionButton onClick={() => ingestMutation.mutate()} disabled={ingestMutation.isPending}>
              {ingestMutation.isPending ? "Running ingest…" : "Run ingest"}
            </ActionButton>
          </div>
        }
        aside={
          <div className="space-y-3">
            <div className="rounded-[1.1rem] border border-white/8 bg-white/[0.04] px-4 py-3">
              <p className="text-sm text-[var(--text-soft)]">Active stories</p>
              <p className="mt-2 font-display text-3xl text-white">{activeStories.length}</p>
            </div>
            <div className="rounded-[1.1rem] border border-white/8 bg-white/[0.04] px-4 py-3">
              <p className="text-sm text-[var(--text-soft)]">Queue depth</p>
              <p className="mt-2 font-display text-3xl text-white">{queueDepth}</p>
            </div>
          </div>
        }
      />

      <PageStatusBar>
        <StatusBadge tone="accent">{scheduledToday} scheduled today</StatusBadge>
        <StatusBadge tone="success">{winners} winners</StatusBadge>
        <StatusBadge tone="warning">{awaitingMetrics} awaiting metrics</StatusBadge>
        {ingestMutation.isSuccess ? (
          <StatusBadge tone="success">
            {ingestMutation.data.total_inserted} ingested
          </StatusBadge>
        ) : null}
        {ingestMutation.isError ? (
          <StatusBadge tone="danger">
            {ingestMutation.error instanceof Error ? ingestMutation.error.message : "Ingest failed"}
          </StatusBadge>
        ) : null}
      </PageStatusBar>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        {analyticsLinks.map((card) => (
          <Link
            key={card.label}
            to={card.to}
            className="rounded-[1.3rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.03))] p-4 shadow-[0_20px_70px_rgba(0,0,0,0.16)] transition hover:-translate-y-0.5 hover:border-white/16 hover:bg-white/[0.06]"
          >
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
              {card.label}
            </p>
            <div className="mt-3 flex items-end justify-between gap-3">
              <p className="font-display text-4xl tracking-[-0.04em] text-white">{card.value}</p>
              <p className="text-[0.68rem] uppercase tracking-[0.16em] text-[var(--muted)]">{card.detail}</p>
            </div>
          </Link>
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Panel className="space-y-4 p-5">
          <SectionHeading eyebrow="Jump to" title="Operational routes" />
          <div className="grid gap-3">
            <div className="rounded-[1.25rem] border border-emerald-300/16 bg-emerald-300/[0.06] px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-base font-semibold text-white">Run retrieval</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-emerald-100/75">
                    reddit ingest
                  </p>
                </div>
                <ActionButton
                  onClick={() => ingestMutation.mutate()}
                  disabled={ingestMutation.isPending}
                  className="shrink-0"
                >
                  {ingestMutation.isPending ? "Running…" : "Run now"}
                </ActionButton>
              </div>
              {ingestMutation.isError ? (
                <p className="mt-3 text-sm text-rose-200">
                  {ingestMutation.error instanceof Error ? ingestMutation.error.message : "Unable to run retrieval."}
                </p>
              ) : null}
              {ingestMutation.isSuccess ? (
                <p className="mt-3 text-sm text-[var(--text-soft)]">
                  {ingestMutation.data.total_inserted} new stor{ingestMutation.data.total_inserted === 1 ? "y" : "ies"} inserted.
                </p>
              ) : null}
            </div>
            <Link
              to="/insights"
              className="rounded-[1.25rem] border border-cyan-300/18 bg-cyan-300/[0.07] px-4 py-4 transition hover:-translate-y-0.5 hover:border-cyan-300/28"
            >
              <div className="flex items-end justify-between gap-3">
                <div>
                  <p className="text-base font-semibold text-white">Insights</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-cyan-100/75">
                    winners {winners} · stale {staleSync}
                  </p>
                </div>
                <span className="text-sm font-semibold text-cyan-50">Open</span>
              </div>
            </Link>
            <Link
              to="/publish"
              className="rounded-[1.25rem] border border-white/10 bg-white/[0.03] px-4 py-4 transition hover:-translate-y-0.5 hover:border-white/16 hover:bg-white/[0.05]"
            >
              <div className="flex items-end justify-between gap-3">
                <div>
                  <p className="text-base font-semibold text-white">Publish queue</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
                    scheduled {scheduledToday} · ready {readyToApprove} · queue {queueDepth}
                  </p>
                </div>
                <span className="text-sm font-semibold text-white">Open</span>
              </div>
            </Link>
            <Link
              to="/inbox"
              className="rounded-[1.25rem] border border-white/10 bg-white/[0.03] px-4 py-4 transition hover:-translate-y-0.5 hover:border-white/16 hover:bg-white/[0.05]"
            >
              <div className="flex items-end justify-between gap-3">
                <div>
                  <p className="text-base font-semibold text-white">Stories</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
                    active {activeStories.length} · ready now {runway.reviewableStoriesNow}
                  </p>
                </div>
                <span className="text-sm font-semibold text-white">Open</span>
              </div>
            </Link>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="accent">{runway.queuedShorts} shorts queued</StatusBadge>
            {cadenceKnown ? <StatusBadge tone="neutral">{configuredSlotsPerDay} per day</StatusBadge> : null}
            {cadenceKnown ? <StatusBadge tone="warning">{runway.shortageShorts} short of target</StatusBadge> : null}
            {!cadenceKnown ? <StatusBadge tone="warning">Cadence not loaded</StatusBadge> : null}
          </div>
        </Panel>

        <Panel className="space-y-4 p-5">
          <SectionHeading eyebrow="Next stories" title="Active queue" action={<Link to="/inbox" className="text-sm font-semibold text-[var(--text-soft)] transition hover:text-white">Open inbox</Link>} />
          {topStories.length === 0 ? (
            <EmptyState
              title="No active stories in flight"
              description="Once new stories are ingested or queued, they land here."
            />
          ) : (
            <div className="space-y-3">
              {topStories.map((story) => (
                <Link
                  key={story.id}
                  to={nextWorkspaceRoute(story.status, story.id, Boolean(story.active_asset_bundle_id))}
                  className="block rounded-[1.25rem] border border-white/8 bg-white/[0.03] px-4 py-3 transition hover:-translate-y-0.5 hover:border-white/14 hover:bg-white/[0.05]"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate text-sm font-semibold text-white">{story.title}</h3>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                        #{story.id} · {story.author || "Unknown author"}
                      </p>
                    </div>
                    <StatusBadge tone={statusTone(story.status)} className="shrink-0">
                      {STATUS_LABELS[story.status]}
                    </StatusBadge>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Panel>
      </section>

      <Panel className="space-y-4">
        <SectionHeading
          eyebrow="Ingestion"
          title="Manual Reddit retrieval"
        />
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(16rem,0.7fr)]">
          <label className="space-y-2">
            <span className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
              Subreddit override
            </span>
            <textarea
              value={subredditInput}
              onChange={(event) => setSubredditInput(event.target.value)}
              rows={3}
              placeholder="Odd_directions, shortscarystories, nosleep"
              className="min-h-24 w-full rounded-[1.2rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
            />
            <p className="text-sm leading-6 text-[var(--text-soft)]">
              Blank uses the default order: Odd_directions, shortscarystories, nosleep, stayawake, Ruleshorror, libraryofshadows, JustNotRight, TheCrypticCompendium, SignalHorrorFiction, scarystories, SLEEPSPELL, TwoSentenceHorror.
            </p>
          </label>
          <div className="rounded-[1.25rem] border border-white/8 bg-white/[0.03] p-4">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
              Retrieval result
            </p>
            {ingestMutation.isSuccess ? (
              <div className="mt-3 space-y-3">
                <p className="text-sm text-white">
                  Inserted {ingestMutation.data.total_inserted} new stor{ingestMutation.data.total_inserted === 1 ? "y" : "ies"}.
                </p>
                <div className="space-y-2">
                  {ingestMutation.data.results.map((result) => (
                    <div key={result.subreddit} className="flex items-center justify-between gap-3 rounded-[1rem] border border-white/8 bg-black/20 px-3 py-2">
                      <StatusBadge tone="accent">r/{result.subreddit}</StatusBadge>
                      <span className="text-sm text-[var(--text-soft)]">{result.inserted} inserted</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-[var(--text-soft)]">
                This action runs through `/api/admin/reddit/incremental` on the web server proxy and executes the fetch immediately.
              </p>
            )}
            {ingestMutation.isError ? (
              <p className="mt-3 text-sm text-rose-200">
                {ingestMutation.error instanceof Error ? ingestMutation.error.message : "Unable to run retrieval."}
              </p>
            ) : null}
          </div>
        </div>
      </Panel>

      {(storiesQuery.isLoading || releasesQuery.isLoading || publishSettingsQuery.isLoading || insightsSummaryQuery.isLoading) ? (
        <LoadingState label="Loading dashboard queues…" className="min-h-64" />
      ) : (
      <section className="grid gap-4 xl:grid-cols-[1.3fr_0.9fr]">
        <Panel className="space-y-4">
          <SectionHeading
            eyebrow="Operator queue"
            title="Stories needing attention"
            description="Keep review and production moving while the publish side runs on a fixed daily cadence."
            action={
              <Link to="/inbox" className="text-sm font-semibold text-[var(--text-soft)] transition hover:text-white">
                See full inbox
              </Link>
            }
          />
          {activeStories.length === 0 ? (
            <EmptyState
              title="No active stories in flight"
              description="Once new stories are ingested or queued, the control room will surface them here with their next stage."
            />
          ) : (
            <div className="space-y-3">
              {activeStories.slice(0, 6).map((story) => (
                <Link
                  key={story.id}
                  to={nextWorkspaceRoute(story.status, story.id, Boolean(story.active_asset_bundle_id))}
                  className="block rounded-[1.4rem] border border-white/8 bg-white/[0.03] p-4 transition hover:-translate-y-0.5 hover:border-white/14 hover:bg-white/[0.05]"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-2">
                      <h3 className="text-lg font-semibold text-white">{story.title}</h3>
                      <p className="text-sm text-[var(--text-soft)]">
                        #{story.id} · {story.author || "Unknown author"}
                      </p>
                    </div>
                    <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Panel>

        <Panel className="space-y-4">
          <SectionHeading
            eyebrow="Early signal"
            title="Recent release pulse"
            description="Use the first 4 hours to decide what to ignore and what to expand into a follow-up."
            action={
              <Link to="/publish" className="text-sm font-semibold text-[var(--text-soft)] transition hover:text-white">
                Open queue
              </Link>
            }
          />
          {pulseReleases.length === 0 ? (
            <EmptyState
              title="No recent release signal yet"
              description="Once shorts are published or scheduled, this view will show the early winners and flats."
            />
          ) : (
            <div className="space-y-3">
              {pulseReleases
                .slice(0, 4)
                .map((release) => (
                <div key={release.id} className="rounded-[1.4rem] border border-white/8 bg-white/[0.03] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="text-base font-semibold text-white">{release.title}</h3>
                    <StatusBadge
                      tone={
                        release.early_signal?.state === "winner"
                          ? "success"
                          : release.early_signal?.state === "flat"
                            ? "danger"
                            : "warning"
                      }
                    >
                      {release.early_signal?.state ?? "monitor"}
                    </StatusBadge>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-soft)]">{release.early_signal?.summary}</p>
                  <p className="mt-2 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                    {release.early_signal?.recommended_action} · {release.platform}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </section>
      )}
    </div>
  );
}
