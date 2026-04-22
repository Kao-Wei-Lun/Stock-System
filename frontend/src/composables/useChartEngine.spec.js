import { describe, expect, it } from "vitest";

import { formatLegacyAxisDateLabel, resolveLegacyMainChartAutoScaleRange } from "./useChartEngine";

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

describe("formatLegacyAxisDateLabel", () => {
  it("formats intraday labels with time for minute bars", () => {
    expect(
      formatLegacyAxisDateLabel("2026-04-22T09:22:00.000+08:00", { interval: "1m" }),
    ).toBe("09:22");
  });

  it("adds the date when an intraday crosshair label needs full context", () => {
    expect(
      formatLegacyAxisDateLabel("2026-04-22 09:22:00", { interval: "1m", includeDate: true }),
    ).toBe("26/04/22 09:22");
  });

  it("keeps daily labels on the existing short date format", () => {
    expect(
      formatLegacyAxisDateLabel("2026-04-22T00:00:00.000+08:00", { interval: "1d", rangeDays: 30 }),
    ).toBe("26/04/22");
  });
});
