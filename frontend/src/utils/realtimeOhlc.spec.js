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

  it("keeps weekly candles as date-only rows while updating the current bucket", () => {
    const rows = [
      {
        date: "2026-04-06",
        open: 95,
        high: 102,
        low: 93,
        close: 101,
        volume: 6200,
        adj_close: 101,
        source: "fubon_neo",
      },
    ];

    const updated = upsertRealtimeOhlcFromQuote(
      rows,
      {
        price: 103,
        open: 96,
        high: 104,
        low: 92,
        volume: 2400,
        quote_timestamp: "2026-04-10T11:18:40+08:00",
        source: "fubon_neo",
      },
      "1wk",
    );

    expect(updated).toHaveLength(1);
    expect(updated[0]).toMatchObject({
      date: "2026-04-06",
      open: 95,
      high: 104,
      low: 92,
      close: 103,
      volume: 6200,
    });
  });

  it("creates month candles with date-only labels when a new month starts", () => {
    const rows = [
      {
        date: "2026-04-01",
        open: 90,
        high: 106,
        low: 88,
        close: 104,
        volume: 8200,
        adj_close: 104,
        source: "fubon_neo",
      },
    ];

    const updated = upsertRealtimeOhlcFromQuote(
      rows,
      {
        price: 107,
        open: 105,
        high: 108,
        low: 104,
        volume: 1500,
        quote_timestamp: "2026-05-04T09:06:00+08:00",
        source: "fubon_neo",
      },
      "1mo",
    );

    expect(updated).toHaveLength(2);
    expect(updated[1]).toMatchObject({
      date: "2026-05-01",
      open: 105,
      high: 108,
      low: 104,
      close: 107,
      volume: 1500,
    });
  });
});
