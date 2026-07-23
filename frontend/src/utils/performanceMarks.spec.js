import { afterEach, describe, expect, it, vi } from "vitest";

import {
  QV_PERFORMANCE_MARKS,
  markQuantVisionPerformance,
  readQuantVisionPerformance,
} from "./performanceMarks";


describe("performanceMarks", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete window.__QV_PERFORMANCE__;
  });

  it("records only known marks and publishes a safe browser snapshot", () => {
    const entries = new Map();
    vi.spyOn(performance, "clearMarks").mockImplementation((name) => entries.delete(name));
    vi.spyOn(performance, "mark").mockImplementation((name, options) => {
      entries.set(name, [{ startTime: 123.456, detail: options?.detail || null }]);
    });
    vi.spyOn(performance, "getEntriesByName").mockImplementation((name) => entries.get(name) || []);

    expect(markQuantVisionPerformance(QV_PERFORMANCE_MARKS.chartDataReady, {
      ticker: "*TMFF",
      rows: 120,
      nested: { excluded: true },
    })).toBe(true);
    expect(markQuantVisionPerformance("qv:unknown", {})).toBe(false);

    expect(window.__QV_PERFORMANCE__.marks[QV_PERFORMANCE_MARKS.chartDataReady]).toEqual({
      start_time_ms: 123.46,
      detail: { ticker: "*TMFF", rows: 120 },
    });
  });

  it("returns null entries when a mark has not been recorded", () => {
    vi.spyOn(performance, "getEntriesByName").mockReturnValue([]);

    const snapshot = readQuantVisionPerformance();

    expect(snapshot.marks[QV_PERFORMANCE_MARKS.appMounted]).toBeNull();
  });
});

