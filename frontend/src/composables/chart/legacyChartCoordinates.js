import { clampPositive } from "./legacyChartPriceScale";

export const LEGACY_CHART_PAD = { top: 20, right: 70, bottom: 22, left: 10 };

export const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

export function createLegacyBarLayout(width, count, pad = LEGACY_CHART_PAD) {
  const plotWidth = width - pad.left - pad.right;
  const step = plotWidth / Math.max(count, 1);
  return {
    width: plotWidth,
    step,
    barWidth: Math.max(1.5, step * 0.72),
    barX: (index) => pad.left + (index + 0.5) * step,
  };
}

export function scaleLegacyPriceY(
  value,
  min,
  max,
  topPad,
  chartHeight,
  scaleMode = "linear",
) {
  if (scaleMode === "log" && min > 0 && max > 0 && value > 0) {
    const logMin = Math.log(clampPositive(min));
    const logMax = Math.log(clampPositive(max));
    const logValue = Math.log(clampPositive(value));
    return topPad + (1 - (logValue - logMin) / (logMax - logMin || 1)) * chartHeight;
  }
  return topPad + (1 - (value - min) / (max - min || 1)) * chartHeight;
}

export function invertLegacyPriceY(
  pixelY,
  min,
  max,
  topPad,
  chartHeight,
  scaleMode = "linear",
) {
  const ratio = 1 - (pixelY - topPad) / (chartHeight || 1);
  if (scaleMode === "log" && min > 0 && max > 0) {
    const logMin = Math.log(clampPositive(min));
    const logMax = Math.log(clampPositive(max));
    return Math.exp(logMin + ratio * (logMax - logMin));
  }
  return min + ratio * (max - min);
}

export function distanceToSegment(pointX, pointY, x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (dx === 0 && dy === 0) return Math.hypot(pointX - x1, pointY - y1);
  const ratio = clamp(((pointX - x1) * dx + (pointY - y1) * dy) / (dx * dx + dy * dy), 0, 1);
  const projectionX = x1 + ratio * dx;
  const projectionY = y1 + ratio * dy;
  return Math.hypot(pointX - projectionX, pointY - projectionY);
}
