"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { enqueueStory } from "@/lib/jobs";

export default function EnqueueDialog({ storyId }: { storyId: number }) {
  const router = useRouter();
  const [preset, setPreset] = useState("default");
  const [captions, setCaptions] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    await enqueueStory(storyId, preset, captions);
    router.push(`/story/${storyId}/jobs`);
  };

  return (
    <form onSubmit={submit} data-testid="enqueue-form">
      <label>
        Preset
        <select
          value={preset}
          onChange={(e) => setPreset(e.target.value)}
          data-testid="preset-select"
        >
          <option value="default">default</option>
        </select>
      </label>
      <label>
        <input
          type="checkbox"
          checked={captions}
          onChange={(e) => setCaptions(e.target.checked)}
          data-testid="captions-checkbox"
        />
        Captions
      </label>
      <button type="submit">Enqueue</button>
    </form>
  );
}
