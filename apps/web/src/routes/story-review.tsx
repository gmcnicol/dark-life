import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import type { StoryStatus } from "@dark-life/shared-types";
import ReviewBar from "@/components/review-bar";
import { getStoryOverview } from "@/lib/stories";
import { STATUS_LABELS, WORKFLOW_STEPS, statusTone, workflowStepState } from "@/lib/workflow";
import { LoadingState, Panel, SectionHeading, StatusBadge } from "@/components/ui-surfaces";

export default function StoryReviewRoute() {
  const params = useParams();
  const [searchParams] = useSearchParams();
  const storyId = Number(params.id);
  const saved = searchParams.get("saved");
  const overviewQuery = useQuery({
    queryKey: ["story-overview", storyId],
    queryFn: () => getStoryOverview(storyId),
    enabled: Number.isFinite(storyId),
  });
  const overview = overviewQuery.data;

  if (overviewQuery.isLoading || !overview) {
    return <LoadingState label="Loading story review…" className="min-h-56" />;
  }

  const story = overview.story;
  const script = overview.active_script;
  const terminal = story.status === "rejected" || story.status === "errored";

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_24rem]">
        <Panel className="space-y-5">
          <SectionHeading
            eyebrow="Source"
            title="Original story"
            description="Start here. Read the source in full before deciding whether the narration direction and pacing are ready for the next stage."
          />
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
            {terminal ? (
              <StatusBadge tone="danger">
                Terminal until an operator explicitly reopens it.
              </StatusBadge>
            ) : null}
            {saved === "parts" ? (
              <StatusBadge tone="success">Parts saved and returned to review.</StatusBadge>
            ) : null}
          </div>
          <div className="max-h-[72vh] overflow-auto whitespace-pre-wrap pr-2 text-base leading-8 text-white/92">
            {story.body_md || "No source story body is attached yet."}
          </div>
        </Panel>

        <div className="space-y-4 xl:sticky xl:top-4">
          <ReviewBar story={story} activeScript={script} compact />
          <WorkflowSnapshot status={story.status} />
        </div>
      </section>

      <Panel className="space-y-4">
        <SectionHeading
          eyebrow="Narration"
          title={script ? "Active script draft" : "No active script yet"}
          description={
            script
              ? "Review the generated narration after the source text. This is the canonical draft the split and media stages will build on."
              : "Generate a first-person narration once the source is clear enough to move into the rest of the production pipeline."
          }
        />
        {script ? (
          <div className="grid gap-5 xl:grid-cols-[15rem_minmax(0,1fr)]">
            <div className="space-y-3">
              <div className="rounded-[1.15rem] border border-white/8 bg-black/15 px-4 py-3">
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Hook
                </p>
                <p className="mt-2 text-sm leading-6 text-white">{script.hook}</p>
              </div>
              <div className="rounded-[1.15rem] border border-white/8 bg-black/15 px-4 py-3">
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Outro
                </p>
                <p className="mt-2 text-sm leading-6 text-white">{script.outro}</p>
              </div>
            </div>
            <div className="rounded-[1.35rem] border border-white/8 bg-black/10 px-5 py-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                Voiceover
              </p>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-white">{script.narration_text}</p>
            </div>
          </div>
        ) : (
          <p className="text-sm leading-7 text-[var(--text-soft)]">
            This story is still waiting for its narrator-ready draft. Generate one to unlock parts, media, and queue setup.
          </p>
        )}
      </Panel>
    </div>
  );
}

function WorkflowSnapshot({ status }: { status: StoryStatus }) {
  return (
    <Panel className="space-y-4 p-4">
      <SectionHeading
        eyebrow="Workflow"
        title="Compact stage map"
        description="Useful for orientation, but secondary to reading the story."
      />
      <div className="flex flex-wrap gap-2">
        {WORKFLOW_STEPS.map((step) => {
          const state = workflowStepState(status, step);
          return (
            <span
              key={step}
              className={[
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.18em]",
                state === "active" && "border-cyan-300/35 bg-cyan-300/[0.12] text-cyan-100",
                state === "done" && "border-emerald-400/25 bg-emerald-400/[0.12] text-emerald-100",
                state === "terminal" && "border-rose-400/25 bg-rose-400/[0.12] text-rose-100",
                state === "upcoming" && "border-white/8 bg-white/[0.03] text-[var(--text-soft)]",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span
                className={[
                  "h-2 w-2 rounded-full",
                  state === "active" && "bg-cyan-300",
                  state === "done" && "bg-emerald-300",
                  state === "terminal" && "bg-rose-300",
                  state === "upcoming" && "bg-slate-600",
                ]
                  .filter(Boolean)
                  .join(" ")}
              />
              {STATUS_LABELS[step]}
            </span>
          );
        })}
      </div>
    </Panel>
  );
}
