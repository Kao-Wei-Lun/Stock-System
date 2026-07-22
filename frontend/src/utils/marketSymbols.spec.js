import { describe, expect, it } from "vitest";

import {
  inferMarketFromTicker,
  isFutoptTicker,
  normalizeTicker,
  resolveDashboardTimeframeForTicker,
} from "./marketSymbols";

describe("market symbol policies", () => {
  it("keeps continuous and concrete futures symbols intact", () => {
    expect(normalizeTicker("*tmff")).toBe("*TMFF");
    expect(normalizeTicker("TMFE6")).toBe("TMFE6");
    expect(isFutoptTicker("TXFE6")).toBe(true);
    expect(inferMarketFromTicker("*TXFF")).toBe("FUTOPT");
  });

  it("normalizes numeric Taiwan symbols and leaves US symbols unchanged", () => {
    expect(normalizeTicker("2330")).toBe("2330.TW");
    expect(normalizeTicker("aapl")).toBe("AAPL");
    expect(inferMarketFromTicker("2330.TW")).toBe("TW");
  });

  it("keeps futures requests inside supported intraday ranges", () => {
    expect(resolveDashboardTimeframeForTicker("TMF", "1y", "1d")).toEqual({
      period: "1d",
      interval: "1m",
    });
  });
});
