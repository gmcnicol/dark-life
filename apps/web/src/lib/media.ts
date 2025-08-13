import type { CatalogImage } from "./catalog";

export function selectImage(
  images: (CatalogImage | null)[],
  index: number,
  image: CatalogImage,
): (CatalogImage | null)[] {
  const next = [...images];
  next[index] = image;
  return next;
}

export function bulkApply(
  images: (CatalogImage | null)[],
): (CatalogImage | null)[] {
  return images.map(() => images[0] ?? null);
}
