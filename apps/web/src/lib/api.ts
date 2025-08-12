export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = path.startsWith("/") ? `/api${path}` : `/api/${path}`;
  const res = await fetch(url, init);
  if (!res.ok) {
    throw new Error(`API request failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}
