import { describe, expect, it, vi } from "vitest";
import { optimisticUpdate } from "./optimistic";

describe("optimisticUpdate", () => {
  it("rolls back on failure", async () => {
    let state = "pending";
    const setState = (v: string) => {
      state = v;
    };
    const action = vi.fn().mockRejectedValue(new Error("fail"));
    await expect(optimisticUpdate(state, setState, "approved", action)).rejects.toThrow();
    expect(state).toBe("pending");
  });
});
