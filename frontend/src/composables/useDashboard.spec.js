import { describe, expect, it } from "vitest";

import {
  getTimeframeOptionsForTicker,
  normalizeDashboardRightTab,
  normalizeTicker,
  resolveDashboardTimeframeForTicker,
  shouldPollFutoptRestFallback,
} from "./useDashboard";

describe("dashboard timeframe helpers", () => {
  it("maps retired database drawer state to the supported indicator drawer", () => {
    expect(normalizeDashboardRightTab("db")).toBe("indicators");
    expect(normalizeDashboardRightTab("alerts")).toBe("alerts");
    expect(normalizeDashboardRightTab(" JOURNAL ")).toBe("journal");
  });

  it("uses a futopt-only intraday timeframe menu for futures contracts and base symbols", () => {
    expect(normalizeTicker("TMF")).toBe("TMF");
    expect(normalizeTicker("*txff")).toBe("*TXFF");
    expect(normalizeTicker("*tmff")).toBe("*TMFF");

    const labels = getTimeframeOptionsForTicker("TMF").map((option) => option.label);

    expect(labels).toEqual(["1m", "5m", "15m", "30m", "60m"]);
    expect(labels).not.toContain("1M");
    expect(labels).not.toContain("MAX");
  });

  it("keeps supported futopt intraday intervals when switching timeframe", () => {
    expect(resolveDashboardTimeframeForTicker("TXFE6", "5d", "5m")).toEqual({
      period: "5d",
      interval: "5m",
    });
    expect(resolveDashboardTimeframeForTicker("TXFE6", "1mo", "30m")).toEqual({
      period: "1mo",
      interval: "30m",
    });
    expect(resolveDashboardTimeframeForTicker("TXFE6", "3mo", "60m")).toEqual({
      period: "3mo",
      interval: "60m",
    });
  });

  it("falls back invalid futopt daily timeframe requests to the 1m intraday view", () => {
    expect(resolveDashboardTimeframeForTicker("MXF", "1y", "1d")).toEqual({
      period: "1d",
      interval: "1m",
    });
  });

  it("polls futopt REST fallback only when intraday realtime is stale", () => {
    expect(shouldPollFutoptRestFallback({
      ticker: "TMFE6",
      interval: "1m",
      lastRealtimeAt: 1_000,
      now: 14_000,
      staleMs: 12_000,
    })).toBe(true);
    expect(shouldPollFutoptRestFallback({
      ticker: "TMFE6",
      interval: "1m",
      lastRealtimeAt: 10_000,
      now: 14_000,
      staleMs: 12_000,
    })).toBe(false);
    expect(shouldPollFutoptRestFallback({
      ticker: "2330.TW",
      interval: "1m",
      lastRealtimeAt: 1_000,
      now: 14_000,
      staleMs: 12_000,
    })).toBe(false);
    expect(shouldPollFutoptRestFallback({
      ticker: "TMFE6",
      interval: "1d",
      lastRealtimeAt: 1_000,
      now: 14_000,
      staleMs: 12_000,
    })).toBe(false);
  });
});
