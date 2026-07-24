import { describe, expect, it, vi } from "vitest";

import {
  createLegacyBarLayout,
  distanceToSegment,
  invertLegacyPriceY,
  scaleLegacyPriceY,
} from "./legacyChartCoordinates";
import {
  formatLegacyAxisDateLabel,
  getLegacyTimeTickIndices,
  resolveLegacyCrosshairMarker,
} from "./legacyChartCrosshair";
import {
  createLegacyDrawingRenderer,
  getDrawingDash,
  getDrawingFill,
  getDrawingWidth,
  LEGACY_FIB_LEVELS,
  withOpacity,
} from "./legacyChartDrawingRenderer";
import { drawLine, findLastDefinedIndex } from "./legacyChartIndicatorRenderer";
import {
  buildLegacyCrosshairPayload,
  computePannedStartIndex,
  computeZoomViewport,
} from "./legacyChartInteraction";
import {
  getPaddedPriceRange,
  getVisiblePriceScale,
  resolveLegacyMainChartAutoScaleRange,
} from "./legacyChartPriceScale";

describe("legacy chart numeric modules", () => {
  it("round-trips linear and logarithmic price coordinates", () => {
    for (const scaleMode of ["linear", "log"]) {
      const min = scaleMode === "log" ? 10 : -10;
      const max = 200;
      const price = scaleMode === "log" ? 48 : 48.5;
      const pixel = scaleLegacyPriceY(price, min, max, 20, 400, scaleMode);
      const restored = invertLegacyPriceY(pixel, min, max, 20, 400, scaleMode);
      expect(restored).toBeCloseTo(price, 10);
    }
  });

  it("keeps bar centers and segment hit distance deterministic", () => {
    const layout = createLegacyBarLayout(1080, 100);
    expect(layout.width).toBe(1000);
    expect(layout.step).toBe(10);
    expect(layout.barX(0)).toBe(15);
    expect(layout.barX(99)).toBe(1005);
    expect(distanceToSegment(5, 4, 0, 0, 10, 0)).toBe(4);
  });

  it("pads ranges and filters unreasonable main-chart overlays", () => {
    const padded = getPaddedPriceRange(90, 110);
    expect((110 - 90) / (padded.max - padded.min)).toBeCloseTo(0.9, 8);

    const visible = getVisiblePriceScale(
      [{ low: 90, high: 110 }],
      [[85, 115]],
    );
    expect(visible.min).toBeLessThan(85);
    expect(visible.max).toBeGreaterThan(115);

    const main = resolveLegacyMainChartAutoScaleRange(
      [{ low: 90, high: 110 }],
      [[1, 1000]],
    );
    expect(main.min).toBeGreaterThan(80);
    expect(main.max).toBeLessThan(120);
  });

  it("preserves zoom anchors and clamps pan boundaries", () => {
    expect(computePannedStartIndex({
      startIndex: 5,
      deltaBars: -20,
      totalCount: 200,
      visibleCount: 100,
    })).toBe(0);

    const zoomed = computeZoomViewport({
      startIndex: 40,
      currentVisibleCount: 100,
      nextVisibleCount: 50,
      minimumVisibleCount: 20,
      totalCount: 300,
      anchorRatio: 0.5,
    });
    expect(zoomed).toEqual({ startIndex: 66, visibleCount: 50, changed: true });
    const previousAnchor = 40 + Math.round((100 - 1) * 0.5);
    const nextAnchor = zoomed.startIndex + Math.round((zoomed.visibleCount - 1) * 0.5);
    expect(Math.abs(nextAnchor - previousAnchor)).toBeLessThanOrEqual(1);
  });

  it("resolves crosshair markers only inside the visible viewport", () => {
    const data = [
      { date: "2026-07-24T09:00:00+08:00" },
      { date: "2026-07-24T09:01:00+08:00" },
    ];
    const layout = { barX: (index) => index * 10 + 5 };
    const marker = resolveLegacyCrosshairMarker({
      crosshair: { visible: true, absoluteIndex: 11 },
      viewportStartIndex: 10,
      data,
      layout,
      interval: "1m",
    });
    expect(marker).toMatchObject({ localIndex: 1, x: 15, dateLabel: "26/07/24 09:01" });
    expect(resolveLegacyCrosshairMarker({
      crosshair: { visible: true, absoluteIndex: 12 },
      viewportStartIndex: 10,
      data,
      layout,
      interval: "1m",
    })).toBeNull();
    expect(getLegacyTimeTickIndices(data, 6)).toEqual([0, 1]);
    expect(formatLegacyAxisDateLabel(data[0].date, { interval: "1m" })).toBe("09:00");
  });

  it("builds formatted crosshair payloads in the interaction layer", () => {
    const payload = buildLegacyCrosshairPayload({
      info: {
        x: 20,
        y: 30,
        price: 102,
        absoluteIndex: 3,
        row: {
          date: "2026-07-24",
          open: 100,
          high: 104,
          low: 99,
          close: 103,
          volume: 1200,
        },
      },
      previousRow: { close: 100 },
      formatPrice: (value) => Number(value).toFixed(2),
      formatVolume: (value) => `${value}v`,
    });
    expect(payload).toMatchObject({
      change: "+3.00",
      changePct: "+3.00%",
      volume: "1200v",
      absoluteIndex: 3,
    });
  });

  it("keeps drawing presentation normalization outside the engine", () => {
    expect(getDrawingDash({ lineStyle: "dot" })).toEqual([2, 4]);
    expect(getDrawingWidth({ lineWidth: "2.5" })).toBe(2.5);
    expect(getDrawingFill({ color: "#123456", fillOpacity: "0.4" }))
      .toEqual({ color: "#123456", opacity: 0.4 });
    expect(withOpacity("#0af", 0.5)).toBe("rgba(0,170,255,0.5)");
  });

  it("renders Fibonacci levels through the dedicated drawing renderer", () => {
    const ctx = {
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      fillText: vi.fn(),
      setLineDash: vi.fn(),
    };
    const renderer = createLegacyDrawingRenderer({
      xForAbsoluteIndex: (_layout, index) => index * 10,
    });
    renderer.drawFib(
      ctx,
      {},
      { startIndex: 1, endIndex: 3, startPrice: 100, endPrice: 120 },
      (value) => value,
      400,
    );
    expect(ctx.stroke).toHaveBeenCalledTimes(LEGACY_FIB_LEVELS.length);
    expect(ctx.setLineDash).toHaveBeenLastCalledWith([]);
  });

  it("renders finite indicator points and finds the final finite value", () => {
    const ctx = {
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      setLineDash: vi.fn(),
    };
    drawLine(ctx, [1, null, Number.NaN, 3], (index) => index * 10, (value) => value, "#fff");
    expect(ctx.moveTo).toHaveBeenCalledWith(0, 1);
    expect(ctx.lineTo).toHaveBeenCalledWith(30, 3);
    expect(findLastDefinedIndex([1, null, Number.NaN, 3])).toBe(3);
  });
});
