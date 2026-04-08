import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { enqueueRedditIncremental, listReleaseQueue, listStories } from "@/lib/stories";
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

export default function DashboardRoute() {
  const queryClient = useQueryClient();
  const [subredditInput, setSubredditInput] = useState("");
  const storiesQuery = useQuery({ queryKey: ["stories"], queryFn: () => listStories({ limit: 100 }) });
  const releasesQuery = useQuery({ queryKey: ["release-queue"], queryFn: listReleaseQueue });
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
  const counts = stories.reduce<Record<string, number>>((acc, story) => {
    acc[story.status] = (acc[story.status] ?? 0) + 1;
    return acc;
  }, {});

  const activeStories = stories
    .filter((story) => !["published", "rejected"].includes(story.status))
    .sort((a, b) => a.id - b.id);

  const stagePressure = [
    { label: "Script review", value: (counts.ingested ?? 0) + (counts.scripted ?? 0) },
    { label: "Media prep", value: (counts.approved ?? 0) + (counts.media_ready ?? 0) },
    { label: "Render queue", value: (counts.queued ?? 0) + (counts.rendering ?? 0) },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Studio control"
        title="Dark Life production board"
        description="Keep the whole content factory legible at a glance: what needs review, what is waiting on media, what is in the render queue, and what is ready for manual publish."
        actions={
          <>
            <Link
              to="/inbox"
              className="inline-flex items-center justify-center rounded-full bg-[linear-gradient(135deg,#8be9fd,#56d6ff)] px-4 py-2.5 text-sm font-semibold text-slate-950 shadow-[0_12px_30px_rgba(86,214,255,0.25)] transition hover:-translate-y-0.5"
            >
              Open inbox
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
            <StatusBadge tone="accent">Queue health</StatusBadge>
            {stagePressure.map((item) => (
              <div key={item.label} className="flex items-center justify-between gap-3 rounded-[1.1rem] border border-white/8 bg-white/[0.04] px-4 py-3">
                <span className="text-sm text-[var(--text-soft)]">{item.label}</span>
                <span className="font-display text-2xl text-white">{item.value}</span>
              </div>
            ))}
          </div>
        }
      />

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Active stories" value={storiesQuery.isLoading ? "…" : activeStories.length} detail="Stories still moving through review, media, render, or publish handoff." timestamp={telemetryTimestampLabel(storiesQuery.dataUpdatedAt)} />
        <MetricCard label="Script pressure" value={storiesQuery.isLoading ? "…" : (counts.ingested ?? 0) + (counts.scripted ?? 0)} detail="Items still waiting for script approval or narrative cleanup." timestamp={telemetryTimestampLabel(storiesQuery.dataUpdatedAt)} />
        <MetricCard label="Render pressure" value={storiesQuery.isLoading ? "…" : (counts.queued ?? 0) + (counts.rendering ?? 0)} detail="Stories already committed to render execution or actively processing." timestamp={telemetryTimestampLabel(storiesQuery.dataUpdatedAt)} />
        <MetricCard label="Publish queue" value={releasesQuery.isLoading ? "…" : releaseQueue.length} detail="Releases currently waiting on approval, schedule, delivery, or manual completion." timestamp={telemetryTimestampLabel(releasesQuery.dataUpdatedAt)} />
      </section>

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

      {(storiesQuery.isLoading || releasesQuery.isLoading) ? (
        <LoadingState label="Loading dashboard queues…" className="min-h-64" />
      ) : (
      <section className="grid gap-4 xl:grid-cols-[1.3fr_0.9fr]">
        <Panel className="space-y-4">
          <SectionHeading
            eyebrow="Operator queue"
            title="Stories needing attention"
            description="Open the highest-value item directly at its next valid stage instead of bouncing through the full workspace."
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
            eyebrow="Manual handoff"
            title="Publish queue"
            description="Releases that have cleared render and are waiting on a final operator action."
            action={
              <Link to="/publish" className="text-sm font-semibold text-[var(--text-soft)] transition hover:text-white">
                Open queue
              </Link>
            }
          />
          {releaseQueue.length === 0 ? (
            <EmptyState
              title="Nothing is publish-ready"
              description="Rendered releases will land here once the pipeline marks them ready for manual posting."
            />
          ) : (
            <div className="space-y-3">
              {releaseQueue.slice(0, 4).map((release) => (
                <div key={release.id} className="rounded-[1.4rem] border border-white/8 bg-white/[0.03] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h3 className="text-base font-semibold text-white">{release.title}</h3>
                    <StatusBadge tone={release.status === "errored" ? "danger" : release.status === "manual_handoff" ? "warning" : "success"}>
                      {release.platform}
                    </StatusBadge>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--text-soft)]">{release.description}</p>
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
