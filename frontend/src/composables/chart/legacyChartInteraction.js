import { clamp } from "./legacyChartCoordinates";

export function computePannedStartIndex({
  startIndex,
  deltaBars,
  totalCount,
  visibleCount,
}) {
  return clamp(
    startIndex + deltaBars,
    0,
    Math.max(0, totalCount - visibleCount),
  );
}

export function computeZoomViewport({
  startIndex,
  currentVisibleCount,
  nextVisibleCount,
  minimumVisibleCount,
  totalCount,
  anchorRatio = 0.5,
}) {
  const visibleCount = clamp(nextVisibleCount, minimumVisibleCount, totalCount);
  if (visibleCount === currentVisibleCount) {
    return { startIndex, visibleCount, changed: false };
  }
  const anchorIndex = startIndex
    + Math.round(anchorRatio * Math.max(currentVisibleCount - 1, 0));
  return {
    startIndex: clamp(
      Math.round(anchorIndex - anchorRatio * Math.max(visibleCount - 1, 0)),
      0,
      Math.max(0, totalCount - visibleCount),
    ),
    visibleCount,
    changed: true,
  };
}

export function buildLegacyCrosshairPayload({
  info,
  previousRow,
  formatPrice,
  formatVolume,
}) {
  const referenceClose = previousRow?.close ?? info.row.open ?? info.row.close;
  const change = (info.row.close ?? 0) - (referenceClose ?? 0);
  const changePct = referenceClose ? (change / referenceClose) * 100 : 0;
  return {
    visible: true,
    canvasX: info.x,
    canvasY: info.y,
    date: info.row.date,
    hoverPrice: formatPrice(info.price),
    open: formatPrice(info.row.open),
    high: formatPrice(info.row.high),
    low: formatPrice(info.row.low),
    close: formatPrice(info.row.close),
    change: `${change >= 0 ? "+" : ""}${formatPrice(change)}`,
    changePct: `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`,
    volume: formatVolume(info.row.volume),
    absoluteIndex: info.absoluteIndex,
  };
}
