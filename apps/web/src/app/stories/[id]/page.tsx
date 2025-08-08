"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { marked } from "marked";
import ImagesTab from "./images-tab";

interface Story {
  id: string;
  title: string;
  body_md: string;
  status: "draft" | "approved";
}

interface Asset {
  id: string;
  selected: boolean;
}

interface Job {
  id: string;
  status: string;
}

type Toast = {
  type: "success" | "error";
  message: string;
  link?: string;
  linkText?: string;
};

export default function StoryEditorPage({
  params,
}: {
  params: { id: string };
}) {
  const { id } = params;
  const [form, setForm] = useState<Story | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const isInitial = useRef(true);
  const [tab, setTab] = useState<"content" | "images">("content");
  const queryClient = useQueryClient();

  const { data: images } = useQuery({
    queryKey: ["images", id],
    queryFn: () => apiFetch<Asset[]>(`/stories/${id}/images`),
  });

  const selectedCount = images?.filter((img) => img.selected).length ?? 0;

  function showToast(toast: Toast) {
    setToast(toast);
    setTimeout(() => setToast(null), 3000);
  }

  const { data, isLoading } = useQuery({
    queryKey: ["story", id],
    queryFn: () => apiFetch<Story>(`/stories/${id}`),
  });

  useEffect(() => {
    if (data) {
      setForm(data);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: (patch: Partial<Story>) =>
      apiFetch<Story>(`/stories/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      }),
    onMutate: async (patch) => {
      await queryClient.cancelQueries({ queryKey: ["story", id] });
      const previous = queryClient.getQueryData<Story>(["story", id]);
      if (previous) {
        queryClient.setQueryData<Story>(["story", id], {
          ...previous,
          ...patch,
        });
      }
      return { previous };
    },
    onError: (err: unknown, _patch, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(["story", id], ctx.previous);
      }
      showToast({ type: "error", message: (err as Error).message });
    },
    onSuccess: () => showToast({ type: "success", message: "Saved" }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["story", id] }),
  });

  const enqueueMutation = useMutation({
    mutationFn: () =>
      apiFetch<Job>(`/stories/${id}/enqueue-render`, { method: "POST" }),
    onSuccess: (job) =>
      showToast({
        type: "success",
        message: `Job ${job.status}`,
        link: "/jobs",
        linkText: "View jobs",
      }),
    onError: (err: unknown) =>
      showToast({ type: "error", message: (err as Error).message }),
  });

  useEffect(() => {
    if (!form) return;
    if (isInitial.current) {
      isInitial.current = false;
      return;
    }
    const timer = setTimeout(() => {
      mutation.mutate({
        title: form.title,
        body_md: form.body_md,
        status: form.status,
      });
    }, 1000);
    return () => clearTimeout(timer);
  }, [form, mutation]);

  const preview = useMemo(() => marked.parse(form?.body_md ?? ""), [form?.body_md]);

  useEffect(() => {
    function handleShortcut(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (form) {
          mutation.mutate({
            title: form.title,
            body_md: form.body_md,
            status: form.status,
          });
        }
      }
      if (e.key === "a" || e.key === "A") {
        e.preventDefault();
        setForm((f) => f && { ...f, status: "approved" });
        mutation.mutate({ status: "approved" });
      }
      if (e.key === "r" || e.key === "R") {
        e.preventDefault();
        enqueueMutation.mutate();
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [form, mutation, enqueueMutation]);

  if (isLoading || !form) {
    return (
      <div className="p-6 space-y-4 animate-pulse">
        <div className="h-8 bg-neutral-800 rounded w-1/3" />
        <div className="h-6 bg-neutral-800 rounded w-24" />
        <div className="h-96 bg-neutral-800 rounded" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {toast && (
        <div
          className={`fixed top-4 right-4 px-4 py-2 rounded text-white shadow ${
            toast.type === "success" ? "bg-green-600" : "bg-red-600"
          }`}
        >
          {toast.message}
          {toast.link && (
            <a href={toast.link} className="underline ml-2">
              {toast.linkText ?? "Link"}
            </a>
          )}
        </div>
      )}
      <div className="flex gap-4 border-b border-neutral-800 pb-2">
        <button
          className={`px-3 py-1 ${
            tab === "content" ? "border-b-2 border-white" : "text-gray-500"
          }`}
          onClick={() => setTab("content")}
        >
          Content
        </button>
        <button
          className={`px-3 py-1 ${
            tab === "images" ? "border-b-2 border-white" : "text-gray-500"
          }`}
          onClick={() => setTab("images")}
        >
          Images
        </button>
      </div>
      <button
        className="bg-blue-600 hover:bg-blue-500 px-3 py-1 rounded text-white disabled:opacity-50"
        disabled={
          form.status !== "approved" || selectedCount === 0 || enqueueMutation.isLoading
        }
        onClick={() => enqueueMutation.mutate()}
      >
        Queue for render
      </button>
      {tab === "content" && (
        <>
          <input
            type="text"
            className="border border-neutral-700 bg-neutral-900 p-2 w-full rounded"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <div>
            <label className="mr-2">Status:</label>
            <select
              className="border border-neutral-700 bg-neutral-900 rounded p-1"
              value={form.status}
              onChange={(e) =>
                setForm({ ...form, status: e.target.value as Story["status"] })
              }
            >
              <option value="draft">Draft</option>
              <option value="approved">Approved</option>
            </select>
          </div>
          <div className="flex gap-4">
            <textarea
              className="w-1/2 border border-neutral-700 bg-neutral-900 p-2 rounded h-96"
              value={form.body_md}
              onChange={(e) => setForm({ ...form, body_md: e.target.value })}
            />
            <div
              className="w-1/2 border border-neutral-700 p-2 rounded h-96 overflow-auto"
              dangerouslySetInnerHTML={{ __html: preview }}
            />
          </div>
        </>
      )}
      {tab === "images" && <ImagesTab storyId={id} />}
    </div>
  );
}

