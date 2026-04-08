import { UserButton } from "@clerk/react";
import { type ReactNode, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { clerkEnabled } from "@/lib/auth-config";
import { listReleaseQueue, listStories } from "@/lib/stories";
import { cn } from "@/lib/utils";
import KeyboardShortcuts from "./keyboard-shortcuts";
import { StatusBadge } from "./ui-surfaces";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Overview", kicker: "Studio pulse" },
  { to: "/inbox", label: "Inbox", kicker: "Story triage" },
  { to: "/experiments", label: "Experiments", kicker: "Learning loop" },
  { to: "/board", label: "Pipeline", kicker: "Stage pressure" },
  { to: "/jobs", label: "Renders", kicker: "Worker queue" },
  { to: "/publish", label: "Publish", kicker: "Approval + delivery" },
  { to: "/settings", label: "Settings", kicker: "System defaults" },
];

function routeMeta(pathname: string) {
  if (pathname.startsWith("/story/")) {
    return {
      eyebrow: "Story workspace",
      title: "Operator workspace",
      description:
        "Move a story from script review to media, queueing, and final render checks without losing stage context.",
    };
  }
  if (pathname.startsWith("/inbox")) {
    return {
      eyebrow: "Story inbox",
      title: "Review queue",
      description:
        "Triage incoming stories, keep active work visible, and open the next item without bouncing between dead-end screens.",
    };
  }
  if (pathname.startsWith("/board")) {
    return {
      eyebrow: "Pipeline board",
      title: "Stage pressure",
      description:
        "Spot bottlenecks across the editorial-to-render workflow and focus on what is stalled, at risk, or ready to move.",
    };
  }
  if (pathname.startsWith("/experiments")) {
    return {
      eyebrow: "Experiment loop",
      title: "Refinement telemetry",
      description:
        "Track active script experiments, analyst reports, and prompt governance without leaving the operator surface.",
    };
  }
  if (pathname.startsWith("/jobs")) {
    return {
      eyebrow: "Render jobs",
      title: "Queue telemetry",
      description:
        "Track current worker activity, artifact output, and queue health without dropping into backend logs for every answer.",
    };
  }
  if (pathname.startsWith("/publish")) {
    return {
      eyebrow: "Release queue",
      title: "Publish handoff",
      description:
        "Review releases, schedule automated delivery, and close out manual handoffs without dropping into backend scripts.",
    };
  }
  if (pathname.startsWith("/settings")) {
    return {
      eyebrow: "Studio settings",
      title: "Operating defaults",
      description:
        "Keep voice, subtitles, music policy, and queue cadence visible so operators know which defaults shape each render.",
    };
  }
  return {
    eyebrow: "Dark Life",
    title: "Studio control room",
    description:
      "A production surface for turning stories into rendered videos with clear workflow stages, queue visibility, and confident handoffs.",
  };
}

export function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const meta = routeMeta(location.pathname);
  const storiesQuery = useQuery({
    queryKey: ["stories", "shell"],
    queryFn: () => listStories({ limit: 80 }),
  });
  const releasesQuery = useQuery({
    queryKey: ["release-queue", "shell"],
    queryFn: listReleaseQueue,
  });
  const [command, setCommand] = useState("");
  const [commandOpen, setCommandOpen] = useState(false);

  const stories = storiesQuery.data ?? [];
  const releases = releasesQuery.data ?? [];
  const activeStories = stories.filter((story) => !["published", "rejected"].includes(story.status));
  const queuedStories = stories.filter((story) => ["queued", "rendering"].includes(story.status));

  const results = useMemo(() => {
    const query = command.trim().toLowerCase();
    const navResults = NAV_ITEMS.filter((item) => item.label.toLowerCase().includes(query)).map((item) => ({
      id: item.to,
      label: item.label,
      detail: item.kicker,
      to: item.to,
    }));

    if (!query) {
      return navResults.slice(0, 4);
    }

    const storyResults = stories
      .filter((story) => {
        const haystack = `${story.title} ${story.author ?? ""} ${story.id}`.toLowerCase();
        return haystack.includes(query);
      })
      .slice(0, 5)
      .map((story) => ({
        id: `story-${story.id}`,
        label: story.title,
        detail: `Open story #${story.id}`,
        to: `/story/${story.id}/review`,
      }));

    return [...storyResults, ...navResults].slice(0, 6);
  }, [command, stories]);

  const runCommand = (target?: string) => {
    if (!target) {
      return;
    }
    navigate(target);
    setCommand("");
    setCommandOpen(false);
  };

  return (
    <div className="min-h-screen bg-[var(--app-bg)] text-[var(--text-main)]">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top_left,rgba(96,231,255,0.14),transparent_32%),radial-gradient(circle_at_85%_12%,rgba(251,113,133,0.14),transparent_24%),linear-gradient(180deg,rgba(6,9,16,0.98),rgba(4,6,12,1))]" />
      <div className="pointer-events-none fixed inset-0 opacity-[0.18] [background-image:linear-gradient(rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:72px_72px]" />

      <div className="relative mx-auto grid min-h-screen max-w-[1600px] gap-6 px-4 py-4 md:grid-cols-[18rem_minmax(0,1fr)] md:px-6 md:py-6">
        <aside className="flex flex-col gap-5 rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(11,17,27,0.94),rgba(8,11,18,0.84))] p-4 shadow-[0_24px_90px_rgba(0,0,0,0.28)] backdrop-blur-xl">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.34em] text-cyan-200/80">
                  Dark Life
                </p>
                <h1 className="font-display text-2xl tracking-[-0.04em] text-white">Studio</h1>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge tone="accent">Live</StatusBadge>
                {clerkEnabled ? (
                  <div className="rounded-full border border-white/10 bg-white/5 p-1">
                    <UserButton />
                  </div>
                ) : null}
              </div>
            </div>
            <p className="text-sm leading-6 text-[var(--text-soft)]">
              Editorial triage, media assembly, render queueing, and publish handoff in one operator surface.
            </p>
          </div>

          <nav className="space-y-2">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "group block rounded-[1.25rem] border px-4 py-3 transition duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/70",
                    isActive
                      ? "border-cyan-300/35 bg-cyan-300/10 shadow-[0_12px_24px_rgba(56,189,248,0.12)]"
                      : "border-white/5 bg-white/[0.03] hover:border-white/12 hover:bg-white/[0.06]",
                  )
                }
              >
                <p className="text-sm font-semibold text-white">{item.label}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                  {item.kicker}
                </p>
              </NavLink>
            ))}
          </nav>

          <div className="grid gap-3 sm:grid-cols-3 md:grid-cols-1">
            <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.04] p-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                Active stories
              </p>
              <p className="mt-3 font-display text-4xl tracking-[-0.04em] text-white">
                {storiesQuery.isLoading ? "…" : activeStories.length}
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.04] p-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                Queue pressure
              </p>
              <p className="mt-3 font-display text-4xl tracking-[-0.04em] text-white">
                {storiesQuery.isLoading ? "…" : queuedStories.length}
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-white/8 bg-white/[0.04] p-4">
              <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                Ready to publish
              </p>
              <p className="mt-3 font-display text-4xl tracking-[-0.04em] text-white">
                {releasesQuery.isLoading ? "…" : releases.length}
              </p>
            </div>
          </div>

          <div className="mt-auto rounded-[1.5rem] border border-cyan-300/12 bg-cyan-300/[0.06] p-4">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-cyan-100/80">
              Keyboard
            </p>
            <p className="mt-2 text-sm text-[var(--text-soft)]">
              `g i` opens inbox, `g b` opens pipeline, and `/` focuses the command search.
            </p>
          </div>
        </aside>

        <div className="flex min-h-screen flex-col gap-5">
          <header className="rounded-[2rem] border border-white/10 bg-[linear-gradient(180deg,rgba(13,19,32,0.92),rgba(10,15,27,0.82))] p-4 shadow-[0_24px_90px_rgba(0,0,0,0.22)] backdrop-blur-xl">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-2">
                <p className="text-[0.72rem] font-semibold uppercase tracking-[0.34em] text-[var(--muted)]">
                  {meta.eyebrow}
                </p>
                <div className="space-y-2">
                  <h2 className="font-display text-4xl tracking-[-0.04em] text-white md:text-[3.4rem]">
                    {meta.title}
                  </h2>
                  <p className="max-w-3xl text-sm leading-7 text-[var(--text-soft)] md:text-base">
                    {meta.description}
                  </p>
                </div>
              </div>

              <div className="relative w-full max-w-xl">
                <label className="block text-[0.68rem] font-semibold uppercase tracking-[0.28em] text-[var(--muted)]">
                  Command search
                </label>
                <input
                  id="global-search"
                  type="search"
                  value={command}
                  placeholder="Jump to a route or story title"
                  onFocus={() => setCommandOpen(true)}
                  onBlur={() => {
                    window.setTimeout(() => setCommandOpen(false), 120);
                  }}
                  onChange={(event) => {
                    setCommand(event.target.value);
                    setCommandOpen(true);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      runCommand(results[0]?.to);
                    }
                    if (event.key === "Escape") {
                      setCommandOpen(false);
                    }
                  }}
                  className="mt-2 w-full rounded-[1.25rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/25"
                />
                {commandOpen && results.length > 0 ? (
                  <div className="absolute inset-x-0 top-full z-20 mt-2 rounded-[1.5rem] border border-white/10 bg-[rgba(7,11,18,0.98)] p-2 shadow-[0_24px_80px_rgba(0,0,0,0.28)] backdrop-blur-xl">
                    {results.map((result) => (
                      <button
                        key={result.id}
                        type="button"
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => runCommand(result.to)}
                        className="flex w-full items-center justify-between rounded-[1rem] px-3 py-3 text-left transition hover:bg-white/6"
                      >
                        <span className="text-sm font-medium text-white">{result.label}</span>
                        <span className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                          {result.detail}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-2 md:hidden">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      "rounded-full border px-3 py-2 text-sm font-medium transition",
                      isActive
                        ? "border-cyan-300/35 bg-cyan-300/10 text-cyan-50"
                        : "border-white/10 text-[var(--text-soft)]",
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </header>

          <main className="flex-1 pb-6">{children}</main>
          <KeyboardShortcuts />
        </div>
      </div>
    </div>
  );
}
