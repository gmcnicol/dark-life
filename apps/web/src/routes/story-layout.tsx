import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useTransition } from "react";
import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import { getStory, updateStoryStatus } from "@/lib/stories";
import { canRejectStory, STATUS_LABELS, statusTone } from "@/lib/workflow";
import { cn } from "@/lib/utils";
import { ActionButton, LoadingState, Panel, StatusBadge } from "@/components/ui-surfaces";

const WORKSPACE_TABS = [
  { key: "review", label: "Review", description: "Approve source and script" },
  { key: "split", label: "Script", description: "Primary script blocks" },
  { key: "media", label: "Media", description: "Attach visual package" },
  { key: "queue", label: "Scheduled", description: "Queue and schedule release" },
  { key: "jobs", label: "Published", description: "Track output and delivery" },
];

export default function StoryLayoutRoute() {
  const params = useParams();
  const location = useLocation();
  const storyId = Number(params.id);
  const queryClient = useQueryClient();
  const [isPending, startTransition] = useTransition();
  const [actionError, setActionError] = useState<string | null>(null);
  const storyQuery = useQuery({
    queryKey: ["story", storyId],
    queryFn: () => getStory(storyId),
    enabled: Number.isFinite(storyId),
  });
  const story = storyQuery.data;

  if (storyQuery.isLoading || !story) {
    return <LoadingState label="Loading story workspace…" className="min-h-56" />;
  }

  const onAlternativesRoute = location.pathname.endsWith("/refinement");
  const activeTab = WORKSPACE_TABS.find((tab) => location.pathname.endsWith(`/${tab.key}`));
  const activeIndex = Math.max(
    WORKSPACE_TABS.findIndex((tab) => tab.key === activeTab?.key),
    0,
  );
  const canReject = canRejectStory(story.status);

  const handleReject = () => {
    startTransition(async () => {
      try {
        setActionError(null);
        await updateStoryStatus(story.id, "rejected");
        await queryClient.invalidateQueries({ queryKey: ["story", storyId] });
        await queryClient.invalidateQueries({ queryKey: ["story-overview", storyId] });
        await queryClient.invalidateQueries({ queryKey: ["stories"] });
      } catch (err) {
        setActionError(err instanceof Error ? err.message : "Failed to reject story");
      }
    });
  };

  return (
    <div className="space-y-6">
      <Panel className="p-4 md:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
                Story workspace
              </p>
              <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
            </div>
            <div className="space-y-2">
              <h1 className="font-display text-3xl tracking-[-0.04em] text-white md:text-4xl">
                {story.title}
              </h1>
              <p className="max-w-3xl text-sm leading-6 text-[var(--text-soft)]">
                Follow the operator path in order. Alternatives are optional and only needed when the primary draft is weak.
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[18rem]">
            <ActionButton
              onClick={handleReject}
              tone="danger"
              disabled={isPending || !canReject}
              className="sm:col-span-2"
            >
              Reject story
            </ActionButton>
            <div className="rounded-[1.2rem] border border-white/8 bg-black/15 px-4 py-3">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                Active stage
              </p>
              <p className="mt-2 text-base font-semibold text-white">
                {onAlternativesRoute ? "Alternatives" : activeTab?.label || "Review"}
              </p>
            </div>
            <div className="rounded-[1.2rem] border border-white/8 bg-black/15 px-4 py-3">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                Story ID
              </p>
              <p className="mt-2 text-base font-semibold text-white">#{story.id}</p>
            </div>
            {actionError ? <StatusBadge tone="danger">{actionError}</StatusBadge> : null}
          </div>
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <Panel className="overflow-x-auto p-3 lg:overflow-visible">
            <div className="flex gap-3 lg:flex-col">
              <div className="hidden px-2 pb-1 lg:block">
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
                  Story stages
                </p>
                <p className="mt-2 text-sm leading-6 text-[var(--text-soft)]">
                  Secondary navigation. The main panel should stay focused on the current step.
                </p>
              </div>

              {WORKSPACE_TABS.map((tab, index) => (
                <NavLink
                  key={tab.key}
                  to={`/story/${storyId}/${tab.key}`}
                  className={({ isActive }) =>
                    cn(
                      "min-w-[10.5rem] rounded-[1.2rem] border px-4 py-3 transition lg:min-w-0",
                      isActive
                        ? "border-cyan-300/35 bg-cyan-300/[0.1] shadow-[0_12px_28px_rgba(56,189,248,0.12)]"
                        : "border-white/8 bg-white/[0.03] hover:border-white/14 hover:bg-white/[0.05]",
                    )
                  }
                >
                  <div className="flex items-start gap-3">
                    <div
                      className={cn(
                        "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[0.68rem] font-semibold uppercase tracking-[0.08em]",
                        activeTab?.key === tab.key
                          ? "border-cyan-300/35 bg-cyan-300/[0.14] text-cyan-100"
                          : index < activeIndex
                            ? "border-emerald-400/25 bg-emerald-400/[0.12] text-emerald-100"
                            : "border-white/10 bg-white/[0.05] text-[var(--muted)]",
                      )}
                    >
                      {index + 1}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-white">{tab.label}</p>
                      <p className="mt-1 text-[0.68rem] uppercase tracking-[0.18em] text-[var(--muted)]">
                        {tab.description}
                      </p>
                    </div>
                  </div>
                </NavLink>
              ))}
            </div>
          </Panel>
        </aside>

        <section className="min-w-0">
          <Outlet />
        </section>
      </div>
    </div>
  );
}
