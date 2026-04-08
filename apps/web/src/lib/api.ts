async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    cache: init?.cache ?? "no-store",
  });
  if (!res.ok) {
    let message = `API request failed with ${res.status}`;
    try {
      const payload = await res.json() as { detail?: string; error?: string; message?: string };
      message = payload.detail || payload.error || payload.message || message;
    } catch {
      // Ignore non-JSON error responses and fall back to the status message.
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  if (!path.startsWith("/")) {
    throw new Error("apiFetch path must start with '/'");
  }
  const base =
    (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "/api";
  const url = base.startsWith("http") ? `${base}${path}` : `${base}${path}`;
  return jsonFetch<T>(url, init);
}

export async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  if (!path.startsWith("/api/admin/") && path !== "/api/admin") {
    throw new Error("adminFetch path must stay under '/api/admin'");
  }
  return jsonFetch<T>(path, init);
}
