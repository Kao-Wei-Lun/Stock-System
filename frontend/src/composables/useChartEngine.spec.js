import { describe, expect, it } from "vitest";

import { resolveLegacyMainChartAutoScaleRange } from "./useChartEngine";

describe("resolveLegacyMainChartAutoScaleRange", () => {
  it("keeps legacy auto scale focused on candle prices instead of overlays", () => {
    const candles = [
      { high: 110, low: 98 },
      { high: 108, low: 95 },
      { high: 109, low: 97 },
    ];
    const farAwayOverlayValues = [[20, 1000], [60], [420]];

    const rangeWithCandlesOnly = resolveLegacyMainChartAutoScaleRange(candles, [], "linear");
    const rangeWithOverlays = resolveLegacyMainChartAutoScaleRange(candles, farAwayOverlayValues, "linear");
    const candleRange = 110 - 95;
    const renderedRange = rangeWithOverlays.max - rangeWithOverlays.min;

    expect(rangeWithOverlays).toEqual(rangeWithCandlesOnly);
    expect(candleRange / renderedRange).toBeCloseTo(0.9, 4);
    expect(rangeWithOverlays.min).toBeCloseTo(94.1667, 4);
    expect(rangeWithOverlays.max).toBeCloseTo(110.8333, 4);
  });
});
