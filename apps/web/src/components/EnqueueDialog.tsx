"use client";

import { useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import type { AssetBundle, RenderPreset, Story } from "@/lib/stories";
import { createCompilation, createShortReleases } from "@/lib/stories";
import { canQueueRenders, STATUS_LABELS } from "@/lib/workflow";
import { ActionButton, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

export default function EnqueueDialog({
  story,
  storyId,
  bundles,
  presets,
}: {
  story: Story;
  storyId: number;
  bundles: AssetBundle[];
  presets: RenderPreset[];
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [platforms, setPlatforms] = useState<string[]>(["youtube", "tiktok", "instagram"]);
  const [presetSlug, setPresetSlug] = useState("short-form");
  const [bundleId, setBundleId] = useState<number | null>(bundles[0]?.id ?? null);
  const [includeWeekly, setIncludeWeekly] = useState(true);
  const [isPending, startTransition] = useTransition();
  const canQueue = canQueueRenders(story.status);

  const togglePlatform = (platform: string) => {
    if (!canQueue) {
      return;
    }
    setPlatforms((current) =>
      current.includes(platform)
        ? current.filter((value) => value !== platform)
        : [...current, platform],
    );
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    startTransition(async () => {
      await createShortReleases(storyId, {
        platforms,
        preset_slug: presetSlug,
        asset_bundle_id: bundleId,
      });
      if (includeWeekly) {
        await createCompilation(storyId, {
          preset_slug: "weekly-full",
          platforms: ["youtube"],
        });
      }
      await queryClient.invalidateQueries();
      navigate(`/story/${storyId}/jobs`);
    });
  };

  return (
    <form onSubmit={submit} data-testid="enqueue-form" className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_19rem]">
      <Panel className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <SectionHeading
            eyebrow="Render handoff"
            title="Queue renders"
            description="Lock the render preset, attach the chosen asset bundle, and pick the delivery platforms before the story enters the worker queue."
          />
          <div className="space-y-2 text-right">
            <span data-testid="status" className="inline-flex rounded-full border border-white/10 px-3 py-1.5 text-sm font-semibold text-white">
              Status: {story.status}
            </span>
            <div>
              <StatusBadge tone="neutral">{STATUS_LABELS[story.status]}</StatusBadge>
            </div>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm text-white">
            <span className="block text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
              Render preset
            </span>
            <select
              value={presetSlug}
              onChange={(event) => setPresetSlug(event.target.value)}
              data-testid="preset-select"
              disabled={!canQueue}
              className="w-full rounded-[1.2rem] border border-white/10 bg-black/20 px-4 py-3 outline-none focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
            >
              {presets
                .filter((preset) => preset.variant === "short")
                .map((preset) => (
                  <option key={preset.id} value={preset.slug}>
                    {preset.name}
                  </option>
                ))}
            </select>
          </label>
          <label className="space-y-2 text-sm text-white">
            <span className="block text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
              Asset bundle
            </span>
            <select
              value={bundleId ?? ""}
              onChange={(event) => setBundleId(Number(event.target.value))}
              disabled={!canQueue}
              className="w-full rounded-[1.2rem] border border-white/10 bg-black/20 px-4 py-3 outline-none focus:border-cyan-300/40 focus:ring-2 focus:ring-cyan-300/20"
            >
              {bundles.map((bundle) => (
                <option key={bundle.id} value={bundle.id}>
                  {bundle.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="space-y-3">
          <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
            Platforms
          </p>
          <div className="flex flex-wrap gap-3">
            {["youtube", "tiktok", "instagram"].map((platform) => {
              const active = platforms.includes(platform);
              return (
                <button
                  key={platform}
                  type="button"
                  onClick={() => togglePlatform(platform)}
                  disabled={!canQueue}
                  className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
                    active
                      ? "border-cyan-300/35 bg-cyan-300/[0.12] text-cyan-50"
                      : "border-white/10 text-[var(--text-soft)]"
                  }`}
                >
                  {platform}
                </button>
              );
            })}
          </div>
        </div>

        <label className="flex items-center gap-3 rounded-[1.3rem] border border-white/8 bg-white/[0.03] px-4 py-4 text-sm text-white">
          <input
            type="checkbox"
            checked={includeWeekly}
            onChange={(event) => setIncludeWeekly(event.target.checked)}
            disabled={!canQueue}
            data-testid="captions-checkbox"
          />
          Create a weekly full-story compilation for YouTube
        </label>

        <div className="flex flex-wrap items-center gap-3">
          <ActionButton type="submit" disabled={isPending || !bundleId || !canQueue}>
            {isPending ? "Queueing…" : "Queue renders"}
          </ActionButton>
          {!canQueue ? (
            <p className="text-sm text-[var(--text-soft)]">
              Queueing unlocks only when the story is media-ready.
            </p>
          ) : null}
        </div>
      </Panel>

      <Panel className="h-fit space-y-4">
        <SectionHeading
          eyebrow="Checklist"
          title="Before queueing"
          description="This stage should feel like a final confirmation, not another edit surface."
        />
        <div className="space-y-3 text-sm text-[var(--text-soft)]">
          <p>1. Confirm the narration split feels stable.</p>
          <p>2. Confirm the active asset bundle matches the story mood.</p>
          <p>3. Confirm the preset matches the final destination.</p>
        </div>
      </Panel>
    </form>
  );
}
