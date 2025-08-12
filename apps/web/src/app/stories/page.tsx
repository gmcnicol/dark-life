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
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(5);

  function showToast(toast: Toast) {
    setToast(toast);
    setTimeout(() => setToast(null), 3000);
  }

  const { data: stories, isLoading, error } = useQuery({
    queryKey: ["stories", { status, q, page, limit }],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (q) params.set("q", q);
      params.set("page", String(page));
      params.set("limit", String(limit));
      return apiFetch<Story[]>(`/api/stories?${params.toString()}`);
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      apiFetch<Story>("/api/stories", {
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
    mutationFn: (id: number) =>
      apiFetch(`/api/stories/${id}`, { method: "DELETE" }),
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
      <div className="flex gap-2 items-center">
        <input
          className="border px-2 py-1 rounded"
          placeholder="Search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
        />
        <select
          className="border px-2 py-1 rounded"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All</option>
          <option value="draft">Draft</option>
          <option value="approved">Approved</option>
          <option value="ready">Ready</option>
          <option value="rendered">Rendered</option>
          <option value="uploaded">Uploaded</option>
        </select>
        <select
          className="border px-2 py-1 rounded"
          value={limit}
          onChange={(e) => {
            setLimit(parseInt(e.target.value));
            setPage(1);
          }}
        >
          <option value={5}>5</option>
          <option value={10}>10</option>
          <option value={20}>20</option>
        </select>
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
      <div className="flex items-center gap-2">
        <button
          className="border px-2 py-1 rounded"
          disabled={page === 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          Prev
        </button>
        <span>Page {page}</span>
        <button
          className="border px-2 py-1 rounded"
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

