import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import type { StoryStatus } from "@dark-life/shared-types";
import { BionicText } from "@/components/bionic-text";
import ReviewBar from "@/components/review-bar";
import { getStoryOverview } from "@/lib/stories";
import { STATUS_LABELS, statusTone } from "@/lib/workflow";
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
    refetchInterval: (query) => {
      const overview = query.state.data;
      const batches = overview?.script_batches ?? [];
      return batches.some(
        (batch) =>
          (batch.config as { compat?: boolean } | null | undefined)?.compat &&
          ["queued", "processing", "generated", "concept_ready"].includes(batch.status),
      )
        ? 3000
        : false;
    },
  });
  const overview = overviewQuery.data;

  if (overviewQuery.isLoading || !overview) {
    return <LoadingState label="Loading story review…" className="min-h-56" />;
  }

  const story = overview.story;
  const script = overview.active_script;
  const terminal = story.status === "rejected" || story.status === "errored";
  const scriptGenerationPending = overview.script_batches.some(
    (batch) =>
      (batch.config as { compat?: boolean } | null | undefined)?.compat &&
      ["queued", "processing", "generated", "concept_ready"].includes(batch.status),
  ) || story.status === "generating_script";
  const subworkflow = currentReviewSubworkflow({
    hasScript: Boolean(script),
    scriptGenerationPending,
    status: story.status,
  });

  return (
    <div className="space-y-6">
      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_24rem]">
        <Panel className="space-y-5">
          <SectionHeading
            eyebrow="Source"
            title="Original story"
            description="Start here. Read the source in full before deciding whether the narration direction and pacing are ready for the next stage."
          />
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
            {scriptGenerationPending ? <StatusBadge tone="warning">Script generation in progress</StatusBadge> : null}
            {terminal ? (
              <StatusBadge tone="danger">
                Terminal until an operator explicitly reopens it.
              </StatusBadge>
            ) : null}
            {saved === "parts" ? (
              <StatusBadge tone="success">Script blocks saved and returned to review.</StatusBadge>
            ) : null}
          </div>
          <div className="max-h-[72vh] overflow-auto pr-2 text-[1.2rem] leading-10 text-white/92">
            <BionicText
              text={story.body_md || "No source story body is attached yet."}
              showToggle
              className="whitespace-pre-wrap text-[1.2rem] leading-10 text-white/92"
            />
          </div>
        </Panel>

        <div className="space-y-4 lg:sticky lg:top-4">
          <ReviewBar story={story} activeScript={script} scriptGenerationPending={scriptGenerationPending} compact />
          <Panel className="space-y-3 p-4">
            <SectionHeading
              eyebrow="Current sub-workflow"
              title={subworkflow.title}
              description={subworkflow.description}
            />
            <StatusBadge tone={subworkflow.tone}>{subworkflow.badge}</StatusBadge>
          </Panel>
        </div>
      </section>

    </div>
  );
}

function currentReviewSubworkflow({
  hasScript,
  scriptGenerationPending,
  status,
}: {
  hasScript: boolean;
  scriptGenerationPending: boolean;
  status: StoryStatus;
}) {
  if (scriptGenerationPending) {
    return {
      title: "Script generation",
      description: "The source has been accepted and queued. The worker is producing the first draft now.",
      badge: "Running now",
      tone: "warning" as const,
    };
  }
  if (!hasScript) {
    return {
      title: "Source approval",
      description: "Read the source and approve it only if it is worth turning into a first narration draft.",
      badge: "Decision needed",
      tone: "accent" as const,
    };
  }
  if (status === "approved") {
    return {
      title: "Script and media prep",
      description: "The script is accepted. Move into script first, then optional alternatives, then media and scheduling.",
      badge: "Approved",
      tone: "success" as const,
    };
  }
  return {
    title: "Script review",
    description: "Judge the generated draft. If it is good, approve it and move to script. If it is weak, use alternatives before media.",
    badge: "Review draft",
    tone: "accent" as const,
  };
}
