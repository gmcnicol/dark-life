import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import InboxGrid from "@/components/inbox-grid";
import { enqueueRedditIncremental, listStories } from "@/lib/stories";
import { ActionButton, LoadingState, PageHeader, StatusBadge } from "@/components/ui-surfaces";

const INBOX_FILTERS = [
  { value: "active", label: "Active" },
  { value: "all", label: "All" },
  { value: "ingested", label: "Ingested" },
  { value: "generating_script", label: "Generating Script" },
  { value: "scripted", label: "Scripted" },
  { value: "approved", label: "Approved" },
  { value: "media_ready", label: "Media Ready" },
  { value: "queued", label: "Queued" },
  { value: "publish_ready", label: "Publish Ready" },
  { value: "rejected", label: "Rejected" },
];

export default function InboxRoute() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = searchParams.get("status") || "active";
  const storiesQuery = useQuery({
    queryKey: ["stories", "inbox", filter],
    queryFn: () =>
      listStories({
        status: filter === "active" || filter === "all" ? undefined : filter,
        limit: 200,
      }),
  });
  const ingestMutation = useMutation({
    mutationFn: () => enqueueRedditIncremental({}),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["stories"] });
    },
  });

  const stories = useMemo(() => {
    const items = storiesQuery.data ?? [];
    if (filter === "active") {
      return items.filter((story) => story.status !== "rejected");
    }
    return items;
  }, [storiesQuery.data, filter]);

  const statusCounts = stories.reduce<Record<string, number>>((acc, story) => {
    acc[story.status] = (acc[story.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Editorial triage"
        title="Stories"
        description="Review incoming stories, keep active work visible, and run ingestion without leaving the main queue."
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <ActionButton onClick={() => ingestMutation.mutate()} disabled={ingestMutation.isPending}>
              {ingestMutation.isPending ? "Running ingest…" : "Run ingest"}
            </ActionButton>
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
          </div>
        }
        aside={
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <StatusBadge tone="accent">
                {storiesQuery.isLoading ? "Loading" : `${stories.length} visible`}
              </StatusBadge>
              <label className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                Status filter
              </label>
            </div>
            <select
              name="status"
              value={filter}
              onChange={(event) => {
                const value = event.target.value;
                if (value === "active") {
                  setSearchParams({});
                  return;
                }
                setSearchParams({ status: value });
              }}
              className="w-full rounded-[1.2rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
            >
              {INBOX_FILTERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        }
      />

      {storiesQuery.isLoading ? <LoadingState label="Loading story queue…" className="min-h-64" /> : <InboxGrid stories={stories} />}
    </div>
  );
}
