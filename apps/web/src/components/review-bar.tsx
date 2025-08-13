"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import type { Story } from "@/lib/stories";
import { updateStoryStatus } from "@/lib/stories";
import { optimisticUpdate } from "@/lib/optimistic";

export default function ReviewBar({ story }: { story: Story }) {
  const router = useRouter();
  const [status, setStatus] = useState(story.status);
  const [notes, setNotes] = useState("");

  const changeStatus = async (next: string) => {
    await optimisticUpdate(status, setStatus, next, () =>
      updateStoryStatus(story.id, next, notes),
    );
    router.refresh();
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "a" || e.key === "A") {
        changeStatus("approved");
      } else if (e.key === "r" || e.key === "R") {
        changeStatus("rejected");
      } else if (e.key === "s" || e.key === "S") {
        changeStatus("pending");
      } else if (e.key === "[") {
        router.back();
      } else if (e.key === "]") {
        router.push("/inbox");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [changeStatus, router]);

  return (
    <div>
      <span data-testid="status">Status: {status}</span>
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Notes"
      />
      <button onClick={() => changeStatus("approved")}>Approve</button>
      <button onClick={() => changeStatus("rejected")}>Reject</button>
      <button onClick={() => changeStatus("pending")}>Skip</button>
    </div>
  );
}
