import { describe, expect, it } from "vitest";

import { getIntervalBucketStart, upsertRealtimeOhlcFromQuote } from "./realtimeOhlc";

describe("realtimeOhlc", () => {
  it("rounds intraday timestamps into the active timeframe bucket", () => {
    const bucket = getIntervalBucketStart("2026-04-13T09:07:21+08:00", "5m");

    expect(bucket.getHours()).toBe(9);
    expect(bucket.getMinutes()).toBe(5);
  });

  it("updates the latest intraday candle for non-1m intervals from realtime quotes", () => {
    const rows = [
      {
        date: "2026-04-13 09:00:00",
        open: 100,
        high: 102,
        low: 99,
        close: 101,
        volume: 300,
        adj_close: 101,
        source: "fubon_neo",
      },
      {
        date: "2026-04-13 09:05:00",
        open: 101,
        high: 103,
        low: 100,
        close: 102,
        volume: 260,
        adj_close: 102,
        source: "fubon_neo",
      },
    ];

    const updated = upsertRealtimeOhlcFromQuote(
      rows,
      {
        price: 104,
        quote_timestamp: "2026-04-13T09:07:21+08:00",
        source: "fubon_neo",
      },
      "5m",
    );

    expect(updated).toHaveLength(2);
    expect(updated[1]).toMatchObject({
      date: "2026-04-13 09:05:00",
      open: 101,
      high: 104,
      low: 100,
      close: 104,
      volume: 260,
    });
  });

  it("creates the next intraday bucket when realtime quotes move into a new timeframe", () => {
    const rows = [
      {
        date: "2026-04-13 09:05:00",
        open: 101,
        high: 103,
        low: 100,
        close: 102,
        volume: 260,
        adj_close: 102,
        source: "fubon_neo",
      },
    ];

    const updated = upsertRealtimeOhlcFromQuote(
      rows,
      {
        price: 105,
        quote_timestamp: "2026-04-13T09:10:02+08:00",
        source: "fubon_neo",
      },
      "5m",
    );

    expect(updated).toHaveLength(2);
    expect(updated[1]).toMatchObject({
      date: "2026-04-13 09:10:00",
      open: 105,
      high: 105,
      low: 105,
      close: 105,
    });
  });

  it("uses daily quote fields to update the current day candle", () => {
    const rows = [
      {
        date: "2026-04-12",
        open: 98,
        high: 100,
        low: 96,
        close: 99,
        volume: 1000,
        adj_close: 99,
        source: "yahoo_finance",
      },
      {
        date: "2026-04-13",
        open: 100,
        high: 103,
        low: 99,
        close: 102,
        volume: 2300,
        adj_close: 102,
        source: "fubon_neo",
      },
    ];

    const updated = upsertRealtimeOhlcFromQuote(
      rows,
      {
        price: 104,
        open: 100,
        high: 105,
        low: 98,
        volume: 2800,
        quote_timestamp: "2026-04-13T11:18:40+08:00",
        source: "fubon_neo",
      },
      "1d",
    );

    expect(updated).toHaveLength(2);
    expect(updated[1]).toMatchObject({
      date: "2026-04-13",
      open: 100,
      high: 105,
      low: 98,
      close: 104,
      volume: 2800,
    });
  });
});
