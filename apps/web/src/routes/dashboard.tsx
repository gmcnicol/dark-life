import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { enqueueRedditIncremental, getInsightsSummary, getPublishPlatformSettings, listReleaseQueue, listStories } from "@/lib/stories";
import { buildQueueRunwaySummary } from "@/lib/publish-planning";
import { STATUS_LABELS, nextWorkspaceRoute, statusTone } from "@/lib/workflow";
import {
  ActionButton,
  EmptyState,
  MetricCard,
  PageHeader,
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
  const publishedRecent = insightsSummary?.published_today ?? 0;
  const winners = insightsSummary?.winners ?? 0;
  const flats = insightsSummary?.flat ?? 0;
  const pulseReleases = releaseQueue.filter((release) => Boolean(release.early_signal));
  const runway = buildQueueRunwaySummary(releaseQueue, stories, publishSettingsQuery.data);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Studio control"
        title="Dark Life production board"
        description="Run an early-phase shorts program: keep volume up, know what is scheduled today, and separate winners from flats without over-managing every post."
        actions={
          <>
            <Link
              to="/inbox"
              className="inline-flex items-center justify-center rounded-full bg-[linear-gradient(135deg,#8be9fd,#56d6ff)] px-4 py-2.5 text-sm font-semibold text-slate-950 shadow-[0_12px_30px_rgba(86,214,255,0.25)] transition hover:-translate-y-0.5"
            >
              Open inbox
            </Link>
            <Link
              to="/insights"
              className="inline-flex items-center justify-center rounded-full border border-white/12 bg-white/8 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/12"
            >
              Open insights
            </Link>
            <Link
              to="/board"
              className="inline-flex items-center justify-center rounded-full border border-white/12 bg-white/8 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/12"
            >
              View stage board
            </Link>
          </>
        }
        aside={
          <div className="space-y-3">
            <StatusBadge tone="accent">Early pulse</StatusBadge>
            {[
              { label: "Scheduled today", value: scheduledToday },
              { label: "Published < 4h", value: publishedRecent },
              { label: "Winners", value: winners },
              { label: "Flat", value: flats },
              { label: "Days queued", value: runway.queuedDays.toFixed(1) },
              { label: "Stories needed", value: runway.storiesNeededApprox },
            ].map((item) => (
              <div key={item.label} className="flex items-center justify-between gap-3 rounded-[1.1rem] border border-white/8 bg-white/[0.04] px-4 py-3">
                <span className="text-sm text-[var(--text-soft)]">{item.label}</span>
                <span className="font-display text-2xl text-white">{item.value}</span>
              </div>
            ))}
          </div>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Scheduled today" value={releasesQuery.isLoading ? "…" : scheduledToday} detail="Shorts already slotted into today’s fixed cadence." timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)} />
        <MetricCard label="Published < 4h" value={releasesQuery.isLoading ? "…" : publishedRecent} detail="Fresh posts still inside the early decision window." timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)} />
        <MetricCard label="Early winners" value={releasesQuery.isLoading ? "…" : winners} detail="Posts worth extending into a rewrite, new angle, or series." timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)} />
        <MetricCard label="Flat posts" value={releasesQuery.isLoading ? "…" : flats} detail="Posts to mentally discard and leave alone instead of obsessing over." timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)} />
      </section>

      <Panel className="space-y-3 p-4">
        <SectionHeading
          eyebrow="Queue runway"
          title={`${runway.queuedDays.toFixed(1)} days queued at ${runway.slotsPerDay} shorts/day`}
          description={`Target is about ${runway.targetDays} days. At the current queue mix you need roughly ${runway.storiesNeededApprox} more reviewed stor${runway.storiesNeededApprox === 1 ? "y" : "ies"} to get there.`}
        />
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone="accent">{runway.queuedShorts} shorts queued</StatusBadge>
          <StatusBadge tone="neutral">{runway.reviewableStoriesNow} ingested ready now</StatusBadge>
          <StatusBadge tone="warning">{runway.shortageShorts} shorts short of target</StatusBadge>
          <StatusBadge tone="neutral">Avg {runway.averageShortsPerStory.toFixed(1)} shorts/story</StatusBadge>
        </div>
      </Panel>

      <Panel className="space-y-4">
        <SectionHeading
          eyebrow="Ingestion"
          title="Manual Reddit retrieval"
          description="Run incremental Reddit fetches directly from the overview page. Blank uses the default subreddit order."
          action={
            <ActionButton
              onClick={() => ingestMutation.mutate()}
              disabled={ingestMutation.isPending}
            >
              {ingestMutation.isPending ? "Running…" : "Run retrieval"}
            </ActionButton>
          }
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
