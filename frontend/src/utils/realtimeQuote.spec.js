import { describe, expect, it } from "vitest";

import { mergeRealtimeQuote } from "./realtimeQuote";

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
});
