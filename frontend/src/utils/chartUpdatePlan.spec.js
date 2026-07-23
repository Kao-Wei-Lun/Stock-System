import { describe, expect, it } from "vitest";

import { CHART_UPDATE_KIND, classifyChartDataUpdate } from "./chartUpdatePlan";

const row = (date, close) => ({ date, open: close, high: close, low: close, close, volume: 1 });

describe("classifyChartDataUpdate", () => {
  it("uses the last-bar path for an immutable replacement of the current bucket", () => {
    const first = row("2026-07-23 09:00:00", 100);
    const previous = [first, row("2026-07-23 09:01:00", 101)];
    const next = [first, { ...previous[1], close: 102 }];

    expect(classifyChartDataUpdate(previous, next)).toBe(CHART_UPDATE_KIND.lastBar);
  });

  it("uses append only when the previous history is retained by identity", () => {
    const previous = [row("2026-07-23 09:00:00", 100), row("2026-07-23 09:01:00", 101)];
    const next = [...previous, row("2026-07-23 09:02:00", 102)];

    expect(classifyChartDataUpdate(previous, next)).toBe(CHART_UPDATE_KIND.appendBar);
  });

  it("requires full reset for refreshed history, ticker changes, and interval changes", () => {
    const previous = [row("2026-07-23 09:00:00", 100), row("2026-07-23 09:01:00", 101)];
    const refreshed = previous.map((item) => ({ ...item }));

    expect(classifyChartDataUpdate(previous, refreshed)).toBe(CHART_UPDATE_KIND.fullReset);
    expect(classifyChartDataUpdate(previous, previous, {
      previousTicker: "AAPL",
      nextTicker: "MSFT",
    })).toBe(CHART_UPDATE_KIND.fullReset);
    expect(classifyChartDataUpdate(previous, previous, {
      previousInterval: "1m",
      nextInterval: "5m",
    })).toBe(CHART_UPDATE_KIND.fullReset);
  });
});
