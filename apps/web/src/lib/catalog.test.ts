import { beforeAll, afterAll, afterEach, describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { fetchCatalog } from "./catalog";

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("fetchCatalog", () => {
  it("returns mocked images", async () => {
    const images = await fetchCatalog();
    expect(images).toHaveLength(2);
    expect(images[0]!.url).toBeDefined();
  });
});
