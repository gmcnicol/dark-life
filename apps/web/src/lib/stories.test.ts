import { describe, expect, it } from "vitest";
import type { Story, StoryOverview } from "./stories";

describe("story typing fixtures", () => {
  it("accepts canonical story statuses", () => {
    const story: Story = { id: 1, title: "t", status: "ingested" };
    expect(story.status).toBe("ingested");
  });

  it("captures overview collections", () => {
    const overview: StoryOverview = {
      story: { id: 1, title: "t", status: "scripted" },
      active_script: null,
      script_versions: [],
      script_batches: [],
      parts: [],
      asset_bundles: [],
      releases: [],
      artifacts: [],
    };
    expect(overview.story.status).toBe("scripted");
  });
});
