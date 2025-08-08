const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(`API request failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}
