export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  if (!path.startsWith("/")) {
    throw new Error("apiFetch path must start with '/'");
  }
  const url =
    typeof window === "undefined"
      ? `http://localhost:3000/api${path}`
      : `/api${path}`;
  const res = await fetch(url, init);
  if (!res.ok) {
    throw new Error(`API request failed with ${res.status}`);
  }
  return (await res.json()) as T;
}
