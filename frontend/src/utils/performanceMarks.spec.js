import { afterEach, describe, expect, it, vi } from "vitest";

import {
  QV_PERFORMANCE_MARKS,
  markQuantVisionPerformance,
  recordQuantVisionRealtimeMessage,
  readQuantVisionPerformance,
  resetQuantVisionPerformanceForTests,
  startQuantVisionPerformanceObserver,
} from "./performanceMarks";


describe("performanceMarks", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    resetQuantVisionPerformanceForTests();
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

  it("collects bounded long-task, resource, and measure summaries", () => {
    let callback = null;
    class FakeObserver {
      static supportedEntryTypes = ["longtask", "measure", "resource"];

      constructor(handler) {
        callback = handler;
      }

      observe = vi.fn();
      disconnect = vi.fn();
    }

    expect(startQuantVisionPerformanceObserver(FakeObserver)).toBe(true);
    callback({
      getEntries: () => [
        { entryType: "longtask", duration: 75.25 },
        { entryType: "measure", name: "qv:test-measure", duration: 12.5 },
        { entryType: "resource", initiatorType: "script", duration: 20, transferSize: 1024 },
      ],
    });

    const snapshot = readQuantVisionPerformance();
    expect(snapshot.runtime.long_tasks).toMatchObject({ count: 1, p95_ms: 75.25 });
    expect(snapshot.runtime.measures["qv:test-measure"]).toBe(12.5);
    expect(snapshot.runtime.resources.script).toMatchObject({
      count: 1,
      transfer_bytes: 1024,
      duration_ms: 20,
    });
  });

  it("measures transport and next-paint latency without retaining payload data", () => {
    let paintCallback = null;
    recordQuantVisionRealtimeMessage(
      { ts: 9_950, ticker: "private-symbol", data: { account: "private" } },
      {
        nowEpochMs: 10_000,
        nowPerformanceMs: 200,
        requestFrame: (callback) => {
          paintCallback = callback;
          return 1;
        },
      },
    );
    paintCallback(216.5);

    const snapshot = readQuantVisionPerformance();
    expect(snapshot.runtime.realtime_transport).toMatchObject({ count: 1, p95_ms: 50 });
    expect(snapshot.runtime.realtime_paint).toMatchObject({ count: 1, p95_ms: 16.5 });
    expect(JSON.stringify(snapshot)).not.toContain("private-symbol");
    expect(JSON.stringify(snapshot)).not.toContain("account");
  });

  it("reads the default performance clock without production-only call binding errors", () => {
    let paintCallback = null;
    vi.spyOn(performance, "now").mockReturnValue(250);

    recordQuantVisionRealtimeMessage(
      { ts: 9_990 },
      {
        nowEpochMs: 10_000,
        requestFrame: (callback) => {
          paintCallback = callback;
          return 1;
        },
      },
    );
    paintCallback(260);

    expect(readQuantVisionPerformance().runtime.realtime_paint).toMatchObject({
      count: 1,
      p95_ms: 10,
    });
  });
});
