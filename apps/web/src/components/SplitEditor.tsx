"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Story } from "@/lib/stories";
import { splitStory } from "@/lib/stories";
import {
  segmentSentences,
  splitSentences,
  estimateDuration,
} from "@/lib/split";

export default function SplitEditor({ story }: { story: Story }) {
  const router = useRouter();
  const [parts, setParts] = useState<string[][]>(() => {
    const sentences = segmentSentences(story.body_md || "");
    return splitSentences(sentences);
  });
  const [status, setStatus] = useState(story.status);

  const moveHandle = (index: number, dir: -1 | 1) => {
    setParts((prev) => {
      const left = prev[index];
      const right = prev[index + 1];
      if (!left || !right) return prev;
      if (dir === -1 && right.length > 0) {
        const sentence = right.shift()!;
        left.push(sentence);
      } else if (dir === 1 && left.length > 0) {
        const sentence = left.pop()!;
        right.unshift(sentence);
      }
      return [...prev];
    });
  };

  const onHandleKey = (i: number, e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft") moveHandle(i, -1);
    if (e.key === "ArrowRight") moveHandle(i, 1);
  };

  const onDrop = (i: number, e: React.DragEvent<HTMLDivElement>) => {
    const from = Number(e.dataTransfer.getData("text/plain"));
    if (isNaN(from)) return;
    if (from < i) {
      for (let x = from; x < i; x++) moveHandle(x, 1);
    } else if (from > i) {
      for (let x = from; x > i; x--) moveHandle(x - 1, -1);
    }
  };

  const handleSave = async () => {
    const texts = parts.map((p) => p.join(" ").trim());
    await splitStory(story.id, texts);
    setStatus("split");
    router.refresh();
  };

  return (
    <div>
      <span data-testid="status">Status: {status}</span>
      {parts.map((part, i) => {
        const words = part.join(" ").split(/\s+/).filter(Boolean).length;
        const est = estimateDuration(words);
        const warn = est < 50 || est > 70;
        return (
          <div key={i} className="mb-4">
            <p>{part.join(" ")}</p>
            <p className={warn ? "text-red-600" : undefined}>Est: {est} sec</p>
            {i < parts.length - 1 && (
              <div
                data-testid={`handle-${i}`}
                draggable
                onDragStart={(e) =>
                  e.dataTransfer.setData("text/plain", String(i))
                }
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => onDrop(i, e)}
                tabIndex={0}
                onKeyDown={(e) => onHandleKey(i, e)}
                style={{
                  height: 4,
                  background: "gray",
                  cursor: "col-resize",
                }}
              />
            )}
          </div>
        );
      })}
      <button onClick={handleSave}>Save</button>
    </div>
  );
}
