import { describe, expect, it } from "vitest";

import { mergeBookLevels, mergeRealtimeQuote } from "./realtimeQuote";

describe("mergeRealtimeQuote", () => {
  it("keeps the previous volume when realtime payload omits cumulative volume", () => {
    const merged = mergeRealtimeQuote(
      {
        price: 233,
        volume: 125000,
        name: "TSMC",
        source: "fubon_neo",
      },
      {
        price: 234,
        volume: null,
        quote_timestamp: "2026-04-16T09:05:01+08:00",
      },
      "TSMC",
    );

    expect(merged.price).toBe(234);
    expect(merged.volume).toBe(125000);
    expect(merged.name).toBe("TSMC");
  });

  it("accepts a new positive cumulative volume when provided", () => {
    const merged = mergeRealtimeQuote(
      {
        price: 233,
        volume: 125000,
      },
      {
        price: 234,
        volume: 126400,
      },
      "TSMC",
    );

    expect(merged.volume).toBe(126400);
  });

  it("keeps existing book depth when incoming realtime payload has empty books", () => {
    const previousBook = [
      { price: 39656, size: 1 },
      { price: 39655, size: 2 },
      { price: 39654, size: 3 },
    ];
    const merged = mergeRealtimeQuote(
      {
        price: 39658,
        bid: 39656,
        ask: 39660,
        bids: previousBook,
        asks: [{ price: 39660, size: 1 }, { price: 39661, size: 2 }],
      },
      {
        price: 39658,
        bids: [],
        asks: [],
      },
      "TMFE6",
    );

    expect(merged.bids).toEqual(previousBook);
    expect(merged.asks).toEqual([{ price: 39660, size: 1 }, { price: 39661, size: 2 }]);
  });

  it("updates the first book level while preserving deeper levels", () => {
    const merged = mergeRealtimeQuote(
      {
        bid: 39656,
        bid_size: 1,
        bids: [
          { price: 39656, size: 1 },
          { price: 39655, size: 2 },
          { price: 39654, size: 3 },
        ],
      },
      {
        bid: 39657,
        bid_size: 4,
        bids: [{ price: 39657, size: 4 }],
      },
      "TMFE6",
    );

    expect(merged.bids).toEqual([
      { price: 39657, size: 4 },
      { price: 39655, size: 2 },
      { price: 39654, size: 3 },
    ]);
  });

  it("carries provider freshness metadata and clears recovered errors", () => {
    const merged = mergeRealtimeQuote(
      {
        freshness_status: "stale",
        stale_reason: "provider_backoff",
        backoff_until: "2026-07-23T10:00:00Z",
        provider_degraded: true,
      },
      {
        freshness_status: "current",
        is_stale: false,
        stale_reason: null,
        backoff_until: null,
        provider_degraded: false,
      },
    );

    expect(merged.freshness_status).toBe("current");
    expect(merged.is_stale).toBe(false);
    expect(merged.stale_reason).toBeNull();
    expect(merged.backoff_until).toBeNull();
    expect(merged.provider_degraded).toBe(false);
  });
});

describe("mergeBookLevels", () => {
  it("does not clear previous levels for missing or empty incremental updates", () => {
    const previous = [
      { price: 101, size: 10 },
      { price: 100, size: 20 },
    ];

    expect(mergeBookLevels(previous, undefined)).toEqual(previous);
    expect(mergeBookLevels(previous, [])).toEqual(previous);
  });

  it("uses scalar top-of-book updates without dropping deeper levels", () => {
    const previous = [
      { price: 101, size: 10 },
      { price: 100, size: 20 },
    ];

    expect(mergeBookLevels(previous, undefined, { price: 102, size: 3 })).toEqual([
      { price: 102, size: 3 },
      { price: 100, size: 20 },
    ]);
  });
});
