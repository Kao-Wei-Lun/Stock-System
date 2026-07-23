import { describe, expect, it } from "vitest";

import {
  formatLegacyAxisDateLabel,
  resolveLegacyMainChartAutoScaleRange,
  shouldHandlePriceAxisInteraction,
} from "./useChartEngine";

describe("resolveLegacyMainChartAutoScaleRange", () => {
  it("includes reasonable price indicators but rejects corrupt overlay outliers", () => {
    const candles = [
      { high: 110, low: 98 },
      { high: 108, low: 95 },
      { high: 109, low: 97 },
    ];
    const farAwayOverlayValues = [[20, 1000], [60], [420]];
    const reasonablePriceIndicators = [[94, 112]];

    const rangeWithCandlesOnly = resolveLegacyMainChartAutoScaleRange(candles, [], "linear");
    const rangeWithOverlays = resolveLegacyMainChartAutoScaleRange(candles, farAwayOverlayValues, "linear");
    const rangeWithIndicators = resolveLegacyMainChartAutoScaleRange(candles, reasonablePriceIndicators, "linear");
    const candleRange = 110 - 95;
    const renderedRange = rangeWithOverlays.max - rangeWithOverlays.min;

    expect(rangeWithOverlays).toEqual(rangeWithCandlesOnly);
    expect(candleRange / renderedRange).toBeCloseTo(0.9, 4);
    expect(rangeWithOverlays.min).toBeCloseTo(94.1667, 4);
    expect(rangeWithOverlays.max).toBeCloseTo(110.8333, 4);
    expect(rangeWithIndicators.min).toBeLessThan(94);
    expect(rangeWithIndicators.max).toBeGreaterThan(112);
  });

  it("always contains every visible candle including a newly appended high and low", () => {
    const range = resolveLegacyMainChartAutoScaleRange([
      { high: 100, low: 95 },
      { high: 102, low: 94 },
      { high: 140, low: 80 },
    ]);

    expect(range.min).toBeLessThan(80);
    expect(range.max).toBeGreaterThan(140);
  });
});

describe("price-axis interaction mode", () => {
  it("does not let price-axis wheel or drag leave auto mode implicitly", () => {
    expect(shouldHandlePriceAxisInteraction("auto")).toBe(false);
    expect(shouldHandlePriceAxisInteraction("manual")).toBe(false);
    expect(shouldHandlePriceAxisInteraction("manual_locked")).toBe(true);
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
