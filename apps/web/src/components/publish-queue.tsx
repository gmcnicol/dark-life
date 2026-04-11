"use client";

import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
import { useEffect, useMemo, useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, RowClickedEvent } from "ag-grid-community";
import type { Release } from "@/lib/stories";
import { approveRelease, clearRelease, completeManualPublish, retryRelease } from "@/lib/stories";
import { formatLocalDateTime } from "@/lib/utils";
import { ActionButton, DataGridSurface, EmptyState, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

type QueueRow = Release & {
  platformLabel: string;
  statusLabel: string;
  targetLabel: string;
  scheduledLabel: string;
  publishedLabel: string;
  signalLabel: string;
  signalAction: string;
};

function toLocalInputValue(value?: string | null): string {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  const normalized = new Date(date.getTime() - offset * 60_000);
  return normalized.toISOString().slice(0, 16);
}

function toIsoValue(value: string): string | null {
  if (!value) {
    return null;
  }
  return new Date(value).toISOString();
}

function releaseTone(status: Release["status"]): "neutral" | "accent" | "success" | "warning" | "danger" {
  if (status === "published") {
    return "success";
  }
  if (status === "errored") {
    return "danger";
  }
  if (status === "manual_handoff") {
    return "warning";
  }
  if (status === "publishing") {
    return "accent";
  }
  return "neutral";
}

function signalTone(
  state?: Release["early_signal"] extends infer T ? T extends { state: infer S } ? S : never : never,
): "neutral" | "warning" | "success" | "danger" {
  if (state === "winner") {
    return "success";
  }
  if (state === "flat") {
    return "danger";
  }
  if (state === "monitor") {
    return "warning";
  }
  return "neutral";
}

function statusLabel(status: Release["status"]): string {
  if (status === "manual_handoff") {
    return "Manual handoff";
  }
  return status.replace(/_/g, " ");
}

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

function targetLabel(release: Release): string {
  if (release.compilation_id) {
    return "Weekly compilation";
  }
  if (release.story_part_id) {
    return `Part ${release.story_part_id}`;
  }
  return "Story cut";
}

function formatDateTime(value?: string | null): string {
  return formatLocalDateTime(value, "Not set");
}

const baseColumns: Array<ColDef<QueueRow>> = [
  {
    field: "id",
    headerName: "ID",
    width: 88,
    pinned: "left",
    sort: "asc",
    suppressMovable: true,
    valueFormatter: ({ value }) => `#${value}`,
    cellClass: "publish-grid__id",
  },
  {
    field: "title",
    headerName: "Release",
    minWidth: 340,
    flex: 2.4,
    tooltipField: "title",
    cellRenderer: ({ data }: { data?: QueueRow }) =>
      data ? (
        <div className="flex min-w-0 flex-col py-1">
          <span className="truncate text-sm font-semibold text-white">{data.title}</span>
          <span className="truncate text-xs text-[var(--text-soft)]">
            {data.platformLabel} · {data.targetLabel} · {data.variant}
          </span>
        </div>
      ) : null,
  },
  {
    field: "statusLabel",
    headerName: "Status",
    width: 160,
    cellRenderer: ({ data }: { data?: QueueRow }) =>
      data ? (
        <StatusBadge tone={releaseTone(data.status)} className="px-2.5 py-1 text-[0.62rem]">
          {data.statusLabel}
        </StatusBadge>
      ) : null,
  },
  {
    field: "signalLabel",
    headerName: "Early signal",
    width: 148,
    cellRenderer: ({ data }: { data?: QueueRow }) =>
      data?.early_signal ? (
        <StatusBadge tone={signalTone(data.early_signal.state)} className="px-2.5 py-1 text-[0.62rem]">
          {data.signalLabel}
        </StatusBadge>
      ) : (
        <span className="text-xs text-[var(--muted)]">Not yet</span>
      ),
  },
  {
    field: "scheduledLabel",
    headerName: "Scheduled",
    minWidth: 156,
    width: 156,
    cellClass: "publish-grid__muted",
  },
  {
    field: "publishedLabel",
    headerName: "Published",
    minWidth: 156,
    width: 156,
    cellClass: "publish-grid__muted",
  },
  {
    field: "platformLabel",
    headerName: "Platform",
    width: 120,
    cellClass: "publish-grid__muted",
  },
];

export default function PublishQueue({ releases }: { releases: Release[] }) {
  const queryClient = useQueryClient();
  const [titleDrafts, setTitleDrafts] = useState<Record<number, string>>({});
  const [descriptionDrafts, setDescriptionDrafts] = useState<Record<number, string>>({});
  const [hashtagDrafts, setHashtagDrafts] = useState<Record<number, string>>({});
  const [scheduleDrafts, setScheduleDrafts] = useState<Record<number, string>>({});
  const [videoIds, setVideoIds] = useState<Record<number, string>>({});
  const [manualNotes, setManualNotes] = useState<Record<number, string>>({});
  const [previewOpen, setPreviewOpen] = useState<Record<number, boolean>>({});
  const [selectedReleaseId, setSelectedReleaseId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | Release["status"]>("all");
  const [isPending, startTransition] = useTransition();

  const mutate = (task: () => Promise<unknown>) => {
    startTransition(async () => {
      await task();
      await queryClient.invalidateQueries();
    });
  };

  const filteredReleases = useMemo<QueueRow[]>(() => {
    const needle = query.trim().toLowerCase();
    return releases
      .filter((release) => statusFilter === "all" || release.status === statusFilter)
      .filter((release) => {
        if (!needle) {
          return true;
        }
        const haystack = `${release.id} ${release.title} ${release.platform} ${release.variant} ${release.status}`.toLowerCase();
        return haystack.includes(needle);
      })
      .map((release) => ({
        ...release,
        platformLabel: platformLabel(release.platform),
        statusLabel: statusLabel(release.status),
        targetLabel: targetLabel(release),
        scheduledLabel: formatDateTime(release.publish_at),
        publishedLabel: formatDateTime(release.published_at),
        signalLabel: release.early_signal?.state ? release.early_signal.state.replace(/_/g, " ") : "Not yet",
        signalAction: release.early_signal?.recommended_action ?? "No decision window yet",
      }));
  }, [query, releases, statusFilter]);

  const selectedRelease = useMemo(
    () => filteredReleases.find((release) => release.id === selectedReleaseId) ?? filteredReleases[0] ?? null,
    [filteredReleases, selectedReleaseId],
  );

  useEffect(() => {
    if (filteredReleases.length === 0) {
      setSelectedReleaseId(null);
      return;
    }
    if (!filteredReleases.some((release) => release.id === selectedReleaseId)) {
      setSelectedReleaseId(filteredReleases[0]?.id ?? null);
    }
  }, [filteredReleases, selectedReleaseId]);

  const approve = (release: Release, scheduled: boolean) => {
    const publishAt = scheduled
      ? toIsoValue(scheduleDrafts[release.id] ?? toLocalInputValue(release.publish_at))
      : null;
    mutate(async () =>
      approveRelease(release.id, {
        title: titleDrafts[release.id] ?? release.title,
        description: descriptionDrafts[release.id] ?? release.description,
        hashtags: (hashtagDrafts[release.id] ?? (release.hashtags ?? []).join(", "))
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        publish_at: publishAt,
      }),
    );
  };

  const completeManual = (release: Release) => {
    mutate(async () =>
      completeManualPublish(release.id, {
        platform_video_id: videoIds[release.id] ?? "",
        notes: manualNotes[release.id],
      }),
    );
  };

  const clear = (release: Release) => {
    mutate(async () => clearRelease(release.id));
  };

  const statusCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const release of releases) {
      counts.set(release.status, (counts.get(release.status) ?? 0) + 1);
    }
    return counts;
  }, [releases]);

  const statusFilters: Array<{ value: "all" | Release["status"]; label: string }> = [
    { value: "all", label: "All" },
    { value: "ready", label: "Ready" },
    { value: "approved", label: "Approved" },
    { value: "scheduled", label: "Scheduled" },
    { value: "publishing", label: "Publishing" },
    { value: "published", label: "Published" },
    { value: "manual_handoff", label: "Manual" },
    { value: "errored", label: "Errored" },
  ];

  const columnDefs = useMemo<Array<ColDef<QueueRow>>>(() => {
    return [
      ...baseColumns,
      {
        colId: "actions",
        headerName: "Actions",
        width: 176,
        pinned: "right",
        sortable: false,
        resizable: false,
        suppressMovable: true,
        cellRenderer: ({ data }: { data?: QueueRow }) =>
          data ? (
            <div className="flex items-center gap-2">
              {data.status === "errored" ? (
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    mutate(async () => retryRelease(data.id));
                  }}
                  className="rounded-full border border-rose-300/18 bg-rose-300/[0.08] px-3 py-1.5 text-xs font-semibold text-rose-100 transition hover:border-rose-300/30 hover:bg-rose-300/[0.14]"
                >
                  Retry
                </button>
              ) : ["ready", "approved"].includes(data.status) ? (
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    approve(data, false);
                  }}
                  className="rounded-full border border-cyan-300/30 bg-cyan-300/[0.14] px-3 py-1.5 text-xs font-semibold text-cyan-50 transition hover:border-cyan-300/50 hover:bg-cyan-300/[0.2]"
                >
                  Upload now
                </button>
              ) : null}
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  clear(data);
                }}
                disabled={isPending}
                className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-semibold text-white transition hover:border-white/16 hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-45"
              >
                Clear
              </button>
            </div>
          ) : null,
      },
    ];
  }, [isPending]);

  if (releases.length === 0) {
    return (
      <EmptyState
        title="No releases in this publish view"
        description="Rendered assets land here once the renderer finishes and the publisher has something real to operate on."
      />
    );
  }

  return (
    <div className="space-y-4">
      <Panel className="space-y-4 p-4">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="space-y-2">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
              Release queue
            </p>
            <p className="text-sm leading-6 text-[var(--text-soft)]">
              One grid, real statuses, and a single selected-release workbench instead of lane cards.
            </p>
          </div>
          <div className="grid w-full max-w-3xl gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
            <label className="space-y-2">
              <span className="block text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                Quick filter
              </span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Filter by title, id, platform, or status"
                className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-2.5 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
              />
            </label>
            <label className="space-y-2">
              <span className="block text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                Status
              </span>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as "all" | Release["status"])}
                className="min-w-[11rem] rounded-[1rem] border border-white/10 bg-black/20 px-4 py-2.5 text-sm text-white outline-none transition focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
              >
                {statusFilters.map((filter) => (
                  <option key={filter.value} value={filter.value}>
                    {filter.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {statusFilters.map((filter) => {
            const count =
              filter.value === "all"
                ? releases.length
                : (statusCounts.get(filter.value) ?? 0);
            if (count === 0 && filter.value !== statusFilter && filter.value !== "all") {
              return null;
            }
            return (
              <button
                key={filter.value}
                type="button"
                onClick={() => setStatusFilter(filter.value)}
                className={[
                  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.18em] transition",
                  statusFilter === filter.value
                    ? "border-cyan-300/35 bg-cyan-300/[0.14] text-cyan-100"
                    : "border-white/8 bg-white/[0.03] text-[var(--text-soft)] hover:border-white/14 hover:bg-white/[0.05]",
                ].join(" ")}
              >
                <span>{filter.label}</span>
                <span className="rounded-full bg-black/20 px-2 py-0.5 text-[0.62rem] text-white/80">{count}</span>
              </button>
            );
          })}
          <p className="text-sm text-[var(--text-soft)]">
            {filteredReleases.length} visible release{filteredReleases.length === 1 ? "" : "s"}.
          </p>
        </div>

        <DataGridSurface className="h-[34rem] min-h-[28rem]">
          <AgGridReact<QueueRow>
            theme={"legacy"}
            rowData={filteredReleases}
            columnDefs={columnDefs}
            rowHeight={48}
            headerHeight={38}
            animateRows
            rowSelection={{ mode: "singleRow", enableClickSelection: true, checkboxes: false }}
            suppressCellFocus
            defaultColDef={{ sortable: true, resizable: true }}
            onRowClicked={(event: RowClickedEvent<QueueRow>) => {
              if (event.data?.id) {
                setSelectedReleaseId(event.data.id);
              }
            }}
            rowClassRules={{
              "ag-row-selected": (params) => params.data?.id === selectedRelease?.id,
            }}
            getRowId={({ data }) => `${data.id}`}
          />
        </DataGridSurface>
      </Panel>

      {selectedRelease ? (
        <Panel className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="space-y-4">
            <SectionHeading
              eyebrow="Selected release"
              title={selectedRelease.title}
              description={`${selectedRelease.platformLabel} · ${selectedRelease.targetLabel} · ${selectedRelease.variant}`}
            />

            {selectedRelease.early_signal ? (
              <div className="rounded-[1rem] border border-white/8 bg-white/[0.03] px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Early signal</p>
                    <p className="mt-1 text-sm text-white">{selectedRelease.early_signal.summary}</p>
                  </div>
                  <StatusBadge tone={signalTone(selectedRelease.early_signal.state)}>
                    {selectedRelease.signalLabel}
                  </StatusBadge>
                </div>
                <p className="mt-3 text-sm text-[var(--text-soft)]">
                  Recommended action: {selectedRelease.signalAction}
                </p>
              </div>
            ) : null}

            <div className="grid gap-3 xl:grid-cols-2">
              <label className="space-y-2 text-sm text-[var(--text-soft)]">
                <span className="block text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Title</span>
                <input
                  value={titleDrafts[selectedRelease.id] ?? selectedRelease.title}
                  onChange={(event) =>
                    setTitleDrafts((current) => ({ ...current, [selectedRelease.id]: event.target.value }))
                  }
                  className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                />
              </label>
              <label className="space-y-2 text-sm text-[var(--text-soft)]">
                <span className="block text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Hashtags</span>
                <input
                  value={hashtagDrafts[selectedRelease.id] ?? (selectedRelease.hashtags ?? []).join(", ")}
                  onChange={(event) =>
                    setHashtagDrafts((current) => ({ ...current, [selectedRelease.id]: event.target.value }))
                  }
                  placeholder="scarystories, nosleep"
                  className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                />
              </label>
            </div>

            <label className="space-y-2 text-sm text-[var(--text-soft)]">
              <span className="block text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Description</span>
              <textarea
                value={descriptionDrafts[selectedRelease.id] ?? selectedRelease.description}
                onChange={(event) =>
                  setDescriptionDrafts((current) => ({ ...current, [selectedRelease.id]: event.target.value }))
                }
                rows={5}
                className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
              />
            </label>

            {selectedRelease.signed_asset_url ? (
              previewOpen[selectedRelease.id] ? (
                <div className="rounded-[1.25rem] border border-white/10 bg-black/20 p-2">
                  <video
                    controls
                    preload="metadata"
                    className="aspect-[9/16] max-h-[32rem] w-full rounded-[1rem] border border-white/8 bg-black/30 object-contain"
                    src={selectedRelease.signed_asset_url}
                  />
                </div>
              ) : (
                <div className="flex items-center justify-between gap-3 rounded-[1rem] border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-[var(--text-soft)]">
                  <span>Preview hidden until you ask for it.</span>
                  <button
                    type="button"
                    onClick={() =>
                      setPreviewOpen((current) => ({
                        ...current,
                        [selectedRelease.id]: true,
                      }))
                    }
                    className="text-sm font-semibold text-cyan-100 transition hover:text-white"
                  >
                    Show preview
                  </button>
                </div>
              )
            ) : null}
          </div>

          <div className="space-y-4">
            <Panel className="space-y-4 p-4">
              <SectionHeading
                eyebrow="Action rail"
                title="Publish actions"
                description="Keep the decisive queue actions in one stable place."
              />
              <div className="flex flex-col gap-3">
                {["ready", "approved"].includes(selectedRelease.status) ? (
                  <>
                    <ActionButton
                      onClick={() => approve(selectedRelease, false)}
                      disabled={isPending || selectedRelease.status === "publishing"}
                    >
                      Upload now
                    </ActionButton>
                    <label className="space-y-2 text-sm text-[var(--text-soft)]">
                      <span className="block text-xs uppercase tracking-[0.2em] text-[var(--muted)]">Schedule</span>
                      <input
                        type="datetime-local"
                        value={scheduleDrafts[selectedRelease.id] ?? toLocalInputValue(selectedRelease.publish_at)}
                        onChange={(event) =>
                          setScheduleDrafts((current) => ({ ...current, [selectedRelease.id]: event.target.value }))
                        }
                        className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                      />
                    </label>
                    <ActionButton
                      tone="secondary"
                      onClick={() => approve(selectedRelease, true)}
                      disabled={isPending || !(scheduleDrafts[selectedRelease.id] ?? toLocalInputValue(selectedRelease.publish_at))}
                    >
                      Schedule
                    </ActionButton>
                  </>
                ) : null}

                {selectedRelease.status === "errored" ? (
                  <ActionButton
                    tone="danger"
                    onClick={() => mutate(async () => retryRelease(selectedRelease.id))}
                    disabled={isPending}
                  >
                    Retry publish
                  </ActionButton>
                ) : null}

                <ActionButton
                  tone="secondary"
                  onClick={() => clear(selectedRelease)}
                  disabled={isPending}
                >
                  Clear from queue
                </ActionButton>

                {selectedRelease.signed_asset_url ? (
                  <a
                    href={selectedRelease.signed_asset_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center rounded-full border border-white/12 bg-white/8 px-4 py-2.5 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/12"
                  >
                    Open asset
                  </a>
                ) : null}
              </div>
            </Panel>

            {selectedRelease.status === "manual_handoff" ? (
              <Panel className="space-y-3 border-amber-400/18 bg-amber-400/10 p-4">
                <SectionHeading
                  eyebrow="Manual handoff"
                  title="Complete platform post"
                  description="Finish the upload on-platform, then record the destination id here."
                />
                <input
                  value={videoIds[selectedRelease.id] ?? ""}
                  onChange={(event) =>
                    setVideoIds((current) => ({ ...current, [selectedRelease.id]: event.target.value }))
                  }
                  placeholder="Platform video id"
                  className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                />
                <input
                  value={manualNotes[selectedRelease.id] ?? ""}
                  onChange={(event) =>
                    setManualNotes((current) => ({ ...current, [selectedRelease.id]: event.target.value }))
                  }
                  placeholder="Manual notes (optional)"
                  className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
                />
                <ActionButton
                  onClick={() => completeManual(selectedRelease)}
                  disabled={isPending || !(videoIds[selectedRelease.id] ?? "").trim()}
                >
                  Complete manual publish
                </ActionButton>
              </Panel>
            ) : null}

            <Panel className="space-y-3 p-4">
              <SectionHeading eyebrow="Queue state" title="Current status" description="Use the grid to scan. Use this panel to act." />
              <div className="flex flex-wrap gap-2">
                <StatusBadge tone={releaseTone(selectedRelease.status)}>{selectedRelease.statusLabel}</StatusBadge>
                <StatusBadge tone="neutral">{selectedRelease.platformLabel}</StatusBadge>
                <StatusBadge tone="neutral">{selectedRelease.variant}</StatusBadge>
              </div>
              {selectedRelease.last_error ? (
                <p className="text-sm text-rose-100">{selectedRelease.last_error}</p>
              ) : (
                <p className="text-sm text-[var(--text-soft)]">
                  Scheduled: {selectedRelease.scheduledLabel}. Published: {selectedRelease.publishedLabel}.
                </p>
              )}
            </Panel>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
