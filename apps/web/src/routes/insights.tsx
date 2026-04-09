import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, RowClickedEvent } from "ag-grid-community";
import { Link } from "react-router-dom";
import {
  getInsightsSummary,
  getReleaseInsightsHistory,
  listInsightsReleases,
  type MetricsSnapshot,
  type Release,
} from "@/lib/stories";
import { EmptyState, LoadingState, PageHeader, Panel, SectionHeading, StatusBadge } from "@/components/ui-surfaces";

type InsightRow = Release & {
  releaseLabel: string;
  publishedLabel: string;
  views: number;
  retention: number;
  engagement: number;
  velocity: number;
  stateLabel: string;
  actionLabel: string;
};

function formatStamp(value?: string | null): string {
  if (!value) {
    return "Awaiting metrics";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function compactNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function signalTone(state?: string | null) {
  if (state === "winner") {
    return "success" as const;
  }
  if (state === "flat") {
    return "danger" as const;
  }
  if (state === "monitor") {
    return "warning" as const;
  }
  return "neutral" as const;
}

function metric(payload: Record<string, number> | null | undefined, key: string): number {
  return Number(payload?.[key] ?? 0);
}

function recentGrowth(snapshots: MetricsSnapshot[]): number {
  if (snapshots.length < 2) {
    return 0;
  }
  const firstSnapshot = snapshots[0];
  const lastSnapshot = snapshots[snapshots.length - 1];
  const first = Number((firstSnapshot?.metrics as Record<string, unknown> | undefined)?.views ?? 0);
  const last = Number((lastSnapshot?.metrics as Record<string, unknown> | undefined)?.views ?? 0);
  return Math.max(0, last - first);
}

const columns: Array<ColDef<InsightRow>> = [
  {
    field: "releaseLabel",
    headerName: "Release",
    pinned: "left",
    minWidth: 320,
    flex: 2.2,
  },
  {
    field: "publishedLabel",
    headerName: "Published",
    minWidth: 156,
    width: 156,
  },
  {
    field: "views",
    headerName: "Views",
    width: 108,
    minWidth: 108,
    valueFormatter: ({ value }) => compactNumber(Number(value ?? 0)),
  },
  {
    field: "velocity",
    headerName: "Velocity",
    width: 112,
    minWidth: 112,
    valueFormatter: ({ value }) => `${Math.round(Number(value ?? 0))}`,
  },
  {
    field: "retention",
    headerName: "Retention",
    width: 116,
    minWidth: 116,
    valueFormatter: ({ value }) => `${Math.round(Number(value ?? 0))}%`,
  },
  {
    field: "engagement",
    headerName: "Engage",
    width: 112,
    minWidth: 112,
    valueFormatter: ({ value }) => Number(value ?? 0).toFixed(1),
  },
  {
    field: "stateLabel",
    headerName: "State",
    width: 130,
    minWidth: 130,
    cellRenderer: ({ data }: { data?: InsightRow }) =>
      data ? <StatusBadge tone={signalTone(data.early_signal?.state)}>{data.stateLabel}</StatusBadge> : null,
  },
  {
    field: "actionLabel",
    headerName: "Recommended action",
    minWidth: 220,
    flex: 1.4,
  },
];

export default function InsightsRoute() {
  const summaryQuery = useQuery({
    queryKey: ["insights-summary"],
    queryFn: () => getInsightsSummary(30),
    refetchInterval: 60_000,
  });
  const releasesQuery = useQuery({
    queryKey: ["insights-releases"],
    queryFn: () => listInsightsReleases(30),
    refetchInterval: 60_000,
  });
  const [selectedReleaseId, setSelectedReleaseId] = useState<number | null>(null);

  const rows = useMemo<InsightRow[]>(
    () =>
      (releasesQuery.data ?? []).map((release) => ({
        ...release,
        releaseLabel: release.title,
        publishedLabel: formatStamp(release.published_at),
        views: metric(release.latest_metrics, "views"),
        retention: metric(release.latest_metrics, "percent_viewed"),
        engagement: metric(release.latest_derived_metrics, "engagement_score"),
        velocity: Math.min(100, metric(release.latest_metrics, "views") / 40),
        stateLabel: release.early_signal?.state ?? (release.latest_metrics_sync_at ? "monitor" : "awaiting"),
        actionLabel: release.early_signal?.recommended_action ?? "Awaiting metrics",
      })),
    [releasesQuery.data],
  );

  useEffect(() => {
    if (!rows.length) {
      setSelectedReleaseId(null);
      return;
    }
    if (!rows.some((row) => row.id === selectedReleaseId)) {
      setSelectedReleaseId(rows[0]?.id ?? null);
    }
  }, [rows, selectedReleaseId]);

  const selectedRelease = rows.find((row) => row.id === selectedReleaseId) ?? null;
  const historyQuery = useQuery({
    queryKey: ["release-insights-history", selectedReleaseId],
    queryFn: () => getReleaseInsightsHistory(selectedReleaseId ?? 0, 24 * 7),
    enabled: Boolean(selectedReleaseId),
  });

  if (summaryQuery.isLoading || releasesQuery.isLoading) {
    return <LoadingState label="Loading release insights…" className="min-h-64" />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Performance pulse"
        title="Insights"
        description="Review the last 30 days of published YouTube Shorts in one dense table. Winners, flats, and stale syncs should be obvious without digging through provider dashboards."
        actions={
          <>
            <Link
              to="/publish"
              className="inline-flex items-center justify-center rounded-full bg-[linear-gradient(135deg,#8be9fd,#56d6ff)] px-4 py-2.5 text-sm font-semibold text-slate-950 shadow-[0_12px_30px_rgba(86,214,255,0.25)] transition hover:-translate-y-0.5"
            >
              Open publish queue
            </Link>
            <Link
              to="/dashboard"
              className="inline-flex items-center justify-center rounded-full border border-white/12 bg-white/8 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/12"
            >
              Back to dashboard
            </Link>
          </>
        }
        aside={
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3 rounded-[1.1rem] border border-white/8 bg-white/[0.04] px-4 py-3">
              <span className="text-sm text-[var(--text-soft)]">Tracked</span>
              <span className="font-display text-2xl text-white">{summaryQuery.data?.tracked_releases ?? 0}</span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-[1.1rem] border border-white/8 bg-white/[0.04] px-4 py-3">
              <span className="text-sm text-[var(--text-soft)]">Published today</span>
              <span className="font-display text-2xl text-white">{summaryQuery.data?.published_today ?? 0}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusBadge tone="success">{summaryQuery.data?.winners ?? 0} winners</StatusBadge>
              <StatusBadge tone="warning">{summaryQuery.data?.monitor ?? 0} monitor</StatusBadge>
              <StatusBadge tone="danger">{summaryQuery.data?.flat ?? 0} flat</StatusBadge>
            </div>
            <p className="text-sm leading-6 text-[var(--text-soft)]">
              Last sync {formatStamp(summaryQuery.data?.last_sync_at)}
            </p>
          </div>
        }
      />

      <Panel className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone="warning">{summaryQuery.data?.awaiting_metrics ?? 0} awaiting metrics</StatusBadge>
          <StatusBadge tone="warning">{summaryQuery.data?.stale_sync ?? 0} stale sync</StatusBadge>
          <StatusBadge tone="neutral">30-day YouTube window</StatusBadge>
        </div>
        <p className="text-sm text-[var(--text-soft)]">
          The grid is the primary operator surface. Read state first, then use the detail panels to see why a release is winning or stalling.
        </p>
      </Panel>

      {!rows.length ? (
        <EmptyState
          title="No tracked releases yet"
          description="Once YouTube Shorts are published and the insights worker has synced them, this grid will fill with state, velocity, and retention data."
        />
      ) : (
        <>
          <div className="ag-theme-quartz-dark h-[34rem] min-h-[30rem] overflow-hidden rounded-[1.35rem] border border-white/10">
            <AgGridReact<InsightRow>
              rowData={rows}
              columnDefs={columns}
              defaultColDef={{
                sortable: true,
                resizable: true,
                filter: true,
                cellStyle: {
                  backgroundColor: "transparent",
                  color: "rgba(229,231,235,0.94)",
                  borderColor: "rgba(255,255,255,0.08)",
                },
              }}
              rowHeight={46}
              headerHeight={38}
              animateRows
              getRowId={({ data }) => String(data.id)}
              onRowClicked={(event: RowClickedEvent<InsightRow>) => setSelectedReleaseId(event.data?.id ?? null)}
            />
          </div>

          {selectedRelease ? (
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_22rem]">
              <Panel className="space-y-4 p-5">
                <SectionHeading
                  eyebrow="Selected release"
                  title={selectedRelease.title}
                  description={selectedRelease.early_signal?.summary ?? "Awaiting metrics classification."}
                  action={
                    <div className="flex flex-wrap gap-2">
                      <StatusBadge tone={signalTone(selectedRelease.early_signal?.state)}>
                        {selectedRelease.stateLabel}
                      </StatusBadge>
                      <StatusBadge tone="neutral">{selectedRelease.platform}</StatusBadge>
                    </div>
                  }
                />
                <div className="grid gap-3 md:grid-cols-4">
                  {[
                    { label: "Views", value: compactNumber(selectedRelease.views) },
                    { label: "Retention", value: `${Math.round(selectedRelease.retention)}%` },
                    { label: "Engagement", value: selectedRelease.engagement.toFixed(1) },
                    { label: "Synced", value: formatStamp(selectedRelease.latest_metrics_sync_at) },
                  ].map((item) => (
                    <div key={item.label} className="rounded-[1.1rem] border border-white/8 bg-white/[0.03] p-4">
                      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">{item.label}</p>
                      <p className="mt-3 text-2xl font-semibold text-white">{item.value}</p>
                    </div>
                  ))}
                </div>

                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
                  <div className="space-y-3">
                    <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">Recent trend</p>
                    {historyQuery.isLoading ? (
                      <LoadingState label="Loading release history…" className="min-h-32" />
                    ) : historyQuery.data?.snapshots?.length ? (
                      <div className="space-y-2">
                        {historyQuery.data.snapshots.slice(-8).map((snapshot) => {
                          const snapshotMetrics = snapshot.metrics as Record<string, unknown>;
                          const views = Number(snapshotMetrics.views ?? 0);
                          return (
                            <div key={snapshot.id} className="grid grid-cols-[7.5rem_minmax(0,1fr)_4rem] items-center gap-3 rounded-[1rem] border border-white/8 bg-white/[0.03] px-3 py-2">
                              <span className="text-xs uppercase tracking-[0.16em] text-[var(--muted)]">
                                {snapshot.captured_at ? formatStamp(snapshot.captured_at) : `+${snapshot.window_hours}h`}
                              </span>
                              <div className="h-2 rounded-full bg-white/6">
                                <div
                                  className="h-2 rounded-full bg-[linear-gradient(90deg,#7dd3fc,#34d399)]"
                                  style={{
                                    width: `${Math.min(100, (views / Math.max(selectedRelease.views, 1)) * 100)}%`,
                                  }}
                                />
                              </div>
                              <span className="text-right text-sm text-white">{compactNumber(views)}</span>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <EmptyState
                        title="No history yet"
                        description="The insights worker has not written any hourly snapshots for this release yet."
                      />
                    )}
                  </div>

                  <div className="space-y-3 rounded-[1.25rem] border border-white/8 bg-white/[0.03] p-4">
                    <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">Recommended next step</p>
                    <p className="text-lg font-semibold text-white">
                      {selectedRelease.early_signal?.recommended_action ?? "Awaiting metrics"}
                    </p>
                    <p className="text-sm leading-6 text-[var(--text-soft)]">
                      {selectedRelease.early_signal?.summary ?? "No hourly data has landed for this release yet."}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Link
                        to="/publish"
                        className="inline-flex items-center justify-center rounded-full border border-white/12 bg-white/8 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/12"
                      >
                        Open publish queue
                      </Link>
                      <Link
                        to={`/story/${selectedRelease.story_id}/jobs`}
                        className="inline-flex items-center justify-center rounded-full border border-white/12 bg-white/8 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/12"
                      >
                        Open story
                      </Link>
                    </div>
                    <p className="text-sm text-[var(--text-soft)]">
                      7-day growth: {historyQuery.data ? compactNumber(recentGrowth(historyQuery.data.snapshots)) : "0"}
                    </p>
                  </div>
                </div>
              </Panel>

              <Panel className="space-y-4 p-4">
                <SectionHeading eyebrow="Latest metrics" title="Raw release telemetry" />
                <div className="space-y-3">
                  {Object.entries(selectedRelease.latest_metrics ?? {}).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between gap-3 rounded-[1rem] border border-white/8 bg-white/[0.03] px-3 py-2">
                      <span className="text-sm capitalize text-[var(--text-soft)]">{key.replace(/_/g, " ")}</span>
                      <span className="text-sm font-semibold text-white">{Number(value).toFixed(key.includes("rate") || key.includes("percent") ? 1 : 0)}</span>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
