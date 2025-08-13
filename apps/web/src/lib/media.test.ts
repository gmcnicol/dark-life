import { describe, expect, it } from "vitest";
import type { CatalogImage } from "./catalog";
import { selectImage, bulkApply } from "./media";

describe("media selection", () => {
  it("selectImage assigns image at index", () => {
    const img: CatalogImage = { url: "a" };
    const res = selectImage([null, null], 1, img);
    expect(res[1]).toEqual(img);
  });
  it("bulkApply copies first selection", () => {
    const img: CatalogImage = { url: "a" };
    const res = bulkApply([img, null, null]);
    expect(res).toEqual([img, img, img]);
  });
});
