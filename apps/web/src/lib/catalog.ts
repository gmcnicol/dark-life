import { z } from "zod";

export const CatalogImageSchema = z.object({
  url: z.string(),
  nsfw: z.boolean().optional(),
  attribution: z.string().optional(),
});

export type CatalogImage = z.infer<typeof CatalogImageSchema>;

export async function fetchCatalog(): Promise<CatalogImage[]> {
  const res = await fetch("/api/catalog");
  if (!res.ok) {
    throw new Error("Failed to fetch catalog");
  }
  const data = await res.json();
  return z.array(CatalogImageSchema).parse(data);
}
