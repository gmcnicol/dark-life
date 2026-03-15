"use client";

import { useMemo, useState, useTransition } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Asset, Story, StoryPart } from "@/lib/stories";
import { createAssetBundle } from "@/lib/stories";
import { canManageMedia, STATUS_LABELS } from "@/lib/workflow";
import { ActionButton, Panel, SectionHeading, StatusBadge } from "./ui-surfaces";

export default function MediaSelector({
  story,
  parts,
  assets,
}: {
  story: Story;
  parts: StoryPart[];
  assets: Asset[];
}) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<number[]>(() =>
    assets.slice(0, Math.max(parts.length, 1)).map((asset) => asset.id),
  );
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const canSave = canManageMedia(story.status);

  const previewAssets = useMemo(
    () => selected.map((id) => assets.find((asset) => asset.id === id)).filter(Boolean) as Asset[],
    [assets, selected],
  );

  const toggleAsset = (id: number) => {
    if (!canSave) {
      return;
    }
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  const autoAssign = () => {
    if (!canSave) {
      return;
    }
    setSelected(assets.slice(0, Math.max(parts.length, 1)).map((asset) => asset.id));
  };

  const saveBundle = () => {
    startTransition(async () => {
      try {
        setError(null);
        await createAssetBundle(story.id, {
          name: "Primary bundle",
          asset_ids: selected,
        });
        await queryClient.invalidateQueries();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save bundle");
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
          <ActionButton onClick={autoAssign} tone="secondary" disabled={!canSave}>
            Apply best matches
          </ActionButton>
          <ActionButton onClick={saveBundle} disabled={isPending || selected.length === 0 || !canSave}>
            {isPending ? "Saving bundle…" : "Save bundle"}
          </ActionButton>
        </div>
        {error ? <StatusBadge tone="danger">{error}</StatusBadge> : null}
        {!canSave ? (
          <p className="text-sm text-[var(--text-soft)]">
            Media selection unlocks after approval and freezes once renders have been queued.
          </p>
        ) : null}
      </Panel>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_21rem]">
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {assets.map((asset) => {
            const selectedAsset = selected.includes(asset.id);
            const previewSrc = asset.local_path || asset.remote_url || "";
            return (
              <button
                key={asset.id}
                type="button"
                onClick={() => toggleAsset(asset.id)}
                disabled={!canSave}
                data-testid={selectedAsset ? `catalog-img-${asset.id}` : undefined}
                className={`overflow-hidden rounded-[1.6rem] border p-3 text-left transition ${
                  selectedAsset
                    ? "border-cyan-300/35 bg-cyan-300/[0.08]"
                    : "border-white/8 bg-white/[0.03] hover:border-white/14 hover:bg-white/[0.05]"
                } ${!canSave ? "cursor-not-allowed opacity-60" : ""}`}
              >
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
