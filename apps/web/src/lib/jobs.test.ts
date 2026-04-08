import { describe, it, expect } from "vitest";
import { STALE_JOB_MS, canRequeueJob, isStaleJob, mapJobStatus } from "./jobs";

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

  it("treats long-running claimed or rendering jobs as stale", () => {
    const now = Date.parse("2026-04-08T18:00:00Z");
    expect(
      isStaleJob(
        { status: "rendering", updated_at: new Date(now - STALE_JOB_MS - 1).toISOString() } as never,
        now,
      ),
    ).toBe(true);
    expect(
      isStaleJob(
        { status: "claimed", updated_at: new Date(now - STALE_JOB_MS - 1).toISOString() } as never,
        now,
      ),
    ).toBe(true);
  });

  it("only enables requeue for errored or stale jobs", () => {
    const now = Date.parse("2026-04-08T18:00:00Z");
    expect(canRequeueJob({ status: "errored", updated_at: null } as never, now)).toBe(true);
    expect(
      canRequeueJob(
        { status: "rendering", updated_at: new Date(now - STALE_JOB_MS - 1).toISOString() } as never,
        now,
      ),
    ).toBe(true);
    expect(
      canRequeueJob(
        { status: "rendering", updated_at: new Date(now - STALE_JOB_MS + 1).toISOString() } as never,
        now,
      ),
    ).toBe(false);
    expect(canRequeueJob({ status: "publish_ready", updated_at: null } as never, now)).toBe(false);
  });
});
