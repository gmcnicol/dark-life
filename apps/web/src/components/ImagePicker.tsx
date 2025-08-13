"use client";
import { useEffect, useState } from "react";
import type { CatalogImage } from "@/lib/catalog";
import { fetchCatalog } from "@/lib/catalog";

interface Props {
  onSelect(image: CatalogImage): void;
}

export default function ImagePicker({ onSelect }: Props) {
  const [tab, setTab] = useState<"catalog" | "url" | "upload">("catalog");
  const [images, setImages] = useState<CatalogImage[]>([]);
  const [url, setUrl] = useState("");
  const [attr, setAttr] = useState("");

  useEffect(() => {
    fetchCatalog().then(setImages).catch(() => setImages([]));
  }, []);

  const select = (img: CatalogImage) => {
    onSelect(img);
  };

  return (
    <div>
      <div className="mb-2 space-x-2">
        <button onClick={() => setTab("catalog")}>Catalog</button>
        <button onClick={() => setTab("url")}>URL</button>
        <button onClick={() => setTab("upload")}>Upload</button>
      </div>
      {tab === "catalog" && (
        <div className="grid grid-cols-3 gap-2 max-h-60 overflow-auto">
          {images.map((img, i) => (
            <button
              type="button"
              key={i}
              data-testid={`catalog-img-${i}`}
              className="relative"
              onClick={() => select(img)}
            >
              <img src={img.url} alt="" loading="lazy" />
              {img.nsfw && (
                <span className="absolute top-1 left-1 bg-red-600 text-white text-xs px-1">
                  NSFW
                </span>
              )}
              {img.attribution && (
                <span className="absolute bottom-1 left-1 bg-black/50 text-white text-xs px-1">
                  {img.attribution}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
      {tab === "url" && (
        <div className="space-y-2">
          <input
            type="text"
            placeholder="Image URL"
            className="border p-1"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <input
            type="text"
            placeholder="Attribution"
            className="border p-1"
            value={attr}
            onChange={(e) => setAttr(e.target.value)}
          />
          <button
            onClick={() =>
              url && select({ url, attribution: attr || undefined })
            }
          >
            Add
          </button>
        </div>
      )}
      {tab === "upload" && (
        <div className="space-y-2">
          <input
            type="file"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                const local = URL.createObjectURL(file);
                select({ url: local, attribution: attr || undefined });
              }
            }}
          />
          <input
            type="text"
            placeholder="Attribution"
            className="border p-1"
            value={attr}
            onChange={(e) => setAttr(e.target.value)}
          />
        </div>
      )}
    </div>
  );
}
