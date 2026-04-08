import { afterEach, describe, expect, it, vi } from "vitest";
import { adminFetch } from "./api";

describe("adminFetch", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps admin requests on the same-origin proxy path", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ jobs: [] }),
    } as Response);

    await adminFetch("/api/admin/reddit/incremental", { method: "POST" });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/admin/reddit/incremental",
      expect.objectContaining({ method: "POST", cache: "no-store" }),
    );
  });

  it("rejects paths outside the admin proxy", async () => {
    await expect(adminFetch("/stories")).rejects.toThrow(
      "adminFetch path must stay under '/api/admin'",
    );
  });

  it("surfaces JSON error details from the proxy", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => ({ detail: "Reddit retrieval failed" }),
    } as Response);

    await expect(adminFetch("/api/admin/reddit/incremental", { method: "POST" })).rejects.toThrow(
      "Reddit retrieval failed",
    );
  });
});
