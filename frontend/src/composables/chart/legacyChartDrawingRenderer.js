import { LEGACY_CHART_PAD } from "./legacyChartCoordinates";

export const LEGACY_FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
const DRAWING_LINE_STYLES = {
  solid: [],
  dash: [6, 4],
  dot: [2, 4],
};

export function getDrawingDash(drawing, fallback = []) {
  return drawing?.lineStyle && DRAWING_LINE_STYLES[drawing.lineStyle]
    ? DRAWING_LINE_STYLES[drawing.lineStyle]
    : fallback;
}

export function getDrawingWidth(drawing, fallback = 1.2) {
  return Number.isFinite(Number(drawing?.lineWidth)) ? Number(drawing.lineWidth) : fallback;
}

export function getDrawingFill(
  drawing,
  fallbackColor = "#9b6dff",
  fallbackOpacity = 0.12,
) {
  return {
    color: drawing?.color || fallbackColor,
    opacity: Number.isFinite(Number(drawing?.fillOpacity))
      ? Number(drawing.fillOpacity)
      : fallbackOpacity,
  };
}

export function withOpacity(color, opacity) {
  if (!color) return `rgba(155,109,255,${opacity})`;
  const normalized = Math.max(0, Math.min(opacity, 1));
  if (color.startsWith("#")) {
    const hex = color.slice(1);
    const full =
      hex.length === 3 ? hex.split("").map((char) => `${char}${char}`).join("") : hex;
    if (full.length === 6) {
      return `rgba(${parseInt(full.slice(0, 2), 16)},${parseInt(full.slice(2, 4), 16)},${parseInt(full.slice(4, 6), 16)},${normalized})`;
    }
  }
  if (color.startsWith("rgb")) {
    const parts = color
      .replace(/rgba?\(|\)/g, "")
      .split(",")
      .map((part) => part.trim())
      .slice(0, 3);
    if (parts.length === 3) return `rgba(${parts.join(",")},${normalized})`;
  }
  return color;
}

export function createLegacyDrawingRenderer({
  xForAbsoluteIndex,
  pad = LEGACY_CHART_PAD,
} = {}) {
  const drawTrendLine = (
    ctx,
    layout,
    drawing,
    scale,
    color = "#00d4ff",
    dash = [],
  ) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = getDrawingWidth(drawing, 1.5);
    ctx.setLineDash(dash);
    ctx.beginPath();
    ctx.moveTo(xForAbsoluteIndex(layout, drawing.startIndex), scale(drawing.startPrice));
    ctx.lineTo(xForAbsoluteIndex(layout, drawing.endIndex), scale(drawing.endPrice));
    ctx.stroke();
    ctx.setLineDash([]);
  };

  const drawArrowLine = (
    ctx,
    layout,
    drawing,
    scale,
    color = "#7be7ff",
    dash = [],
  ) => {
    const startX = xForAbsoluteIndex(layout, drawing.startIndex);
    const endX = xForAbsoluteIndex(layout, drawing.endIndex);
    const startY = scale(drawing.startPrice);
    const endY = scale(drawing.endPrice);
    const angle = Math.atan2(endY - startY, endX - startX);
    const headLength = 10;
    drawTrendLine(ctx, layout, drawing, scale, color, dash);
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = getDrawingWidth(drawing, 1.6);
    ctx.beginPath();
    ctx.moveTo(endX, endY);
    ctx.lineTo(
      endX - headLength * Math.cos(angle - Math.PI / 6),
      endY - headLength * Math.sin(angle - Math.PI / 6),
    );
    ctx.moveTo(endX, endY);
    ctx.lineTo(
      endX - headLength * Math.cos(angle + Math.PI / 6),
      endY - headLength * Math.sin(angle + Math.PI / 6),
    );
    ctx.stroke();
    ctx.restore();
  };

  const drawFib = (
    ctx,
    layout,
    drawing,
    scale,
    width,
    color = "#ffd166",
    dash = [],
  ) => {
    const x1 = xForAbsoluteIndex(layout, drawing.startIndex);
    const x2 = xForAbsoluteIndex(layout, drawing.endIndex);
    const leftX = Math.min(x1, x2);
    const rightX = Math.max(x1, x2);
    const high = Math.max(drawing.startPrice, drawing.endPrice);
    const low = Math.min(drawing.startPrice, drawing.endPrice);
    const direction = drawing.endPrice >= drawing.startPrice ? 1 : -1;
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.font = "9px JetBrains Mono";
    ctx.lineWidth = getDrawingWidth(drawing, 1.2);
    ctx.setLineDash(dash);
    LEGACY_FIB_LEVELS.forEach((level) => {
      const price =
        direction >= 0 ? high - (high - low) * level : low + (high - low) * level;
      const y = scale(price);
      ctx.beginPath();
      ctx.moveTo(leftX, y);
      ctx.lineTo(rightX, y);
      ctx.stroke();
      ctx.fillText(
        `${Math.round(level * 100)}% ${price.toFixed(2)}`,
        width - pad.right + 3,
        y + 3,
      );
    });
    ctx.setLineDash([]);
  };

  const drawVerticalLine = (
    ctx,
    x,
    height,
    color = "#ff8c42",
    dash = [5, 3],
    lineWidth = 1,
  ) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.setLineDash(dash);
    ctx.beginPath();
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, height - pad.bottom);
    ctx.stroke();
    ctx.setLineDash([]);
  };

  const drawRectZone = (
    ctx,
    xAtAbsolute,
    drawing,
    scale,
    strokeStyle,
    fillStyle,
    width,
    dash = [6, 4],
  ) => {
    const x1 = xAtAbsolute(drawing.startIndex);
    const x2 = xAtAbsolute(drawing.endIndex);
    const y1 = scale(drawing.startPrice);
    const y2 = scale(drawing.endPrice);
    const left = Math.min(x1, x2);
    const top = Math.min(y1, y2);
    ctx.fillStyle = fillStyle;
    ctx.strokeStyle = strokeStyle;
    ctx.lineWidth = getDrawingWidth(drawing, 1.2);
    ctx.setLineDash(dash);
    ctx.fillRect(left, top, Math.abs(x2 - x1), Math.abs(y2 - y1));
    ctx.strokeRect(left, top, Math.abs(x2 - x1), Math.abs(y2 - y1));
    ctx.setLineDash([]);
    const high = Math.max(drawing.startPrice, drawing.endPrice);
    const low = Math.min(drawing.startPrice, drawing.endPrice);
    ctx.fillStyle = strokeStyle;
    ctx.font = "9px JetBrains Mono";
    ctx.fillText(`${high.toFixed(2)} / ${low.toFixed(2)}`, width - pad.right + 2, top + 10);
  };

  const drawMeasureTool = (
    ctx,
    xAtAbsolute,
    drawing,
    scale,
    width,
    strokeStyle = "#00d4ff",
    dash = [4, 3],
  ) => {
    const x1 = xAtAbsolute(drawing.startIndex);
    const x2 = xAtAbsolute(drawing.endIndex);
    const y1 = scale(drawing.startPrice);
    const y2 = scale(drawing.endPrice);
    const left = Math.min(x1, x2);
    const top = Math.min(y1, y2);
    const bars = Math.abs(drawing.endIndex - drawing.startIndex) + 1;
    const priceChange = drawing.endPrice - drawing.startPrice;
    const pctChange = drawing.startPrice ? (priceChange / drawing.startPrice) * 100 : 0;
    ctx.strokeStyle = strokeStyle;
    ctx.fillStyle = "rgba(0,212,255,0.08)";
    ctx.lineWidth = getDrawingWidth(drawing, 1);
    ctx.setLineDash(dash);
    ctx.fillRect(left, top, Math.abs(x2 - x1), Math.abs(y2 - y1));
    ctx.strokeRect(left, top, Math.abs(x2 - x1), Math.abs(y2 - y1));
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = strokeStyle;
    ctx.font = "9px JetBrains Mono";
    ctx.fillText(
      `${bars} bars | ${priceChange >= 0 ? "+" : ""}${priceChange.toFixed(2)} | ${pctChange >= 0 ? "+" : ""}${pctChange.toFixed(2)}%`,
      Math.min(left + 6, width - pad.right - 150),
      top + 12,
    );
  };

  const drawNote = (ctx, xAtAbsolute, drawing, scale, width) => {
    const x = xAtAbsolute(drawing.index);
    const y = scale(drawing.price);
    const text = drawing.text || drawing.label || "註記";
    const color = drawing.color || "#ffd166";
    const { opacity } = getDrawingFill(drawing, color, 0.88);
    const paddingX = 8;
    const paddingY = 5;
    ctx.save();
    ctx.font = "10px JetBrains Mono";
    const textWidth = Math.min(180, Math.max(44, ctx.measureText(text).width + paddingX * 2));
    const boxWidth = Math.min(textWidth, width - pad.right - 12);
    const boxHeight = 22;
    const left = Math.min(
      Math.max(pad.left, x + 8),
      width - pad.right - boxWidth - 6,
    );
    const top = Math.max(pad.top + 6, y - boxHeight - 8);
    ctx.fillStyle = `rgba(8,12,18,${Math.min(opacity, 0.95)})`;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.fillRect(left, top, boxWidth, boxHeight);
    ctx.strokeRect(left, top, boxWidth, boxHeight);
    ctx.fillStyle = color;
    ctx.fillText(text, left + paddingX, top + paddingY + 8);
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(left, top + boxHeight);
    ctx.stroke();
    ctx.restore();
  };

  const drawDrawingLabel = (ctx, text, x, y, color) => {
    if (!text) return;
    ctx.save();
    ctx.font = "9px JetBrains Mono";
    const boxWidth = ctx.measureText(text).width + 10;
    ctx.fillStyle = "rgba(8,12,18,0.88)";
    ctx.strokeStyle = color;
    ctx.fillRect(x, y - 11, boxWidth, 14);
    ctx.strokeRect(x, y - 11, boxWidth, 14);
    ctx.fillStyle = color;
    ctx.fillText(text, x + 5, y);
    ctx.restore();
  };

  return {
    drawArrowLine,
    drawDrawingLabel,
    drawFib,
    drawMeasureTool,
    drawNote,
    drawRectZone,
    drawTrendLine,
    drawVerticalLine,
  };
}
