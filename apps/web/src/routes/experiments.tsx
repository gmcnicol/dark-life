import { useQuery } from "@tanstack/react-query";
import { listAnalysisReports, listStories } from "@/lib/stories";
import { EmptyState, LoadingState, MetricCard, PageHeader, Panel, SectionHeading, StatusBadge } from "@/components/ui-surfaces";

export default function ExperimentsRoute() {
  const storiesQuery = useQuery({ queryKey: ["stories", "experiments"], queryFn: () => listStories({ limit: 100 }) });
  const reportsQuery = useQuery({ queryKey: ["analysis-reports"], queryFn: () => listAnalysisReports() });

  if (storiesQuery.isLoading || reportsQuery.isLoading) {
    return <LoadingState label="Loading experiments…" className="min-h-56" />;
  }

  const stories = storiesQuery.data ?? [];
  const reports = reportsQuery.data ?? [];
  const experimentStories = stories.filter((story) => (story.active_script_version_id ?? 0) > 0);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Experiment control"
        title="Refinement experiments"
        description="Track which stories have active script variants, which cohorts have produced reports, and where the learning loop is already generating reviewable insight."
      />

      <section className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Stories with variants" value={experimentStories.length} detail="Stories that already have at least one tracked script version." />
        <MetricCard label="Analysis reports" value={reports.length} detail="Draft analyst outputs waiting for prompt governance." />
        <MetricCard label="Ready to learn" value={reports.filter((report) => report.status === "draft").length} detail="Reports that can be converted into prompt registry changes." />
      </section>

      <Panel className="space-y-4">
        <SectionHeading
          eyebrow="Analyst output"
          title="Latest findings"
          description="The first pass is intentionally lightweight: this view is for scanning high-signal summaries before you drill back into a story workspace."
        />
        {reports.length === 0 ? (
          <EmptyState title="No analysis reports yet" description="Once 72-hour metrics land for published variants, reports will show up here." />
        ) : (
          <div className="space-y-3">
            {reports.slice(0, 8).map((report) => (
              <div key={report.id} className="rounded-[1.35rem] border border-white/8 bg-white/[0.03] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold text-white">Story #{report.story_id} · Batch #{report.batch_id ?? "?"}</h3>
                  <StatusBadge tone="accent">{report.analyst_version}</StatusBadge>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--text-soft)]">{report.summary}</p>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
