"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import Image from "next/image";
import { apiFetch } from "@/lib/api";

interface Asset {
  id: number;
  remote_url: string;
  selected: boolean;
  rank: number;
}

export default function ImagesTab({ storyId }: { storyId: string }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["images", storyId],
    queryFn: () => apiFetch<Asset[]>(`/api/stories/${storyId}/images`),
  });

  const [images, setImages] = useState<Asset[]>([]);
  useEffect(() => {
    if (data) setImages(data);
  }, [data]);

  const fetchMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/api/stories/${storyId}/fetch-images`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["images", storyId] }),
  });

  const patchMutation = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<Asset> }) =>
      apiFetch(`/api/stories/${storyId}/images/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      }),
    onMutate: async ({ id, patch }) => {
      await queryClient.cancelQueries({ queryKey: ["images", storyId] });
      const previous = queryClient.getQueryData<Asset[]>(["images", storyId]);
      if (previous) {
        queryClient.setQueryData<Asset[]>(["images", storyId], (
          prev = [],
        ) => prev.map((img) => (img.id === id ? { ...img, ...patch } : img)));
      }
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) {
        queryClient.setQueryData(["images", storyId], ctx.previous);
      }
    },
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["images", storyId] }),
  });

  function toggleSelected(index: number) {
    const img = images[index];
    const updated = [...images];
    updated[index] = { ...img, selected: !img.selected };
    setImages(updated);
    patchMutation.mutate({ id: img.id, patch: { selected: !img.selected } });
  }

  function handleDragStart(
    e: React.DragEvent<HTMLDivElement>,
    index: number,
  ) {
    e.dataTransfer.setData("text/plain", index.toString());
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>, index: number) {
    e.preventDefault();
    const from = Number(e.dataTransfer.getData("text/plain"));
    if (isNaN(from)) return;
    const updated = [...images];
    const [moved] = updated.splice(from, 1);
    updated.splice(index, 0, moved);
    const withRank = updated.map((img, i) => ({ ...img, rank: i }));
    setImages(withRank);
    withRank.forEach((img, i) => {
      if (images[i]?.id !== img.id) {
        patchMutation.mutate({ id: img.id, patch: { rank: i } });
      }
    });
  }

  return (
    <div className="space-y-6">
      <button
        className="bg-blue-600 hover:bg-blue-500 px-3 py-1 rounded text-white disabled:opacity-50"
        onClick={() => fetchMutation.mutate()}
        disabled={fetchMutation.isLoading}
      >
        Auto-fetch images
      </button>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {(isLoading || fetchMutation.isLoading) &&
          Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-40 bg-neutral-800 animate-pulse rounded" />
          ))}
        {!isLoading &&
          images.map((img, index) => (
            <div
              key={img.id}
              className={`relative border border-neutral-700 rounded overflow-hidden cursor-pointer ${
                img.selected ? "ring-2 ring-blue-500" : ""
              }`}
              draggable
              onDragStart={(e) => handleDragStart(e, index)}
              onDragOver={handleDragOver}
              onDrop={(e) => handleDrop(e, index)}
              onClick={() => toggleSelected(index)}
            >
              <Image
                src={img.remote_url}
                alt=""
                width={160}
                height={160}
                className="w-full h-40 object-cover"
                sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
              />
              {img.selected && (
                <span className="absolute top-1 left-1 bg-blue-500 text-white text-xs px-1 rounded">
                  Selected
                </span>
              )}
            </div>
          ))}
      </div>
    </div>
  );
}

