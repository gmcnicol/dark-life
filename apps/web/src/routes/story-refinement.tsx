import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
import { type CSSProperties, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AgGridReact } from "ag-grid-react";
import type { ColDef, RowClickedEvent } from "ag-grid-community";
import { useParams } from "react-router-dom";
import {
  activateScriptVersion,
  createScriptBatch,
  createScriptVersionReleases,
  getPublishPlatformSettings,
  getScriptBatch,
  getStoryOverview,
  listAnalysisReports,
  type ScriptBatchDetail,
} from "@/lib/stories";
import {
  ActionButton,
  EmptyState,
  LoadingState,
  MetricCard,
  Panel,
  SectionHeading,
  StatusBadge,
} from "@/components/ui-surfaces";
import { BionicText } from "@/components/bionic-text";

type CandidateRow = ScriptBatchDetail["candidates"][number] & {
  orderValue: number;
  orderLabel: string;
  scoreLabel: string;
  partsCount: number;
  stateLabel: string;
  activeLabel: string;
};

const CANDIDATE_COLUMNS: Array<ColDef<CandidateRow>> = [
  {
    field: "orderValue",
    headerName: "Rank",
    width: 96,
    pinned: "left",
    suppressMovable: true,
    sort: "asc",
    valueFormatter: ({ data }) => data?.orderLabel ?? "n/a",
  },
  {
    field: "hook",
    headerName: "Hook",
    minWidth: 260,
    flex: 1.8,
    wrapText: true,
    autoHeight: true,
  },
  {
    field: "selection_state",
    headerName: "State",
    minWidth: 140,
    valueGetter: ({ data }) => data?.stateLabel ?? "draft",
  },
  {
    field: "scoreLabel",
    headerName: "Score",
    width: 120,
  },
  {
    field: "partsCount",
    headerName: "Parts",
    width: 100,
  },
  {
    field: "activeLabel",
    headerName: "Live",
    width: 100,
  },
];

export default function StoryRefinementRoute() {
  const params = useParams();
  const storyId = Number(params.id);
  const queryClient = useQueryClient();
  const [selectedCandidateId, setSelectedCandidateId] = useState<number | null>(null);
  const overviewQuery = useQuery({
    queryKey: ["story-overview", storyId],
    queryFn: () => getStoryOverview(storyId),
    enabled: Number.isFinite(storyId),
  });
  const batchesQuery = useQuery({
    queryKey: ["story-batches", storyId],
    queryFn: async () => {
      const overview = await getStoryOverview(storyId);
      return overview.script_batches ?? [];
    },
    enabled: Number.isFinite(storyId),
  });
  const latestBatchId = batchesQuery.data?.[0]?.id;
  const batchDetailQuery = useQuery({
    queryKey: ["script-batch", latestBatchId],
    queryFn: () => getScriptBatch(Number(latestBatchId)),
    enabled: Boolean(latestBatchId),
    refetchInterval: (query) => {
      const status = (query.state.data as { batch?: { status?: string } } | undefined)?.batch?.status;
      return status && ["queued", "processing", "generated", "concept_ready"].includes(status) ? 5000 : false;
    },
  });
  const reportsQuery = useQuery({
    queryKey: ["analysis-reports", storyId],
    queryFn: () => listAnalysisReports({ story_id: storyId }),
    enabled: Number.isFinite(storyId),
  });
  const publishPlatformsQuery = useQuery({
    queryKey: ["publish-platform-settings"],
    queryFn: getPublishPlatformSettings,
  });

  const launchBatch = useMutation({
    mutationFn: () => createScriptBatch(storyId, { candidate_count: 20, shortlisted_count: 3, temperature: 1 }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["story-overview", storyId] });
      await queryClient.invalidateQueries({ queryKey: ["story-batches", storyId] });
    },
  });

  const activateCandidate = useMutation({
    mutationFn: (scriptVersionId: number) => activateScriptVersion(scriptVersionId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["story-overview", storyId] });
      await queryClient.invalidateQueries({ queryKey: ["script-batch", latestBatchId] });
    },
  });

  const queueWinner = useMutation({
    mutationFn: (scriptVersionId: number) =>
      createScriptVersionReleases(scriptVersionId, {
        platforms: publishPlatformsQuery.data?.active_platforms ?? ["youtube"],
        preset_slug: "short-form",
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["story-overview", storyId] });
    },
  });

  const batchDetail = batchDetailQuery.data;
  const candidates = batchDetail?.candidates ?? [];
  const shortlistedCount = candidates.filter((candidate) => candidate.selection_state === "shortlisted").length;
  const candidateRows = candidates.map((candidate, index) => {
    const score = numericMetric(candidate.derived_metrics?.performance_score);
    return {
      ...candidate,
      orderValue: candidate.critic_rank ?? index + 1,
      orderLabel: candidate.critic_rank ? `#${candidate.critic_rank}` : `#${index + 1}`,
      scoreLabel: score ? `${score}` : "n/a",
      partsCount: candidate.parts.length,
      stateLabel: candidate.selection_state ?? "draft",
      activeLabel: candidate.is_active ? "Live" : "Idle",
    };
  }).sort((left, right) => left.orderValue - right.orderValue);

  useEffect(() => {
    const firstCandidate = candidateRows[0];
    if (!firstCandidate) {
      setSelectedCandidateId(null);
      return;
    }
    if (!candidateRows.some((candidate) => candidate.id === selectedCandidateId)) {
      const liveCandidate = candidateRows.find((candidate) => candidate.is_active);
      setSelectedCandidateId(liveCandidate?.id ?? firstCandidate.id);
    }
  }, [candidateRows, selectedCandidateId]);

  const selectedCandidate =
    candidateRows.find((candidate) => candidate.id === selectedCandidateId) ?? candidateRows[0] ?? null;
  if (overviewQuery.isLoading || batchesQuery.isLoading || publishPlatformsQuery.isLoading) {
    return <LoadingState label="Loading refinement lab…" className="min-h-56" />;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-4">
        <MetricCard label="Batches" value={batchesQuery.data?.length ?? 0} detail="Experiment cohorts created for this story." />
        <MetricCard label="Candidates" value={batchDetail?.batch.candidate_count ?? 0} detail="Variants generated in the current cohort." />
        <MetricCard label="Shortlist" value={shortlistedCount} detail="Scripts currently marked for review or posting." />
        <MetricCard label="Reports" value={reportsQuery.data?.length ?? 0} detail="Analyst outputs attached to this story." />
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <Panel className="space-y-4">
          <SectionHeading
            eyebrow="Experiment control"
            title="Refinement lab"
            description="Compare ranked variants in order, inspect one candidate at a time, and keep the main decision surface focused on the selected script."
            action={
              <ActionButton onClick={() => launchBatch.mutate()} disabled={launchBatch.isPending}>
                Launch 20-candidate batch
              </ActionButton>
            }
          />
          {batchDetail ? (
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge tone="accent">Batch #{batchDetail.batch.id}</StatusBadge>
              <StatusBadge tone={statusTone(batchDetail.batch.status)}>{batchDetail.batch.status}</StatusBadge>
              {batchDetail.concept ? <StatusBadge tone="neutral">{batchDetail.concept.concept_label}</StatusBadge> : null}
              {batchDetail.report ? <StatusBadge tone="success">Report ready</StatusBadge> : null}
            </div>
          ) : (
            <EmptyState
              title="No refinement batch yet"
              description="Start by launching a batch. The worker will extract a concept, generate candidates, and rank them before they land here."
            />
          )}
        </Panel>

        <Panel className="space-y-4 p-4">
          <SectionHeading
            eyebrow="Selection mode"
            title="Operator guidance"
            description="The table is for ranking and comparison. The detail pane below is where activation and queueing happen."
          />
          <div className="space-y-2 text-sm leading-6 text-[var(--text-soft)]">
            <p>1. Scan rank, state, score, and hook without losing your place.</p>
            <p>2. Select one row to inspect the full parts stack.</p>
            <p>3. Promote or queue only from the focused candidate.</p>
          </div>
          {batchDetail?.report?.summary ? (
            <div className="rounded-[1.2rem] border border-white/8 bg-black/15 p-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                Latest report
              </p>
              <p className="mt-2 text-sm leading-6 text-white/90">{batchDetail.report.summary}</p>
            </div>
          ) : null}
        </Panel>
      </section>

      {batchDetail ? (
        <section className="space-y-4">
          {candidateRows.length > 1 ? (
            <Panel className="space-y-4 p-4">
              <SectionHeading
                eyebrow="Ordered comparison"
                title="Candidate queue"
                description="Rows are ordered by critic rank ascending. `#1` is the intended top candidate and stays at the top by default."
              />
              <div
                className="ag-theme-quartz-dark overflow-hidden rounded-[1.35rem] border border-white/10"
                style={
                  {
                    width: "100%",
                    ["--ag-background-color" as string]: "rgba(6, 10, 16, 0.88)",
                    ["--ag-foreground-color" as string]: "rgb(241, 245, 249)",
                    ["--ag-header-background-color" as string]: "rgba(255, 255, 255, 0.04)",
                    ["--ag-header-foreground-color" as string]: "rgba(226, 232, 240, 0.84)",
                    ["--ag-row-hover-color" as string]: "rgba(56, 189, 248, 0.08)",
                    ["--ag-selected-row-background-color" as string]: "rgba(56, 189, 248, 0.14)",
                    ["--ag-border-color" as string]: "rgba(255, 255, 255, 0.08)",
                    ["--ag-odd-row-background-color" as string]: "rgba(255, 255, 255, 0.02)",
                    ["--ag-font-family" as string]: "inherit",
                  } as CSSProperties
                }
              >
                <AgGridReact<CandidateRow>
                  theme={"legacy"}
                  rowData={candidateRows}
                  columnDefs={CANDIDATE_COLUMNS}
                  rowHeight={72}
                  headerHeight={44}
                  animateRows
                  domLayout="autoHeight"
                  rowSelection={{ mode: "singleRow", enableClickSelection: true }}
                  suppressCellFocus
                  suppressHorizontalScroll
                  defaultColDef={{
                    sortable: true,
                    resizable: true,
                  }}
                  onRowClicked={(event: RowClickedEvent<CandidateRow>) => {
                    if (event.data?.id) {
                      setSelectedCandidateId(event.data.id);
                    }
                  }}
                  getRowId={({ data }) => `${data.id}`}
                />
              </div>
            </Panel>
          ) : null}

          {selectedCandidate ? (
            <Panel className="space-y-5">
              <SectionHeading
                eyebrow={selectedCandidate.orderLabel}
                title={selectedCandidate.hook}
                description={`State: ${selectedCandidate.stateLabel}${selectedCandidate.scoreLabel !== "n/a" ? ` · Performance ${selectedCandidate.scoreLabel}` : ""}`}
                action={
                  <div className="flex flex-wrap gap-2">
                    <ActionButton
                      tone="secondary"
                      onClick={() => activateCandidate.mutate(selectedCandidate.id)}
                      disabled={activateCandidate.isPending || selectedCandidate.is_active}
                    >
                      {selectedCandidate.is_active ? "Active script" : "Make active"}
                    </ActionButton>
                    <ActionButton
                      onClick={() => queueWinner.mutate(selectedCandidate.id)}
                      disabled={queueWinner.isPending}
                    >
                      Queue releases
                    </ActionButton>
                  </div>
                }
              />

              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge tone={candidateStateTone(selectedCandidate)}>
                  {selectedCandidate.stateLabel}
                </StatusBadge>
                {selectedCandidate.is_active ? <StatusBadge tone="accent">Current live draft</StatusBadge> : null}
                <StatusBadge tone="neutral">{selectedCandidate.partsCount} parts</StatusBadge>
              </div>

              <div className="space-y-3">
                {selectedCandidate.parts
                  .slice()
                  .sort((left, right) => left.index - right.index)
                  .map((part) => (
                    <div
                      key={part.id}
                      className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] p-4"
                    >
                      <div className="flex items-center gap-3 border-b border-white/8 pb-3">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cyan-300/20 bg-cyan-300/[0.1] text-sm font-semibold text-cyan-100">
                          {part.index}
                        </div>
                        <div className="min-w-0">
                          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                            {part.episode_type || "episode"}
                          </p>
                          <p className="mt-1 text-sm font-semibold leading-6 text-white">
                            {part.hook || "No hook"}
                          </p>
                        </div>
                      </div>

                      <div className="mt-4 space-y-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">
                          Script block
                        </p>
                        <BionicText
                          text={part.body_md}
                          className="max-w-none text-[1.08rem] leading-9 text-[var(--text-soft)]"
                        />

                        {part.loop_line ? (
                          <div className="rounded-[0.9rem] border border-cyan-300/12 bg-cyan-300/[0.06] px-3 py-2">
                            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-100/80">
                              Loop line
                            </p>
                            <p className="mt-1 text-sm leading-6 text-cyan-50">{part.loop_line}</p>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))}
              </div>
            </Panel>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function statusTone(status: string) {
  if (status === "ready_for_review" || status === "metrics_ready" || status === "published") {
    return "success" as const;
  }
  if (status === "errored") {
    return "danger" as const;
  }
  return "warning" as const;
}

function candidateStateTone(candidate: CandidateRow) {
  if (candidate.is_active) {
    return "accent" as const;
  }
  if (candidate.selection_state === "shortlisted") {
    return "success" as const;
  }
  return "neutral" as const;
}

function numericMetric(value: unknown) {
  if (typeof value === "number") {
    return value.toFixed(2);
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toFixed(2) : null;
  }
  return null;
}
