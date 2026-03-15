"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Asset, Story, StoryPart } from "@/lib/stories";
import { createAssetBundle } from "@/lib/stories";

export default function MediaSelector({
  story,
  parts,
  assets,
}: {
  story: Story;
  parts: StoryPart[];
  assets: Asset[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<number[]>(() =>
    assets.slice(0, Math.max(parts.length, 1)).map((asset) => asset.id),
  );
  const [isPending, startTransition] = useTransition();

  const previewAssets = useMemo(
    () => selected.map((id) => assets.find((asset) => asset.id === id)).filter(Boolean) as Asset[],
    [assets, selected],
  );

  const toggleAsset = (id: number) => {
    setSelected((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  };

  const autoAssign = () => {
    setSelected(assets.slice(0, Math.max(parts.length, 1)).map((asset) => asset.id));
  };

  const saveBundle = () => {
    startTransition(async () => {
      await createAssetBundle(story.id, {
        name: "Primary bundle",
        asset_ids: selected,
      });
      router.refresh();
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <span data-testid="status" className="rounded-full bg-zinc-800 px-3 py-1 text-sm">
          Status: {story.status}
        </span>
        <button
          onClick={autoAssign}
          className="rounded-full border border-zinc-700 px-4 py-2 text-sm text-zinc-200"
        >
          Apply Best Matches
        </button>
        <button
          onClick={saveBundle}
          disabled={isPending || selected.length === 0}
          className="rounded-full bg-zinc-100 px-4 py-2 text-sm font-medium text-zinc-950"
        >
          Save Bundle
        </button>
      </div>

      <section className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {assets.map((asset) => {
            const selectedAsset = selected.includes(asset.id);
            const previewSrc = asset.local_path || asset.remote_url || "";
            return (
              <button
                key={asset.id}
                type="button"
                onClick={() => toggleAsset(asset.id)}
                data-testid={selectedAsset ? `catalog-img-${asset.id}` : undefined}
                className={`overflow-hidden rounded-3xl border p-3 text-left transition ${
                  selectedAsset
                    ? "border-amber-300 bg-amber-100/10"
                    : "border-zinc-800 bg-zinc-950/70"
                }`}
              >
                <div className="aspect-[9/16] overflow-hidden rounded-2xl bg-zinc-900">
                  {asset.type === "video" ? (
                    <video src={previewSrc} muted className="h-full w-full object-cover" />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={previewSrc} alt="" className="h-full w-full object-cover" />
                  )}
                </div>
                <div className="mt-3 space-y-1">
                  <p className="text-sm font-medium text-zinc-100">
                    {asset.orientation || asset.type}
                  </p>
                  <p className="text-xs text-zinc-400">
                    {(asset.tags || []).slice(0, 4).join(" · ") || "local library"}
                  </p>
                </div>
              </button>
            );
          })}
        </div>

        <aside className="space-y-4 rounded-3xl border border-zinc-800 bg-zinc-950/70 p-4">
          <p className="text-xs uppercase tracking-[0.3em] text-zinc-500">Bundle Preview</p>
          {parts.map((part, index) => {
            const asset = previewAssets[index] || previewAssets[0];
            return (
              <div key={part.id} className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
                <p className="mb-2 text-xs uppercase tracking-[0.25em] text-zinc-500">
                  Part {part.index}
                </p>
                <p className="mb-3 line-clamp-4 text-sm leading-6 text-zinc-200">
                  {part.script_text || part.body_md}
                </p>
                <p className="text-xs text-zinc-500">
                  {asset
                    ? `${asset.type} · ${(asset.tags || []).slice(0, 4).join(", ")}`
                    : "No media selected"}
                </p>
              </div>
            );
          })}
        </aside>
      </section>
    </div>
  );
}
