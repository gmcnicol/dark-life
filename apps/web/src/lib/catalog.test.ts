import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchCatalog } from "./catalog";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchCatalog", () => {
  it("returns images from the API response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: 1,
            type: "image",
            local_path: "data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA==",
          },
          {
            id: 2,
            type: "image",
            local_path: "data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA==",
          },
        ]),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    const images = await fetchCatalog();
    expect(images).toHaveLength(2);
    expect(images[0]!.local_path).toBeDefined();
  });
});
