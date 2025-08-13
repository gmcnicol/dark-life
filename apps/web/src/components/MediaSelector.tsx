"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Story } from "@/lib/stories";
import { updateStoryStatus } from "@/lib/stories";
import ImagePicker from "./ImagePicker";
import type { CatalogImage } from "@/lib/catalog";
import { selectImage, bulkApply } from "@/lib/media";

export default function MediaSelector({
  story,
  parts,
}: {
  story: Story;
  parts: string[];
}) {
  const router = useRouter();
  const [status, setStatus] = useState(story.status);
  const [images, setImages] = useState<(CatalogImage | null)[]>(
    () => Array(parts.length).fill(null),
  );

  const handleSelect = (i: number, img: CatalogImage) => {
    setImages((prev) => selectImage(prev, i, img));
  };

  const handleBulk = () => {
    setImages((prev) => bulkApply(prev));
  };

  const handleSave = async () => {
    await updateStoryStatus(story.id, "media_selected");
    setStatus("media_selected");
    router.refresh();
  };

  return (
    <div>
      <span data-testid="status">Status: {status}</span>
      {parts.map((p, i) => (
        <div key={i} className="mb-4">
          <p>{p}</p>
          {images[i]?.url && (
            <img src={images[i]!.url} alt="" className="mb-2" />
          )}
          <ImagePicker onSelect={(img) => handleSelect(i, img)} />
        </div>
      ))}
      <button onClick={handleBulk}>Apply to all</button>
      <button onClick={handleSave}>Save</button>
    </div>
  );
}
