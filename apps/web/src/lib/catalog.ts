import { apiFetch } from "./api";
import type { Asset } from "./stories";

export type CatalogImage = Asset;

export async function fetchCatalog(): Promise<CatalogImage[]> {
  return apiFetch<CatalogImage[]>("/catalog");
}
