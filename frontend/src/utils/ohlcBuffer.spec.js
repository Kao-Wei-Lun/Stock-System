import { describe, expect, it } from "vitest";

import { mergeOhlcBuffer } from "./ohlcBuffer";

describe("mergeOhlcBuffer", () => {
  it("deduplicates dates, lets incremental rows win, and bounds retained rows", () => {
    const current = [
      { date: "2026-07-23T09:00:00+08:00", close: 100 },
      { date: "2026-07-23T09:01:00+08:00", close: 101 },
    ];
    const incoming = [
      { date: "2026-07-23T09:01:00+08:00", close: 102 },
      { date: "2026-07-23T09:02:00+08:00", close: 103 },
    ];

    expect(mergeOhlcBuffer(current, incoming, 2)).toEqual([
      { date: "2026-07-23T09:01:00+08:00", close: 102 },
      { date: "2026-07-23T09:02:00+08:00", close: 103 },
    ]);
  });
});
