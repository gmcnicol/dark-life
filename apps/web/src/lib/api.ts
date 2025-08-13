export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  const token = process.env.ADMIN_API_TOKEN;
  const headers = new Headers(init?.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(`${baseUrl}${path}`, { ...init, headers });
  if (!res.ok) {
    throw new Error(`API request failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}
