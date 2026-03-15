"use client";

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Story } from "@/lib/stories";
import { STATUS_LABELS, nextWorkspaceRoute, statusTone } from "@/lib/workflow";
import { cn } from "@/lib/utils";
import { EmptyState, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

export default function InboxGrid({ stories }: { stories: Story[] }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const filteredStories = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return stories;
    }

    return stories.filter((story) => {
      const haystack = `${story.title} ${story.author ?? ""} ${story.source_url ?? ""} ${story.id}`.toLowerCase();
      return haystack.includes(needle);
    });
  }, [query, stories]);

  useEffect(() => {
    setSelectedIndex((current) => {
      if (filteredStories.length === 0) {
        return -1;
      }
      if (current < 0) {
        return -1;
      }
      return Math.min(current, filteredStories.length - 1);
    });
  }, [filteredStories.length]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
        return;
      }
      if (event.key === "j") {
        event.preventDefault();
        setSelectedIndex((current) =>
          filteredStories.length === 0
            ? -1
            : current < 0
              ? 0
              : Math.min(current + 1, filteredStories.length - 1),
        );
      }
      if (event.key === "k") {
        event.preventDefault();
        setSelectedIndex((current) => {
          if (filteredStories.length === 0) {
            return -1;
          }
          if (current <= 0) {
            return 0;
          }
          return current - 1;
        });
      }
      if (event.key === "Enter") {
        const story = filteredStories[selectedIndex];
        if (story) {
          navigate(nextWorkspaceRoute(story.status, story.id, Boolean(story.active_asset_bundle_id)));
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [filteredStories, navigate, selectedIndex]);

  const openStory = (story: Story) => {
    navigate(nextWorkspaceRoute(story.status, story.id, Boolean(story.active_asset_bundle_id)));
  };

  return (
    <Panel className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <SectionHeading
          eyebrow="Active queue"
          title="Operator inbox"
          description="Use `j`, `k`, and `Enter` to move through the queue quickly, or click straight into the right workflow stage."
        />
        <div className="flex w-full max-w-md flex-col gap-2">
          <label className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
            Quick filter
          </label>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter by story, author, source, or id"
            className="w-full rounded-[1.15rem] border border-white/10 bg-black/20 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
          />
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filteredStories.length === 0 ? (
          <div className="md:col-span-2 xl:col-span-3">
            <EmptyState
              title="No stories match this filter"
              description="Try a broader status filter or remove some keywords. The inbox only shows stories that still require action."
            />
          </div>
        ) : (
          filteredStories.map((story, index) => (
            <button
              key={story.id}
              type="button"
              onClick={() => openStory(story)}
              className={cn(
                "rounded-[1.5rem] border p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/50",
                index === selectedIndex
                  ? "border-cyan-300/35 bg-cyan-300/[0.08] shadow-[0_16px_40px_rgba(34,211,238,0.12)]"
                  : "border-white/8 bg-white/[0.03] hover:-translate-y-0.5 hover:border-white/14 hover:bg-white/[0.05]",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-2">
                  <p className="text-[0.68rem] font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
                    Story #{story.id}
                  </p>
                  <h3 className="text-lg font-semibold leading-6 text-white">{story.title}</h3>
                </div>
                <StatusBadge tone={statusTone(story.status)}>{STATUS_LABELS[story.status]}</StatusBadge>
              </div>
              <div className="mt-4 flex flex-wrap gap-3 text-sm text-[var(--text-soft)]">
                <span>{story.author || "Unknown author"}</span>
                <span>Next: {STATUS_LABELS[story.status]}</span>
              </div>
              <div className="mt-5 flex items-center justify-between gap-3">
                <p className="text-sm text-[var(--text-soft)]">
                  {story.source_url
                    ? new URL(story.source_url).hostname.replace(/^www\./, "")
                    : "Local source"}
                </p>
                <span className="text-sm font-semibold text-cyan-100">Open</span>
              </div>
            </button>
          ))
        )}
      </div>
    </Panel>
  );
}
