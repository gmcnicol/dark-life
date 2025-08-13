import { describe, expect, it } from "vitest";
import { StorySchema } from "./stories";

describe("StorySchema", () => {
  it("parses valid story", () => {
    const data = { id: 1, title: "t", status: "pending" };
    expect(() => StorySchema.parse(data)).not.toThrow();
  });
  it("rejects invalid story", () => {
    const data = { title: "t", status: "pending" } as unknown;
    expect(() => StorySchema.parse(data)).toThrow();
  });
});
