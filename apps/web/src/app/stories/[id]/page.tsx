"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
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

  const { data: images } = useQuery({
    queryKey: ["images", id],
    queryFn: () => apiFetch<Asset[]>(`/stories/${id}/images`),
  });

  const selectedCount = images?.filter((img) => img.selected).length ?? 0;

  function showToast(toast: Toast) {
    setToast(toast);
    setTimeout(() => setToast(null), 3000);
  }

  const { data } = useQuery({
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
    onSuccess: () => showToast({ type: "success", message: "Saved" }),
    onError: (err: unknown) =>
      showToast({ type: "error", message: (err as Error).message }),
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

  if (!form) {
    return <p className="p-4">Loading...</p>;
  }

  return (
    <div className="p-4 space-y-4">
      {toast && (
        <div
          className={`fixed top-4 right-4 px-4 py-2 rounded text-white ${
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
      <div className="flex gap-4 border-b pb-2">
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
        className="border px-3 py-1 rounded"
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
            className="border p-2 w-full rounded"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <div>
            <label className="mr-2">Status:</label>
            <select
              className="border rounded p-1"
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
              className="w-1/2 border p-2 rounded h-96"
              value={form.body_md}
              onChange={(e) => setForm({ ...form, body_md: e.target.value })}
            />
            <div
              className="w-1/2 border p-2 rounded h-96 overflow-auto"
              dangerouslySetInnerHTML={{ __html: preview }}
            />
          </div>
        </>
      )}
      {tab === "images" && <ImagesTab storyId={id} />}
    </div>
  );
}

