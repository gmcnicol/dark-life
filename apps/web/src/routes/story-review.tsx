import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import ReviewBar from "@/components/review-bar";
import { getStoryOverview } from "@/lib/stories";
import { STATUS_LABELS, WORKFLOW_STEPS, workflowStepState } from "@/lib/workflow";
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
      <Panel className="space-y-5">
        <SectionHeading
          eyebrow="Workflow progress"
          title="Review gate"
          description="Use the review bar to generate narration, approve the story, or reject and advance. Everything below is context for that decision."
        />
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
          {WORKFLOW_STEPS.map((step) => {
            const state = workflowStepState(story.status, step);
            return (
              <div
                key={step}
                className={[
                  "rounded-[1.35rem] border px-4 py-4",
                  state === "active" && "border-cyan-300/35 bg-cyan-300/[0.08]",
                  state === "done" && "border-emerald-400/25 bg-emerald-400/[0.08]",
                  state === "terminal" && "border-rose-400/25 bg-rose-400/[0.08]",
                  state === "upcoming" && "border-white/8 bg-white/[0.03]",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--muted)]">
                    {STATUS_LABELS[step]}
                  </span>
                  <span
                    className={[
                      "h-2.5 w-2.5 rounded-full",
                      state === "active" && "bg-cyan-300",
                      state === "done" && "bg-emerald-300",
                      state === "terminal" && "bg-rose-300",
                      state === "upcoming" && "bg-slate-600",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  />
                </div>
              </div>
            );
          })}
        </div>
        {terminal ? (
          <StatusBadge tone="danger">
            This story is terminal until an operator explicitly reopens it.
          </StatusBadge>
        ) : null}
        {saved === "parts" ? (
          <StatusBadge tone="success">Parts saved and the story returned to review.</StatusBadge>
        ) : null}
      </Panel>

      <ReviewBar story={story} activeScript={script} />

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel className="space-y-4">
          <SectionHeading
            eyebrow="Source"
            title="Original story"
            description="Reference the source text while judging whether the narration direction and pacing are ready for the next stage."
          />
          <div className="max-h-[34rem] overflow-auto whitespace-pre-wrap text-sm leading-7 text-[var(--text-soft)]">
            {story.body_md || "No source story body is attached yet."}
          </div>
        </Panel>

        <Panel className="space-y-4">
          <SectionHeading
            eyebrow="Narration"
            title={script ? "Active script draft" : "No active script yet"}
            description={
              script
                ? "The generated narration is the canonical version the split and media stages will build on."
                : "Generate a first-person narration before approving the story into the rest of the production pipeline."
            }
          />
          {script ? (
            <div className="space-y-5 text-sm leading-7 text-[var(--text-soft)]">
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Hook
                </p>
                <p className="mt-2 text-white">{script.hook}</p>
              </div>
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Voiceover
                </p>
                <p className="mt-2 text-white">{script.narration_text}</p>
              </div>
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Outro
                </p>
                <p className="mt-2 text-white">{script.outro}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm leading-7 text-[var(--text-soft)]">
              This story is still waiting for its narrator-ready draft. Generate one to unlock parts, media, and queue setup.
            </p>
          )}
        </Panel>
      </section>
    </div>
  );
}
