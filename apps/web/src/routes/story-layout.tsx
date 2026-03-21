import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import { getStory } from "@/lib/stories";
import { STATUS_LABELS, statusTone } from "@/lib/workflow";
import { cn } from "@/lib/utils";
import { LoadingState, PageHeader, StatusBadge } from "@/components/ui-surfaces";

const WORKSPACE_TABS = [
  { key: "review", label: "Review", description: "Script gate" },
  { key: "refinement", label: "Lab", description: "Experiments" },
  { key: "split", label: "Parts", description: "Timing and segmentation" },
  { key: "media", label: "Media", description: "Asset bundle" },
  { key: "queue", label: "Queue", description: "Render setup" },
  { key: "jobs", label: "Jobs", description: "Output tracking" },
];

export default function StoryLayoutRoute() {
  const params = useParams();
  const location = useLocation();
  const storyId = Number(params.id);
  const storyQuery = useQuery({
    queryKey: ["story", storyId],
    queryFn: () => getStory(storyId),
    enabled: Number.isFinite(storyId),
  });
  const story = storyQuery.data;

  if (storyQuery.isLoading || !story) {
    return <LoadingState label="Loading story workspace…" className="min-h-56" />;
  }

  const activeTab = WORKSPACE_TABS.find((tab) => location.pathname.endsWith(`/${tab.key}`));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Story workspace"
        title={story.title}
        description="This workspace keeps the production path explicit. Each tab represents a stage, and downstream actions should only unlock when the current gate is complete."
        aside={
          <div className="space-y-3">
            <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
            <div className="rounded-[1.2rem] border border-white/8 bg-white/[0.03] p-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                Active stage
              </p>
              <p className="mt-2 text-lg font-semibold text-white">
                {activeTab?.label || "Review"}
              </p>
            </div>
          </div>
        }
      />

      <div className="grid gap-3 md:grid-cols-5">
        {WORKSPACE_TABS.map((tab) => (
          <NavLink
            key={tab.key}
            to={`/story/${storyId}/${tab.key}`}
            className={({ isActive }) =>
              cn(
                "rounded-[1.35rem] border px-4 py-4 transition",
                isActive
                  ? "border-cyan-300/35 bg-cyan-300/[0.08]"
                  : "border-white/8 bg-white/[0.03] hover:border-white/14 hover:bg-white/[0.05]",
              )
            }
          >
            <p className="text-sm font-semibold text-white">{tab.label}</p>
            <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
              {tab.description}
            </p>
          </NavLink>
        ))}
      </div>

      <Outlet />
    </div>
  );
}
