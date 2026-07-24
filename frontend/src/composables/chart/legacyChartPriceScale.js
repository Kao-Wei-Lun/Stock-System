const AUTO_Y_TARGET_OCCUPANCY = 0.9;
const AUTO_Y_MIN_PADDING_ABS = 0.005;

export const clampPositive = (value) => Math.max(value, Number.EPSILON);

export function resolveAutoYPadding(range) {
  return Math.max(
    (((1 / AUTO_Y_TARGET_OCCUPANCY) - 1) * range) / 2,
    AUTO_Y_MIN_PADDING_ABS,
  );
}

export function getPaddedPriceRange(rawMin, rawMax, scaleMode = "linear") {
  let min = rawMin;
  let max = rawMax;

  if (rawMin === rawMax) {
    const singlePad = Math.max(Math.abs(rawMin) * 0.08, 1);
    min = rawMin - singlePad;
    max = rawMax + singlePad;
  } else {
    const range = rawMax - rawMin;
    const padding = resolveAutoYPadding(range);
    min = rawMin - padding;
    max = rawMax + padding;
  }

  if (scaleMode === "log" && rawMin > 0) {
    min = Math.max(min, rawMin * 0.42);
    max = Math.max(max, clampPositive(rawMax) * 1.08);
  }

  return { min, max };
}

export function getVisiblePriceScale(data, extras = [], scaleMode = "linear") {
  const pricePoints = (Array.isArray(data) ? data : [])
    .flatMap((row) => [row?.high, row?.low])
    .filter(Number.isFinite);
  (Array.isArray(extras) ? extras : []).forEach((value) => {
    const values = Array.isArray(value) ? value : [value];
    values.forEach((item) => {
      if (Number.isFinite(item)) pricePoints.push(item);
    });
  });

  if (!pricePoints.length) return { min: 0, max: 1 };
  return getPaddedPriceRange(
    Math.min(...pricePoints),
    Math.max(...pricePoints),
    scaleMode,
  );
}

export function shouldHandlePriceAxisInteraction(mode) {
  return mode === "manual_locked";
}

export function resolveLegacyMainChartAutoScaleRange(
  data,
  overlayValues = [],
  scaleMode = "linear",
) {
  const pricePoints = (Array.isArray(data) ? data : [])
    .flatMap((row) => [row?.high, row?.low])
    .filter(Number.isFinite);

  if (!pricePoints.length) return { min: 0, max: 1 };

  const rawMin = Math.min(...pricePoints);
  const rawMax = Math.max(...pricePoints);
  const candleRange = Math.max(rawMax - rawMin, Math.abs(rawMax) * 0.01, 1);
  const reasonableMin = rawMin - candleRange * 2;
  const reasonableMax = rawMax + candleRange * 2;
  (Array.isArray(overlayValues) ? overlayValues : []).forEach((series) => {
    const values = Array.isArray(series) ? series : [series];
    values.forEach((value) => {
      if (Number.isFinite(value) && value >= reasonableMin && value <= reasonableMax) {
        pricePoints.push(value);
      }
    });
  });

  const resolvedRawMin = Math.min(...pricePoints);
  const resolvedRawMax = Math.max(...pricePoints);
  return getPaddedPriceRange(resolvedRawMin, resolvedRawMax, scaleMode);
}
