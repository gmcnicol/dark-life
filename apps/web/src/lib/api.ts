export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  if (!path.startsWith("/")) {
    throw new Error("apiFetch path must start with '/'");
  }
  const base =
    (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "/api";
  const url = base.startsWith("http") ? `${base}${path}` : `${base}${path}`;
  const res = await fetch(url, {
    ...init,
    cache: init?.cache ?? "no-store",
  });
  if (!res.ok) {
    throw new Error(`API request failed with ${res.status}`);
  }
  return (await res.json()) as T;
}
