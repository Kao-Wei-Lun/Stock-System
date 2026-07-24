import { clamp, LEGACY_CHART_PAD } from "./legacyChartCoordinates";

const INTRADAY_INTERVALS = new Set(["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]);
const pad2 = (value) => String(value).padStart(2, "0");

export function parseLegacyDateValue(value) {
  const normalized =
    typeof value === "string" && value.includes(" ") ? value.replace(" ", "T") : value;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function isLegacyIntradayInterval(interval) {
  return INTRADAY_INTERVALS.has(String(interval || "").toLowerCase());
}

export function isSameLegacyCalendarDay(left, right) {
  const leftDate = parseLegacyDateValue(left);
  const rightDate = parseLegacyDateValue(right);
  if (!leftDate || !rightDate) return false;
  return leftDate.getFullYear() === rightDate.getFullYear()
    && leftDate.getMonth() === rightDate.getMonth()
    && leftDate.getDate() === rightDate.getDate();
}

export function formatLegacyAxisDateLabel(
  value,
  { rangeDays = 0, interval = "1d", includeDate = false } = {},
) {
  const date = parseLegacyDateValue(value);
  if (!date) return String(value || "").slice(5);
  const dateLabel =
    `${String(date.getFullYear()).slice(2)}/${pad2(date.getMonth() + 1)}/${pad2(date.getDate())}`;
  if (isLegacyIntradayInterval(interval)) {
    const timeLabel = `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
    return includeDate ? `${dateLabel} ${timeLabel}` : timeLabel;
  }
  if (rangeDays >= 730) {
    return `${String(date.getFullYear()).slice(2)}/${pad2(date.getMonth() + 1)}`;
  }
  return dateLabel;
}

export function getLegacyDataRangeDays(data) {
  if (!data?.length) return 0;
  const first = parseLegacyDateValue(data[0]?.date);
  const last = parseLegacyDateValue(data[data.length - 1]?.date);
  if (!first || !last) return 0;
  return Math.abs((last - first) / 86400000);
}

export function getLegacyTimeTickIndices(data, targetTickCount = 6) {
  if (!data.length) return [];
  const indices = new Set([0, data.length - 1]);
  const step = Math.max(
    1,
    Math.floor((data.length - 1) / Math.max(targetTickCount - 1, 1)),
  );
  for (let index = 0; index < data.length; index += step) indices.add(index);
  return [...indices].sort((left, right) => left - right);
}

export function resolveLegacyCrosshairMarker({
  crosshair,
  viewportStartIndex,
  data,
  layout,
  interval = "1d",
}) {
  const absoluteIndex = crosshair?.absoluteIndex;
  if (!crosshair?.visible || !Number.isInteger(absoluteIndex)) return null;
  if (
    absoluteIndex < viewportStartIndex
    || absoluteIndex >= viewportStartIndex + data.length
  ) {
    return null;
  }
  const localIndex = absoluteIndex - viewportStartIndex;
  return {
    absoluteIndex,
    localIndex,
    x: layout.barX(localIndex),
    dateLabel: formatLegacyAxisDateLabel(data[localIndex]?.date, {
      rangeDays: getLegacyDataRangeDays(data),
      interval,
      includeDate: isLegacyIntradayInterval(interval),
    }),
  };
}

export function drawLegacyCrosshairGuide(
  ctx,
  x,
  top,
  bottom,
  dateLabel = "",
  width = 0,
  pad = LEGACY_CHART_PAD,
) {
  ctx.save();
  ctx.strokeStyle = "rgba(255,209,102,0.95)";
  ctx.lineWidth = 1;
  ctx.setLineDash([5, 3]);
  ctx.beginPath();
  ctx.moveTo(x, top);
  ctx.lineTo(x, bottom);
  ctx.stroke();
  ctx.setLineDash([]);

  if (dateLabel && width) {
    const labelWidth = Math.max(46, dateLabel.length * 8 + 10);
    const left = Math.min(
      Math.max(pad.left, x - labelWidth / 2),
      width - pad.right - labelWidth,
    );
    ctx.fillStyle = "rgba(255,209,102,0.14)";
    ctx.strokeStyle = "rgba(255,209,102,0.88)";
    ctx.fillRect(left, 2, labelWidth, 14);
    ctx.strokeRect(left, 2, labelWidth, 14);
    ctx.fillStyle = "#ffd166";
    ctx.font = "9px JetBrains Mono";
    ctx.fillText(dateLabel, left + 5, 12);
  }
  ctx.restore();
}

export function drawLegacyHorizontalCrosshairGuide(
  ctx,
  y,
  left,
  right,
  label = "",
  width = 0,
  top = LEGACY_CHART_PAD.top,
  bottom = 0,
) {
  ctx.save();
  ctx.strokeStyle = "rgba(255,209,102,0.95)";
  ctx.lineWidth = 1;
  ctx.setLineDash([5, 3]);
  ctx.beginPath();
  ctx.moveTo(left, y);
  ctx.lineTo(right, y);
  ctx.stroke();
  ctx.setLineDash([]);

  if (label && width) {
    const labelWidth = Math.max(56, label.length * 8 + 10);
    const boxLeft = Math.max(right + 4, width - labelWidth - 4);
    const boxTop = clamp(y - 8, top + 2, Math.max(top + 2, bottom - 16));
    ctx.fillStyle = "rgba(255,209,102,0.14)";
    ctx.strokeStyle = "rgba(255,209,102,0.88)";
    ctx.fillRect(boxLeft, boxTop, labelWidth, 14);
    ctx.strokeRect(boxLeft, boxTop, labelWidth, 14);
    ctx.fillStyle = "#ffd166";
    ctx.font = "9px JetBrains Mono";
    ctx.fillText(label, boxLeft + 5, boxTop + 10);
  }
  ctx.restore();
}
