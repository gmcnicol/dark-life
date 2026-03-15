import { describe, it, expect } from "vitest";
import { mapJobStatus } from "./jobs";

describe("mapJobStatus", () => {
  it("maps known statuses", () => {
    expect(mapJobStatus("queued")).toBe("Queued");
    expect(mapJobStatus("claimed")).toBe("Claimed");
    expect(mapJobStatus("rendering")).toBe("Rendering");
    expect(mapJobStatus("publish_ready")).toBe("Publish Ready");
    expect(mapJobStatus("errored")).toBe("Errored");
  });
  it("falls back on raw value for unknown", () => {
    expect(mapJobStatus("mystery" as never)).toBe("mystery");
  });
});
