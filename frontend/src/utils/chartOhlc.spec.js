import { describe, expect, it } from "vitest";

import { filterRenderableOhlcRows, isRenderableOhlcRow } from "./chartOhlc";

describe("chartOhlc", () => {
  it("keeps only rows that can render an actual candle", () => {
    const rows = [
      { date: "2026-04-17 09:00:00", open: 100, high: 102, low: 99, close: 101, volume: 300 },
      { date: "2026-04-17 09:01:00", open: null, high: null, low: null, close: null, volume: 0 },
      { date: "bad-date", open: 101, high: 103, low: 100, close: 102, volume: 250 },
      { date: "2026-04-17 09:02:00", open: 101, high: 104, low: 100, close: 103, volume: 280 },
    ];

    expect(filterRenderableOhlcRows(rows)).toEqual([rows[0], rows[3]]);
  });

  it("matches LWC-style validation for realtime placeholders", () => {
    expect(isRenderableOhlcRow({
      date: "2026-04-17 09:03:00",
      open: undefined,
      high: undefined,
      low: undefined,
      close: undefined,
    })).toBe(false);

    expect(isRenderableOhlcRow({
      date: "2026-04-17 09:03:00",
      open: 103,
      high: 105,
      low: 102,
      close: 104,
    })).toBe(true);
  });
});
