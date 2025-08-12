export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || "";
  const res = await fetch(`${base}${path}`, init);
  if (!res.ok) {
    throw new Error(`API request failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}
