"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import Image from "next/image";
import { apiFetch } from "@/lib/api";

interface Asset {
  id: string;
  remote_url: string;
  selected: boolean;
  rank: number;
}

export default function ImagesTab({ storyId }: { storyId: string }) {
  const { data, refetch } = useQuery({
    queryKey: ["images", storyId],
    queryFn: () => apiFetch<Asset[]>(`/stories/${storyId}/images`),
  });

  const [images, setImages] = useState<Asset[]>([]);
  useEffect(() => {
    if (data) setImages(data);
  }, [data]);

  const fetchMutation = useMutation({
    mutationFn: () =>
      apiFetch(`/stories/${storyId}/fetch-images`, { method: "POST" }),
    onSuccess: () => refetch(),
  });

  const patchMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<Asset> }) =>
      apiFetch(`/stories/${storyId}/images/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      }),
    onSuccess: () => refetch(),
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
    setImages(updated);
    updated.forEach((img, i) => {
      patchMutation.mutate({ id: img.id, patch: { rank: i } });
    });
  }

  return (
    <div className="space-y-4">
      <button
        className="border px-3 py-1 rounded"
        onClick={() => fetchMutation.mutate()}
        disabled={fetchMutation.isLoading}
      >
        Auto-fetch images
      </button>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {images.map((img, index) => (
          <div
            key={img.id}
            className={`relative border ${img.selected ? "ring-2 ring-blue-500" : ""}`}
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

