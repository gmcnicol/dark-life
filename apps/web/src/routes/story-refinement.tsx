import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import {
  activateScriptVersion,
  createScriptBatch,
  createScriptVersionReleases,
  getScriptBatch,
  getPublishPlatformSettings,
  getStoryOverview,
  listAnalysisReports,
} from "@/lib/stories";
import { ActionButton, EmptyState, LoadingState, MetricCard, Panel, SectionHeading, StatusBadge } from "@/components/ui-surfaces";

export default function StoryRefinementRoute() {
  const params = useParams();
  const storyId = Number(params.id);
  const queryClient = useQueryClient();
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

  if (overviewQuery.isLoading || batchesQuery.isLoading || publishPlatformsQuery.isLoading) {
    return <LoadingState label="Loading refinement lab…" className="min-h-56" />;
  }

  const overview = overviewQuery.data;
  const batchDetail = batchDetailQuery.data;
  const candidates = batchDetail?.candidates ?? [];

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-4">
        <MetricCard label="Batches" value={batchesQuery.data?.length ?? 0} detail="Experiment cohorts created for this story." />
        <MetricCard label="Candidates" value={batchDetail?.batch.candidate_count ?? 0} detail="Variants generated in the current cohort." />
        <MetricCard label="Shortlist" value={candidates.filter((candidate) => candidate.selection_state === "shortlisted").length} detail="Scripts currently marked for review or posting." />
        <MetricCard label="Reports" value={reportsQuery.data?.length ?? 0} detail="Analyst outputs attached to this story." />
      </section>

      <Panel className="space-y-4">
        <SectionHeading
          eyebrow="Experiment control"
          title="Refinement lab"
          description="Launch a candidate batch, review ranked variants, promote one to the active story draft, and queue multiple winners for render/publish."
          action={
            <ActionButton onClick={() => launchBatch.mutate()} disabled={launchBatch.isPending}>
              Launch 20-candidate batch
            </ActionButton>
          }
        />
        {batchDetail ? (
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge tone="accent">Batch #{batchDetail.batch.id}</StatusBadge>
            <StatusBadge tone={batchDetail.batch.status === "ready_for_review" ? "success" : batchDetail.batch.status === "errored" ? "danger" : "warning"}>
              {batchDetail.batch.status}
            </StatusBadge>
            {batchDetail.concept ? <StatusBadge tone="neutral">{batchDetail.concept.concept_label}</StatusBadge> : null}
          </div>
        ) : (
          <EmptyState
            title="No refinement batch yet"
            description="Start by launching a batch. The worker will extract a concept, generate candidates, and rank them before they land here."
          />
        )}
      </Panel>

      {batchDetail ? (
        <section className="grid gap-4 xl:grid-cols-2">
          {candidates.map((candidate) => (
            <Panel key={candidate.id} className="space-y-4">
              <SectionHeading
                eyebrow={`Candidate #${candidate.critic_rank ?? "?"}`}
                title={candidate.hook}
                description={`State: ${candidate.selection_state ?? "draft"}${candidate.derived_metrics?.performance_score ? ` · Performance ${candidate.derived_metrics.performance_score}` : ""}`}
                action={
                  <div className="flex flex-wrap gap-2">
                    <ActionButton
                      tone="secondary"
                      onClick={() => activateCandidate.mutate(candidate.id)}
                      disabled={activateCandidate.isPending}
                    >
                      Make active
                    </ActionButton>
                    <ActionButton
                      onClick={() => queueWinner.mutate(candidate.id)}
                      disabled={queueWinner.isPending}
                    >
                      Queue releases
                    </ActionButton>
                  </div>
                }
              />
              <div className="grid gap-3 md:grid-cols-2">
                {candidate.parts.map((part) => (
                  <div key={part.id} className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] p-4">
                    <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                      {part.episode_type || "episode"} {part.index}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-white">{part.hook || part.body_md}</p>
                    <p className="mt-2 text-sm leading-6 text-[var(--text-soft)]">{part.body_md}</p>
                    {part.loop_line ? <p className="mt-3 text-xs uppercase tracking-[0.18em] text-cyan-100/80">Loop: {part.loop_line}</p> : null}
                  </div>
                ))}
              </div>
            </Panel>
          ))}
        </section>
      ) : null}
    </div>
  );
}
