"use client";

import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, RowClickedEvent } from "ag-grid-community";
import { useNavigate } from "react-router-dom";
import { updateStoryStatus, type Story } from "@/lib/stories";
import { STATUS_LABELS, nextWorkspaceRoute } from "@/lib/workflow";
import { DataGridSurface, EmptyState, Panel, StatusBadge } from "./ui-surfaces";

type InboxRow = Story & {
  storyLabel: string;
  destinationLabel: string;
  sourceLabel: string;
  authorLabel: string;
  redditCreatedLabel: string;
};

const DESTINATION_LABELS: Record<string, string> = {
  ingested: "Review",
  generating_script: "Generating",
  scripted: "Review",
  approved: "Media",
  media_ready: "Scheduled",
  queued: "Published",
  rendering: "Published",
  rendered: "Published",
  publish_ready: "Published",
  published: "Published",
  rejected: "Rejected",
  errored: "Review",
};

const REJECT_EXIT_MS = 280;

const baseColumns: Array<ColDef<InboxRow>> = [
  {
    field: "id",
    headerName: "ID",
    width: 88,
    pinned: "left",
    suppressMovable: true,
    sort: "desc",
    valueFormatter: ({ value }) => `#${value}`,
    cellClass: "inbox-grid__id",
  },
  {
    field: "storyLabel",
    headerName: "Story",
    minWidth: 360,
    flex: 2.4,
    tooltipField: "title",
    cellRenderer: ({ data }: { data?: InboxRow }) =>
      data ? (
        <div className="flex min-w-0 flex-col py-1">
          <span className="truncate text-sm font-semibold text-white">{data.storyLabel}</span>
        </div>
      ) : null,
  },
  {
    field: "status",
    headerName: "Status",
    width: 136,
    cellRenderer: ({ data }: { data?: InboxRow }) =>
      data ? (
        <StatusBadge tone={badgeTone(data.status)} className="px-2.5 py-1 text-[0.62rem]">
          {STATUS_LABELS[data.status]}
        </StatusBadge>
      ) : null,
  },
  {
    field: "destinationLabel",
    headerName: "Next",
    width: 132,
    cellClass: "inbox-grid__next",
  },
  {
    field: "authorLabel",
    headerName: "Author",
    minWidth: 160,
    flex: 1,
    cellClass: "inbox-grid__muted",
  },
  {
    field: "redditCreatedLabel",
    headerName: "Reddit",
    minWidth: 168,
    width: 168,
    cellClass: "inbox-grid__muted",
  },
  {
    field: "sourceLabel",
    headerName: "Source",
    minWidth: 170,
    flex: 1.1,
    cellClass: "inbox-grid__muted",
  },
];

export default function InboxGrid({ stories }: { stories: Story[] }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [selectedStoryId, setSelectedStoryId] = useState<number | null>(null);
  const [dismissingStoryIds, setDismissingStoryIds] = useState<number[]>([]);
  const [hiddenStoryIds, setHiddenStoryIds] = useState<number[]>([]);
  const rejectTimersRef = useRef<Map<number, number>>(new Map());
  const rejectStory = useMutation({
    mutationFn: (storyId: number) => updateStoryStatus(storyId, "rejected"),
    onMutate: async (storyId) => {
      const visibleStories = buildRows(stories, query).filter((story) => !hiddenStoryIds.includes(story.id));
      const currentIndex = visibleStories.findIndex((story) => story.id === storyId);
      const nextStoryId = currentIndex >= 0
        ? (visibleStories[currentIndex + 1]?.id ?? visibleStories[currentIndex - 1]?.id ?? null)
        : selectedStoryId;

      if (selectedStoryId === storyId) {
        setSelectedStoryId(nextStoryId);
      }

      setDismissingStoryIds((current) => (current.includes(storyId) ? current : [...current, storyId]));

      const timeoutId = window.setTimeout(() => {
        setHiddenStoryIds((current) => (current.includes(storyId) ? current : [...current, storyId]));
        setDismissingStoryIds((current) => current.filter((id) => id !== storyId));
        rejectTimersRef.current.delete(storyId);
      }, REJECT_EXIT_MS);
      rejectTimersRef.current.set(storyId, timeoutId);

      return { storyId, previousSelectedStoryId: selectedStoryId };
    },
    onError: (_error, storyId, context) => {
      const timeoutId = rejectTimersRef.current.get(storyId);
      if (timeoutId) {
        window.clearTimeout(timeoutId);
        rejectTimersRef.current.delete(storyId);
      }
      setDismissingStoryIds((current) => current.filter((id) => id !== storyId));
      setHiddenStoryIds((current) => current.filter((id) => id !== storyId));
      if (context?.previousSelectedStoryId != null) {
        setSelectedStoryId(context.previousSelectedStoryId);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["stories"] });
    },
  });

  const filteredStories = useMemo<InboxRow[]>(() => {
    return buildRows(stories, query).filter((story) => !hiddenStoryIds.includes(story.id));
  }, [hiddenStoryIds, query, stories]);

  useEffect(() => {
    const liveStoryIds = new Set(stories.map((story) => story.id));
    setHiddenStoryIds((current) => current.filter((id) => liveStoryIds.has(id)));
    setDismissingStoryIds((current) => current.filter((id) => liveStoryIds.has(id)));
  }, [stories]);

  useEffect(() => {
    return () => {
      rejectTimersRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      rejectTimersRef.current.clear();
    };
  }, []);

  useEffect(() => {
    if (filteredStories.length === 0) {
      setSelectedStoryId(null);
      return;
    }
    if (!filteredStories.some((story) => story.id === selectedStoryId)) {
      setSelectedStoryId(filteredStories[0]?.id ?? null);
    }
  }, [filteredStories, selectedStoryId]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
        return;
      }
      if (event.key === "j") {
        event.preventDefault();
        setSelectedStoryId((current) => {
          if (filteredStories.length === 0) {
            return null;
          }
          const currentIndex = filteredStories.findIndex((story) => story.id === current);
          if (currentIndex < 0) {
            return filteredStories[0]?.id ?? null;
          }
          return filteredStories[Math.min(currentIndex + 1, filteredStories.length - 1)]?.id ?? current;
        });
      }
      if (event.key === "k") {
        event.preventDefault();
        setSelectedStoryId((current) => {
          if (filteredStories.length === 0) {
            return null;
          }
          const currentIndex = filteredStories.findIndex((story) => story.id === current);
          if (currentIndex <= 0) {
            return filteredStories[0]?.id ?? null;
          }
          return filteredStories[currentIndex - 1]?.id ?? current;
        });
      }
      if (event.key === "Enter") {
        const story = filteredStories.find((item) => item.id === selectedStoryId);
        if (story) {
          navigate(nextWorkspaceRoute(story.status, story.id, Boolean(story.active_asset_bundle_id)));
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [filteredStories, navigate, selectedStoryId]);

  const columnDefs = useMemo<Array<ColDef<InboxRow>>>(() => {
    return [
      ...baseColumns,
      {
        colId: "actions",
        headerName: "Actions",
        width: 180,
        pinned: "right",
        sortable: false,
        resizable: false,
        suppressMovable: true,
        cellClass: "inbox-grid__actions",
        cellRenderer: ({ data }: { data?: InboxRow }) =>
          data ? (
            <div className="flex items-center gap-2" data-inbox-grid-action="true">
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  navigate(nextWorkspaceRoute(data.status, data.id, Boolean(data.active_asset_bundle_id)));
                }}
                className="rounded-full border border-white/12 bg-white/6 px-3 py-1.5 text-xs font-semibold text-white transition hover:border-cyan-300/35 hover:bg-cyan-300/10"
              >
                Open
              </button>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  rejectStory.mutate(data.id);
                }}
                disabled={data.status === "rejected" || dismissingStoryIds.includes(data.id) || rejectStory.isPending}
                className="rounded-full border border-rose-300/15 bg-rose-300/[0.08] px-3 py-1.5 text-xs font-semibold text-rose-100 transition hover:border-rose-300/30 hover:bg-rose-300/[0.14] disabled:cursor-not-allowed disabled:opacity-45"
              >
                {dismissingStoryIds.includes(data.id) ? "Removing…" : "Reject"}
              </button>
            </div>
          ) : null,
      },
    ];
  }, [dismissingStoryIds, navigate, rejectStory]);

  return (
    <Panel className="space-y-3 p-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
            Active queue
          </p>
          <p className="text-sm leading-6 text-[var(--text-soft)]">
            Sort columns, scan rows, move with `j` and `k`, then hit `Enter` to jump into the right stage.
          </p>
        </div>
        <div className="flex w-full max-w-md flex-col gap-2">
          <label className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
            Quick filter
          </label>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by story, author, source, or id"
            className="w-full rounded-[1rem] border border-white/10 bg-black/20 px-4 py-2.5 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
          />
        </div>
      </div>

      {filteredStories.length === 0 ? (
        <EmptyState
          title="No stories match this filter"
          description="Try a broader status filter or remove some keywords. The inbox only shows stories that still require action."
        />
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge tone="neutral">{filteredStories.length} rows</StatusBadge>
            <StatusBadge tone="warning">
              {(stories.filter((story) => story.status === "ingested").length) + (stories.filter((story) => story.status === "generating_script").length) + (stories.filter((story) => story.status === "scripted").length)} waiting for script
            </StatusBadge>
            <StatusBadge tone="accent">
              {(stories.filter((story) => story.status === "approved").length) + (stories.filter((story) => story.status === "media_ready").length)} ready for media
            </StatusBadge>
            <p className="text-sm text-[var(--text-soft)]">
              Click a row to open its current workspace stage.
            </p>
          </div>

          <DataGridSurface className="inbox-grid-theme h-[68vh] min-h-[28rem]">
            <AgGridReact<InboxRow>
              theme={"legacy"}
              rowData={filteredStories}
              columnDefs={columnDefs}
              rowHeight={48}
              headerHeight={38}
              animateRows
              rowSelection={{ mode: "singleRow", enableClickSelection: true, checkboxes: false }}
              suppressCellFocus
              suppressHorizontalScroll
              defaultColDef={{
                sortable: true,
                resizable: true,
              }}
              onRowClicked={(event: RowClickedEvent<InboxRow>) => {
                const target = event.event?.target;
                if (target instanceof Element && target.closest("[data-inbox-grid-action='true']")) {
                  return;
                }
                if (event.data?.id) {
                  setSelectedStoryId(event.data.id);
                  navigate(nextWorkspaceRoute(event.data.status, event.data.id, Boolean(event.data.active_asset_bundle_id)));
                }
              }}
              rowClassRules={{
                "ag-row-selected": (params) => params.data?.id === selectedStoryId,
                "inbox-grid__row-dismissing": (params) => params.data?.id != null && dismissingStoryIds.includes(params.data.id),
              }}
              getRowId={({ data }) => `${data.id}`}
            />
          </DataGridSurface>
        </div>
      )}
    </Panel>
  );
}

function safeHostname(value: string) {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return value;
  }
}

function badgeTone(status: InboxRow["status"]) {
  if (status === "approved" || status === "media_ready" || status === "queued") {
    return "accent" as const;
  }
  if (status === "published") {
    return "success" as const;
  }
  if (status === "rejected" || status === "errored") {
    return "danger" as const;
  }
  if (status === "generating_script" || status === "scripted") {
    return "warning" as const;
  }
  return "neutral" as const;
}

function formatRedditCreated(value?: string | null) {
  if (!value) {
    return "n/a";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "n/a";
  }
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function buildRows(stories: Story[], query: string): InboxRow[] {
  const needle = query.trim().toLowerCase();
  return stories
    .filter((story) => {
      if (!needle) {
        return true;
      }
      const haystack = `${story.title} ${story.author ?? ""} ${story.source_url ?? ""} ${story.id}`.toLowerCase();
      return haystack.includes(needle);
    })
    .map((story) => ({
      ...story,
      storyLabel: story.title,
      destinationLabel: DESTINATION_LABELS[story.status] ?? STATUS_LABELS[story.status],
      sourceLabel: story.source_url ? safeHostname(story.source_url) : "Local source",
      authorLabel: story.author?.trim() || "Unknown author",
      redditCreatedLabel: formatRedditCreated(story.created_utc),
    }));
}
