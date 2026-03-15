"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Story, StoryPart } from "@/lib/stories";
import { replaceStoryParts } from "@/lib/stories";

export default function SplitEditor({
  story,
  parts,
}: {
  story: Story;
  parts: StoryPart[];
}) {
  const router = useRouter();
  const [rows, setRows] = useState(() =>
    parts.length > 0 ? parts.map((part) => part.body_md) : [story.body_md || ""],
  );
  const [isPending, startTransition] = useTransition();

  const updateRow = (index: number, value: string) => {
    setRows((current) => current.map((row, i) => (i === index ? value : row)));
  };

  const addPart = () => setRows((current) => [...current, ""]);
  const removePart = (index: number) =>
    setRows((current) => current.filter((_, i) => i !== index));

  const handleSave = () => {
    startTransition(async () => {
      await replaceStoryParts(
        story.id,
        rows
          .map((body_md) => body_md.trim())
          .filter(Boolean)
          .map((body_md) => ({ body_md, approved: true })),
      );
      router.refresh();
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span data-testid="status" className="rounded-full bg-zinc-800 px-3 py-1 text-sm">
          Status: {story.status}
        </span>
        <button
          onClick={addPart}
          className="rounded-full border border-zinc-700 px-4 py-2 text-sm text-zinc-200"
        >
          Add Part
        </button>
      </div>
      <div className="space-y-4">
        {rows.map((row, index) => (
          <div key={index} className="rounded-3xl border border-zinc-800 bg-zinc-950/70 p-4">
            <div className="mb-2 flex items-center justify-between text-xs uppercase tracking-[0.25em] text-zinc-500">
              <span>Part {index + 1}</span>
              {rows.length > 1 ? (
                <button onClick={() => removePart(index)} className="text-red-300">
                  Remove
                </button>
              ) : null}
            </div>
            <textarea
              className="min-h-48 w-full rounded-2xl border border-zinc-800 bg-zinc-900 p-4 text-sm leading-7 text-zinc-100"
              value={row}
              onChange={(event) => updateRow(index, event.target.value)}
            />
            <p className="mt-2 text-xs text-zinc-500">
              Approx. {Math.max(1, Math.round(row.split(/\s+/).filter(Boolean).length / 2.6))} seconds
            </p>
          </div>
        ))}
      </div>
      <button
        onClick={handleSave}
        disabled={isPending}
        className="rounded-full bg-zinc-100 px-5 py-3 text-sm font-medium text-zinc-950"
      >
        Save Parts
      </button>
    </div>
  );
}
