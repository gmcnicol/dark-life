"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import type { AssetBundle, RenderPreset } from "@/lib/stories";
import { createCompilation, createShortReleases } from "@/lib/stories";

export default function EnqueueDialog({
  storyId,
  bundles,
  presets,
}: {
  storyId: number;
  bundles: AssetBundle[];
  presets: RenderPreset[];
}) {
  const router = useRouter();
  const [platforms, setPlatforms] = useState<string[]>(["youtube", "tiktok", "instagram"]);
  const [presetSlug, setPresetSlug] = useState("short-form");
  const [bundleId, setBundleId] = useState<number | null>(bundles[0]?.id ?? null);
  const [includeWeekly, setIncludeWeekly] = useState(true);
  const [isPending, startTransition] = useTransition();

  const togglePlatform = (platform: string) => {
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
      router.push(`/story/${storyId}/jobs`);
      router.refresh();
    });
  };

  return (
    <form onSubmit={submit} data-testid="enqueue-form" className="space-y-5 rounded-3xl border border-zinc-800 bg-zinc-950/70 p-5">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-zinc-200">
          <span className="block text-xs uppercase tracking-[0.25em] text-zinc-500">Preset</span>
          <select
            value={presetSlug}
            onChange={(event) => setPresetSlug(event.target.value)}
            data-testid="preset-select"
            className="w-full rounded-2xl border border-zinc-800 bg-zinc-900 px-3 py-3"
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
        <label className="space-y-2 text-sm text-zinc-200">
          <span className="block text-xs uppercase tracking-[0.25em] text-zinc-500">Asset Bundle</span>
          <select
            value={bundleId ?? ""}
            onChange={(event) => setBundleId(Number(event.target.value))}
            className="w-full rounded-2xl border border-zinc-800 bg-zinc-900 px-3 py-3"
          >
            {bundles.map((bundle) => (
              <option key={bundle.id} value={bundle.id}>
                {bundle.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="space-y-2">
        <p className="text-xs uppercase tracking-[0.25em] text-zinc-500">Platforms</p>
        <div className="flex flex-wrap gap-3">
          {["youtube", "tiktok", "instagram"].map((platform) => {
            const active = platforms.includes(platform);
            return (
              <button
                key={platform}
                type="button"
                onClick={() => togglePlatform(platform)}
                className={`rounded-full px-4 py-2 text-sm ${
                  active ? "bg-amber-300 text-zinc-950" : "border border-zinc-700 text-zinc-200"
                }`}
              >
                {platform}
              </button>
            );
          })}
        </div>
      </div>

      <label className="flex items-center gap-3 text-sm text-zinc-200">
        <input
          type="checkbox"
          checked={includeWeekly}
          onChange={(event) => setIncludeWeekly(event.target.checked)}
          data-testid="captions-checkbox"
        />
        Create weekly full-story compilation for YouTube
      </label>

      <button
        type="submit"
        disabled={isPending || !bundleId}
        className="rounded-full bg-zinc-100 px-5 py-3 text-sm font-medium text-zinc-950"
      >
        Queue Renders
      </button>
    </form>
  );
}
