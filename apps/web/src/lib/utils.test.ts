import { describe, expect, it } from "vitest";
import { formatLocalDateTime, isSameLocalDay, parseDateValue } from "./utils";

describe("parseDateValue", () => {
  it("returns null for invalid dates", () => {
    expect(parseDateValue("not-a-date")).toBeNull();
  });
});

describe("formatLocalDateTime", () => {
  it("formats timestamps as dd-MM-yyyy hh:mm", () => {
    expect(formatLocalDateTime("2026-04-11T08:05:00Z")).toMatch(/^\d{2}-\d{2}-\d{4} \d{2}:\d{2}$/);
  });

  it("uses the fallback for missing values", () => {
    expect(formatLocalDateTime(null, "n/a")).toBe("n/a");
  });
});

describe("isSameLocalDay", () => {
  it("compares dates using local calendar day semantics", () => {
    const now = new Date("2026-04-11T12:00:00");
    expect(isSameLocalDay("2026-04-11T00:30:00", now)).toBe(true);
    expect(isSameLocalDay("2026-04-10T23:59:00", now)).toBe(false);
  });
});
