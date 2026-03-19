"use client";

import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { MediaRef, Story, StoryPart } from "@/lib/stories";
import { createAssetBundle, indexStoryAssets } from "@/lib/stories";
import { canManageMedia, STATUS_LABELS } from "@/lib/workflow";
import { ActionButton, EmptyState, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

export default function MediaSelector({
  story,
  parts,
  assets,
}: {
  story: Story;
  parts: StoryPart[];
  assets: MediaRef[];
}) {
  const queryClient = useQueryClient();
  const gridRef = useRef<HTMLDivElement | null>(null);
  const [catalogAssets, setCatalogAssets] = useState<MediaRef[]>(assets);
  const [selected, setSelected] = useState<string[]>(() =>
    assets.slice(0, Math.max(parts.length, 1)).map((asset) => asset.key),
  );
  const [isPending, startTransition] = useTransition();
  const [isRefreshing, startRefreshTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fetchNotice, setFetchNotice] = useState<string | null>(null);
  const canSave = canManageMedia(story.status);

  useEffect(() => {
    setCatalogAssets(assets);
  }, [assets]);

  useEffect(() => {
    setSelected((current) => {
      if (catalogAssets.length === 0) {
        return [];
      }
      const validCurrent = current.filter((key) => catalogAssets.some((asset) => asset.key === key));
      if (validCurrent.length > 0) {
        return validCurrent;
      }
      return catalogAssets.slice(0, Math.max(parts.length, 1)).map((asset) => asset.key);
    });
  }, [catalogAssets, parts.length]);

  const previewAssets = useMemo(
    () => selected.map((key) => catalogAssets.find((asset) => asset.key === key)).filter(Boolean) as MediaRef[],
    [catalogAssets, selected],
  );

  const toggleAsset = (key: string) => {
    if (!canSave) {
      return;
    }
    setSelected((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    );
  };

  const autoAssign = () => {
    if (!canSave) {
      return;
    }
    setSelected(catalogAssets.slice(0, Math.max(parts.length, 1)).map((asset) => asset.key));
  };

  const saveBundle = () => {
    startTransition(async () => {
      try {
        setError(null);
        const fallbackAsset = previewAssets[0];
        if (fallbackAsset === undefined) {
          throw new Error("Select at least one asset before saving the bundle");
        }
        const partAssetMap = parts.map((part, index) => ({
          story_part_id: part.id,
          asset: previewAssets[index] ?? fallbackAsset,
        }));
        await createAssetBundle(story.id, {
          name: "Primary bundle",
          asset_refs: previewAssets,
          part_asset_map: partAssetMap,
        });
        await queryClient.invalidateQueries();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save bundle");
      }
    });
  };

  const refreshRemoteMatches = () => {
    startRefreshTransition(async () => {
      try {
        setError(null);
        setFetchNotice(null);
        const latestAssets = await indexStoryAssets(story.id);
        setCatalogAssets(latestAssets);
        setSelected(latestAssets.slice(0, Math.max(parts.length, 1)).map((asset) => asset.key));
        setFetchNotice(
          latestAssets.length > 0
            ? `Showing ${latestAssets.length} latest Pixabay matches for this story.`
            : "No current Pixabay matches for this story.",
        );
        queryClient.setQueryData(["story-assets", story.id], latestAssets);
        requestAnimationFrame(() => {
          gridRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch remote matches");
      }
    });
  };

  return (
    <div className="space-y-4">
      <Panel className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <SectionHeading
            eyebrow="Media assignment"
            title="Asset bundle"
            description="Choose the supporting visual set for each story section, then lock the bundle so the queue stage can render against a stable media package."
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

        <div className="flex flex-wrap items-center gap-3">
          <ActionButton onClick={refreshRemoteMatches} tone="secondary" disabled={isRefreshing}>
            {isRefreshing ? "Fetching Pixabay matches…" : "Fetch remote matches"}
          </ActionButton>
          <ActionButton onClick={autoAssign} tone="secondary" disabled={!canSave}>
            Apply best matches
          </ActionButton>
          <ActionButton onClick={saveBundle} disabled={isPending || selected.length === 0 || !canSave}>
            {isPending ? "Saving bundle…" : "Save bundle"}
          </ActionButton>
        </div>
        {error ? <StatusBadge tone="danger">{error}</StatusBadge> : null}
        {fetchNotice ? <StatusBadge tone="neutral">{fetchNotice}</StatusBadge> : null}
        {!canSave ? (
          <p className="text-sm text-[var(--text-soft)]">
            Media selection unlocks after approval and freezes once renders have been queued.
          </p>
        ) : null}
      </Panel>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_21rem]">
        <div ref={gridRef} className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {catalogAssets.length === 0 ? (
            <div className="md:col-span-2 2xl:col-span-3">
              <EmptyState
                title="No remote media matches yet"
                description="Fetch Pixabay matches for this story. If nothing returns, check the story keywords and make sure `PIXABAY_API_KEY` is configured for the API service."
                action={
                  <ActionButton onClick={refreshRemoteMatches} disabled={isRefreshing}>
                    {isRefreshing ? "Fetching…" : "Fetch Pixabay matches"}
                  </ActionButton>
                }
              />
            </div>
          ) : catalogAssets.map((asset) => {
            const selectedAsset = selected.includes(asset.key);
            const previewSrc = asset.remote_url || asset.local_path || "";
            return (
              <button
                key={asset.key}
                type="button"
                onClick={() => toggleAsset(asset.key)}
                disabled={!canSave}
                data-testid={selectedAsset ? `catalog-img-${asset.key}` : undefined}
                className={`relative overflow-hidden rounded-[1.6rem] border p-3 text-left transition ${
                  selectedAsset
                    ? "border-cyan-300/50 bg-cyan-300/[0.12] shadow-[0_18px_40px_rgba(34,211,238,0.14)]"
                    : "border-white/8 bg-white/[0.03] hover:border-white/14 hover:bg-white/[0.05]"
                } ${!canSave ? "cursor-not-allowed opacity-60" : ""}`}
              >
                <div className="absolute right-3 top-3 z-10">
                  {selectedAsset ? (
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-cyan-200/40 bg-cyan-300 text-slate-950 shadow-[0_10px_24px_rgba(34,211,238,0.35)]">
                      <svg
                        aria-hidden="true"
                        viewBox="0 0 16 16"
                        className="h-4 w-4 fill-none stroke-current stroke-[2.2]"
                      >
                        <path d="M3.5 8.5 6.5 11.5 12.5 4.5" />
                      </svg>
                    </span>
                  ) : (
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/12 bg-black/35 text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-white/70">
                      Pick
                    </span>
                  )}
                </div>
                <div className="aspect-[9/16] overflow-hidden rounded-[1.2rem] bg-black/20">
                  {asset.type === "video" ? (
                    <video src={previewSrc} muted className="h-full w-full object-cover" />
                  ) : (
                    <img src={previewSrc} alt="" className="h-full w-full object-cover" />
                  )}
                </div>
                <div className="mt-3 space-y-1">
                  <p className="text-sm font-semibold text-white">
                    {asset.orientation || asset.type}
                  </p>
                  <p className="text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                    {(asset.tags || []).slice(0, 4).join(" · ") || "library asset"}
                  </p>
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${
                    selectedAsset ? "text-cyan-100" : "text-white/45"
                  }`}>
                    {selectedAsset ? "Selected for bundle" : "Available"}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        <Panel className="h-fit space-y-4">
          <SectionHeading
            eyebrow="Preview"
            title="Part-to-media map"
            description="Check which selected asset will carry each part before locking the bundle."
          />
          {parts.map((part, index) => {
            const asset = previewAssets[index] || previewAssets[0];
            return (
              <div key={part.id} className="rounded-[1.3rem] border border-white/8 bg-white/[0.03] p-4">
                <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
                  Part {part.index}
                </p>
                <p className="mt-2 line-clamp-4 text-sm leading-6 text-white">
                  {part.script_text || part.body_md}
                </p>
                <p className="mt-3 text-xs uppercase tracking-[0.18em] text-[var(--muted)]">
                  {asset
                    ? `${asset.type} · ${(asset.tags || []).slice(0, 4).join(", ")}`
                    : "No media selected"}
                </p>
              </div>
            );
          })}
        </Panel>
      </section>
    </div>
  );
}
