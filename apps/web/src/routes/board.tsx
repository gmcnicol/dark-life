import { useQuery } from "@tanstack/react-query";
import KanbanBoard from "@/components/kanban-board";
import { listStories } from "@/lib/stories";
import { LoadingState, PageHeader, PageStatusBar, StatusBadge } from "@/components/ui-surfaces";

export default function BoardRoute() {
  const storiesQuery = useQuery({
    queryKey: ["stories", "board-summary"],
    queryFn: () => listStories({ limit: 200 }),
  });

  if (storiesQuery.isLoading) {
    return <LoadingState label="Loading pipeline board…" className="min-h-56" />;
  }

  const stories = storiesQuery.data ?? [];
  const blocked = stories.filter((story) => story.status === "errored").length;
  const active = stories.filter((story) => !["published", "rejected"].includes(story.status)).length;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Pipeline board"
        title="Stage pressure"
        description="Scan workflow load by stage, then jump directly into the next valid workspace step for any story that needs attention."
        aside={
          <div className="space-y-3">
            <div className="rounded-[1.1rem] border border-white/8 bg-white/[0.04] px-4 py-3">
              <p className="text-sm text-[var(--text-soft)]">Tracked stories</p>
              <p className="mt-2 font-display text-3xl text-white">{stories.length}</p>
            </div>
          </div>
        }
      />

      <PageStatusBar>
        <StatusBadge tone="accent">{active} active in pipeline</StatusBadge>
        <StatusBadge tone="danger">{blocked} errored</StatusBadge>
        <StatusBadge tone="neutral">Open any card to continue from its next valid step</StatusBadge>
      </PageStatusBar>

      <KanbanBoard />
    </div>
  );
}
