"use client";

import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

interface Story {
  id: number;
  title: string;
}

type Toast = { type: "success" | "error"; message: string };

export default function StoriesPage() {
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<Toast | null>(null);

  function showToast(toast: Toast) {
    setToast(toast);
    setTimeout(() => setToast(null), 3000);
  }

  const { data: stories, isLoading, error } = useQuery({
    queryKey: ["stories"],
    queryFn: () => apiFetch<Story[]>("/stories"),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<Story>("/stories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "Untitled story" }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stories"] });
      showToast({ type: "success", message: "Story created" });
    },
    onError: (err: unknown) =>
      showToast({ type: "error", message: (err as Error).message }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiFetch(`/stories/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["stories"] });
      showToast({ type: "success", message: "Story deleted" });
    },
    onError: (err: unknown) =>
      showToast({ type: "error", message: (err as Error).message }),
  });

  return (
    <div className="p-4 space-y-4">
      {toast && (
        <div
          className={`fixed top-4 right-4 px-4 py-2 rounded text-white ${
            toast.type === "success" ? "bg-green-600" : "bg-red-600"
          }`}
        >
          {toast.message}
        </div>
      )}
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold">Stories</h1>
        <button
          className="border px-3 py-1 rounded"
          onClick={() => createMutation.mutate()}
        >
          New Story
        </button>
      </div>
      {isLoading && <p>Loading...</p>}
      {error && <p className="text-red-500">Failed to load stories</p>}
      <ul className="space-y-2">
        {stories?.map((story) => (
          <li
            key={story.id}
            className="flex justify-between items-center border p-2 rounded"
          >
            <Link href={`/stories/${story.id}`} className="underline">
              {story.title}
            </Link>
            <button
              className="text-sm text-red-600"
              onClick={() => deleteMutation.mutate(story.id)}
            >
              Delete
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

