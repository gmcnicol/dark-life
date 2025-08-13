import { describe, it, expect } from "vitest";
import { mapJobStatus } from "./jobs";

describe("mapJobStatus", () => {
  it("maps known statuses", () => {
    expect(mapJobStatus("queued")).toBe("Queued");
    expect(mapJobStatus("running")).toBe("Running");
    expect(mapJobStatus("done")).toBe("Done");
    expect(mapJobStatus("error")).toBe("Error");
  });
  it("falls back on unknown", () => {
    expect(mapJobStatus("mystery")).toBe("Unknown");
  });
});
