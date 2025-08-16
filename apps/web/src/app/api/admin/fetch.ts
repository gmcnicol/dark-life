import "server-only";

export async function adminApiFetch(path: string, init?: RequestInit) {
  const base = process.env.API_BASE_URL;
  if (!base) {
    throw new Error("API_BASE_URL is not set");
  }
  const headers = new Headers(init?.headers);
  const token = process.env.ADMIN_API_TOKEN;
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(`${base}${path}`, { ...init, headers });
}
