"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import type { AssetBundle, PublishPlatformSettings, RenderPreset, Story } from "@/lib/stories";
import { createCompilation, createShortReleases } from "@/lib/stories";
import { STATUS_LABELS } from "@/lib/workflow";
import {
  ActionButton,
  HintPanel,
  PageActions,
  PageStatusBar,
  Panel,
  SectionHeading,
  StatusBadge,
  SurfaceRail,
} from "./ui-surfaces";

export default function EnqueueDialog({
  story,
  storyId,
  bundles,
  presets,
  publishPlatforms,
}: {
  story: Story;
  storyId: number;
  bundles: AssetBundle[];
  presets: RenderPreset[];
  publishPlatforms: PublishPlatformSettings;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [presetSlug, setPresetSlug] = useState("short-form");
  const [bundleId, setBundleId] = useState<number | null>(bundles[0]?.id ?? null);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(publishPlatforms.active_platforms);
  const [includeWeekly, setIncludeWeekly] = useState(publishPlatforms.active_platforms.includes("youtube"));
  const [isPending, startTransition] = useTransition();
  const activePlatforms = publishPlatforms.active_platforms;
  const queueEligibleStatus = story.status === "approved" || story.status === "media_ready";
  const hasBundle = bundles.length > 0;
  const canConfigureQueue = queueEligibleStatus && hasBundle;
  const youtubeAvailable = activePlatforms.includes("youtube");
  const youtubeSelected = selectedPlatforms.includes("youtube");
  const inactivePlatforms = useMemo(
    () => publishPlatforms.available_platforms.filter((platform) => !activePlatforms.includes(platform)),
    [activePlatforms, publishPlatforms.available_platforms],
  );
  const isCommitted =
    story.status === "queued" ||
    story.status === "rendering" ||
    story.status === "rendered" ||
    story.status === "publish_ready" ||
    story.status === "published";
  const selectedBundle = bundles.find((bundle) => bundle.id === bundleId) ?? bundles[0] ?? null;

  useEffect(() => {
    setSelectedPlatforms((current) => {
      const valid = current.filter((platform) => activePlatforms.includes(platform));
      return valid.length > 0 ? valid : activePlatforms;
    });
  }, [activePlatforms]);

  useEffect(() => {
    if (!youtubeAvailable || !youtubeSelected) {
      setIncludeWeekly(false);
    }
  }, [youtubeAvailable, youtubeSelected]);

  useEffect(() => {
    if (!selectedBundle) {
      setBundleId(null);
      return;
    }
    setBundleId((current) => (current && bundles.some((bundle) => bundle.id === current) ? current : selectedBundle.id));
  }, [bundles, selectedBundle]);

  const togglePlatform = (platform: string) => {
    if (!canConfigureQueue) {
      return;
    }
    setSelectedPlatforms((current) => {
      if (current.includes(platform)) {
        return current.length === 1 ? current : current.filter((item) => item !== platform);
      }
      return [...current, platform];
    });
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    startTransition(async () => {
      await createShortReleases(storyId, {
        platforms: selectedPlatforms,
        preset_slug: presetSlug,
        asset_bundle_id: bundleId,
      });
      if (includeWeekly && youtubeSelected) {
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
      <div className="space-y-4">
        <Panel className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <SectionHeading
              eyebrow="Render handoff"
              title="Queue renders"
              description="Lock the render preset, attach the chosen asset bundle, and let the system queue, schedule, and publish against the active cadence automatically."
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
        </Panel>

        <PageStatusBar>
          <StatusBadge tone="neutral">{STATUS_LABELS[story.status]}</StatusBadge>
          {!hasBundle ? <StatusBadge tone="warning">No asset bundle attached</StatusBadge> : null}
          {!queueEligibleStatus ? <StatusBadge tone="warning">Approval required before queueing</StatusBadge> : null}
          {isCommitted ? <StatusBadge tone="success">Already committed to downstream work</StatusBadge> : null}
        </PageStatusBar>

        <Panel className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2 text-sm text-white">
            <span className="block text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
              Render preset
            </span>
            <select
              value={presetSlug}
              onChange={(event) => setPresetSlug(event.target.value)}
              data-testid="preset-select"
              disabled={!canConfigureQueue}
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
              disabled={!canConfigureQueue || !hasBundle}
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
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">Delivery targets</p>
            <div className="flex flex-wrap gap-3">
              {activePlatforms.map((platform) => (
                <button
                  key={platform}
                  type="button"
                  onClick={() => togglePlatform(platform)}
                  disabled={!canConfigureQueue}
                  className={[
                    "rounded-full border px-4 py-2 text-sm font-semibold transition",
                    selectedPlatforms.includes(platform)
                      ? "border-cyan-300/35 bg-cyan-300/[0.12] text-cyan-50"
                      : "border-white/10 bg-white/[0.03] text-[var(--text-soft)]",
                    !canConfigureQueue && "cursor-not-allowed opacity-60",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                >
                  {platform === "youtube" ? "YouTube" : platform === "instagram" ? "Instagram" : "TikTok"}
                </button>
              ))}
              {inactivePlatforms.map((platform) => (
                <span key={platform} className="rounded-full border border-white/10 px-4 py-2 text-sm text-[var(--text-soft)]">
                  {(platform === "youtube" ? "YouTube" : platform === "instagram" ? "Instagram" : "TikTok")} disabled
                </span>
              ))}
            </div>
            <p className="text-sm text-[var(--text-soft)]">
              Queue now, then fine-tune individual publish times in the <Link to="/publish" className="text-cyan-100 underline decoration-white/20 underline-offset-4">publish queue</Link>. Default cadence now uses fixed daily short slots, with an optional Friday full-story YouTube compilation.
            </p>
          </div>

          <div className="rounded-[1.3rem] border border-white/8 bg-white/[0.03] px-4 py-4 text-sm text-[var(--text-soft)]">
            This handoff is fire-and-forget. Releases are pre-approved, assigned publish slots, and the publisher wakes up when each slot arrives.
          </div>

          <label className="flex items-center gap-3 rounded-[1.3rem] border border-white/8 bg-white/[0.03] px-4 py-4 text-sm text-white">
            <input
              type="checkbox"
              checked={includeWeekly}
              onChange={(event) => setIncludeWeekly(event.target.checked)}
              disabled={!canConfigureQueue || !youtubeSelected}
              data-testid="captions-checkbox"
            />
            Create a weekly full-story compilation for YouTube
          </label>
          {!youtubeAvailable ? (
            <p className="text-sm text-[var(--text-soft)]">
              Weekly compilation is unavailable while YouTube is inactive.
            </p>
          ) : !youtubeSelected ? (
            <p className="text-sm text-[var(--text-soft)]">
              Select YouTube above if you want the weekly compilation scheduled.
            </p>
          ) : null}

          {!hasBundle ? (
            <div className="rounded-[1.3rem] border border-amber-400/20 bg-amber-400/[0.08] px-4 py-4 text-sm text-amber-50">
              This story is not queue-ready yet because no asset bundle is attached. Finish media selection and queue it from there.
              <div className="mt-3">
                <Link
                  to={`/story/${storyId}/media`}
                  className="inline-flex rounded-full border border-amber-300/30 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/8"
                >
                  Open media stage
                </Link>
              </div>
            </div>
          ) : null}

          {story.status === "scripted" || story.status === "ingested" ? (
            <div className="rounded-[1.3rem] border border-white/8 bg-white/[0.03] px-4 py-4 text-sm text-[var(--text-soft)]">
              Queueing is premature for this story. Approve the script first, then lock media, then return here.
            </div>
          ) : null}

          {isCommitted ? (
            <div className="rounded-[1.3rem] border border-white/8 bg-white/[0.03] px-4 py-4 text-sm text-[var(--text-soft)]">
              This story has already moved past queue setup. Track render execution in <Link to={`/story/${storyId}/jobs`} className="text-cyan-100 underline decoration-white/20 underline-offset-4">Jobs</Link> or adjust publish timing in <Link to="/publish" className="text-cyan-100 underline decoration-white/20 underline-offset-4">Publish</Link>.
            </div>
          ) : null}
        </Panel>
      </div>

      <SurfaceRail>
        <HintPanel
          eyebrow="Primary action"
          title="Finalize queueing"
          description="This stage should feel like a final confirmation, not another edit surface. The action stays in the same rail used throughout the story workflow."
        >
          <PageActions>
            <ActionButton
              type="submit"
              disabled={
                isPending || !bundleId || !canConfigureQueue || selectedPlatforms.length === 0 || isCommitted
              }
            >
              {isPending ? "Queueing…" : "Queue and schedule"}
            </ActionButton>
            {!queueEligibleStatus ? (
              <p className="text-sm text-[var(--text-soft)]">
                Queue setup unlocks once the story reaches approval and has a locked bundle.
              </p>
            ) : selectedPlatforms.length === 0 ? (
              <p className="text-sm text-[var(--text-soft)]">
                Pick at least one delivery target before queueing.
              </p>
            ) : null}
          </PageActions>
        </HintPanel>

        <HintPanel
          eyebrow="Checklist"
          title="Before queueing"
          description="Keep final confirmation guidance separate from the form fields so operators do not have to hunt through the page."
        >
          <div className="space-y-3 text-sm text-[var(--text-soft)]">
            <p>1. Confirm the narration split feels stable.</p>
            <p>2. Confirm the active asset bundle matches the story mood.</p>
            <p>3. Confirm the preset matches the final destination.</p>
          </div>
        </HintPanel>
      </SurfaceRail>
    </form>
  );
}
