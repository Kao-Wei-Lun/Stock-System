import { onBeforeUnmount, shallowRef, watch } from "vue";
import { createSeriesMarkers } from "lightweight-charts";

const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
const DRAWING_HIT_TOLERANCE = 10;

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function normalizeIndexPair(startIndex, endIndex, maxIndex) {
  const lower = Math.min(startIndex, endIndex);
  const upper = Math.max(startIndex, endIndex);
  let adjust = 0;

  if (lower < 0) adjust = -lower;
  if (upper + adjust > maxIndex) adjust += maxIndex - (upper + adjust);

  return {
    startIndex: clamp(startIndex + adjust, 0, maxIndex),
    endIndex: clamp(endIndex + adjust, 0, maxIndex),
  };
}

function formatPrice(value) {
  if (!Number.isFinite(Number(value))) return "—";
  return Number(value).toFixed(Math.abs(Number(value)) >= 1000 ? 0 : 2);
}

function toChartTime(dateString) {
  if (!dateString) return null;
  const normalized = String(dateString).trim();
  const dateOnlyMatch = normalized.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (dateOnlyMatch) {
    return {
      year: Number(dateOnlyMatch[1]),
      month: Number(dateOnlyMatch[2]),
      day: Number(dateOnlyMatch[3]),
    };
  }
  const parsed = new Date(normalized.includes(" ") ? normalized.replace(" ", "T") : normalized);
  if (Number.isNaN(parsed.getTime())) return null;
  return Math.floor(parsed.getTime() / 1000);
}

function createSvgNode(name, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attrs).forEach(([key, value]) => {
    if (value == null) return;
    node.setAttribute(key, String(value));
  });
  return node;
}

function getLineDash(style) {
  if (style === "dash") return "6 4";
  if (style === "dot") return "2 4";
  return "";
}

function getDrawingStroke(drawing, fallback) {
  return drawing?.color || fallback;
}

function getDrawingLineWidth(drawing, fallback = 1.5) {
  const width = Number(drawing?.lineWidth);
  return Number.isFinite(width) && width > 0 ? width : fallback;
}

function getDrawingFillOpacity(drawing, fallback = 0.12) {
  const value = Number(drawing?.fillOpacity);
  return Number.isFinite(value) ? clamp(value, 0.02, 0.95) : fallback;
}

function toRgba(hex, alpha) {
  if (!hex || typeof hex !== "string" || !hex.startsWith("#")) {
    return `rgba(123, 231, 255, ${alpha})`;
  }
  const normalized = hex.length === 4
    ? `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`
    : hex;
  const red = Number.parseInt(normalized.slice(1, 3), 16);
  const green = Number.parseInt(normalized.slice(3, 5), 16);
  const blue = Number.parseInt(normalized.slice(5, 7), 16);
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
}

function distanceToSegment(pointX, pointY, x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (!dx && !dy) return Math.hypot(pointX - x1, pointY - y1);
  const t = clamp(((pointX - x1) * dx + (pointY - y1) * dy) / (dx * dx + dy * dy), 0, 1);
  const projX = x1 + t * dx;
  const projY = y1 + t * dy;
  return Math.hypot(pointX - projX, pointY - projY);
}

export function useLWCDrawings({
  chartApi,
  mainSeries,
  props,
  emit,
  scheduleHostSync,
  resetView,
}) {
  const overlayRoot = shallowRef(null);
  const overlaySvg = shallowRef(null);
  const mainPaneElement = shallowRef(null);
  const resizeObserver = shallowRef(null);
  const markersApi = shallowRef(null);
  const priceLines = shallowRef([]);
  const visibleRangeUnsubscribe = shallowRef(null);
  const renderFrame = shallowRef(null);
  const draftDrawing = shallowRef(null);

  const dragState = {
    drawingId: null,
    mode: null,
    startAbsoluteIndex: 0,
    startPrice: 0,
    originDrawing: null,
  };

  function clearRenderFrame() {
    if (renderFrame.value != null) {
      window.cancelAnimationFrame(renderFrame.value);
      renderFrame.value = null;
    }
  }

  function getPaneElement() {
    return chartApi.value?.panes?.()?.[0]?.getHTMLElement?.() || null;
  }

  function getOverlayBounds() {
    const pane = mainPaneElement.value;
    return pane
      ? { width: Math.max(1, pane.clientWidth), height: Math.max(1, pane.clientHeight) }
      : { width: 1, height: 1 };
  }

  function xForAbsoluteIndex(index) {
    const coordinate = chartApi.value?.timeScale?.().logicalToCoordinate?.(index);
    return Number.isFinite(coordinate) ? coordinate : null;
  }

  function yForPrice(price) {
    const coordinate = mainSeries.value?.priceToCoordinate?.(price);
    return Number.isFinite(coordinate) ? coordinate : null;
  }

  function getPointerInfo(event) {
    const pane = mainPaneElement.value;
    const totalRows = Array.isArray(props.ohlcData) ? props.ohlcData.length : 0;
    if (!pane || !mainSeries.value || !totalRows) return null;

    const rect = pane.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    const logical = chartApi.value?.timeScale?.().coordinateToLogical?.(x);
    if (logical == null) return null;

    const absoluteIndex = clamp(Math.round(logical), 0, totalRows - 1);
    const row = props.ohlcData[absoluteIndex];
    const price = mainSeries.value.coordinateToPrice?.(y);
    if (!row) return null;

    return {
      x,
      y,
      logical,
      absoluteIndex,
      row,
      price: Number.isFinite(price) ? price : Number(row.close ?? row.open ?? 0),
    };
  }

  function isDrawingHidden(drawing) {
    return Boolean(drawing?.hidden);
  }

  function isDrawingLocked(drawing) {
    return Boolean(drawing?.locked);
  }

  function isSelectedDrawing(drawing) {
    return Boolean(drawing?.id) && drawing.id === props.selectedDrawingId;
  }

  function getNoteBounds(drawing, width) {
    const anchorX = xForAbsoluteIndex(drawing.index);
    const anchorY = yForPrice(drawing.price);
    const text = drawing.text || drawing.label || "註記";
    const boxWidth = Math.min(180, Math.max(44, text.length * 7 + 16));
    const left = Math.min(Math.max(8, (anchorX ?? 8) + 8), width - boxWidth - 8);
    const top = Math.max(8, (anchorY ?? 24) - 30);
    return {
      anchorX,
      anchorY,
      left,
      top,
      boxWidth,
      boxHeight: 22,
      text,
    };
  }

  function getDrawingEditMode(drawing, info) {
    if (!drawing || !info) return null;
    if (drawing.type === "hline") return "price";
    if (drawing.type === "note") return "point";
    if (drawing.type === "vline" || drawing.type === "buy" || drawing.type === "sell") return "index";
    if (!["trendline", "arrow", "fib", "rect", "measure"].includes(drawing.type)) return null;

    const startX = xForAbsoluteIndex(drawing.startIndex);
    const endX = xForAbsoluteIndex(drawing.endIndex);
    const startY = yForPrice(drawing.startPrice);
    const endY = yForPrice(drawing.endPrice);

    if (startX == null || endX == null || startY == null || endY == null) return null;
    if (Math.hypot(info.x - startX, info.y - startY) <= DRAWING_HIT_TOLERANCE + 4) return "start";
    if (Math.hypot(info.x - endX, info.y - endY) <= DRAWING_HIT_TOLERANCE + 4) return "end";
    return "move";
  }

  function findDrawingAtPoint(info) {
    if (!info || !Array.isArray(props.drawings)) return null;
    const { width } = getOverlayBounds();

    for (let index = props.drawings.length - 1; index >= 0; index -= 1) {
      const drawing = props.drawings[index];
      if (!drawing || isDrawingHidden(drawing)) continue;

      if (drawing.type === "buy" || drawing.type === "sell") {
        const markerX = xForAbsoluteIndex(drawing.index);
        const markerPrice = drawing.type === "buy"
          ? props.ohlcData[drawing.index]?.low
          : props.ohlcData[drawing.index]?.high;
        const markerY = yForPrice(markerPrice);
        if (markerX != null && markerY != null && Math.hypot(info.x - markerX, info.y - markerY) <= DRAWING_HIT_TOLERANCE + 4) {
          return drawing;
        }
        continue;
      }

      if (drawing.type === "hline") {
        const y = yForPrice(drawing.price);
        if (y != null && Math.abs(y - info.y) <= DRAWING_HIT_TOLERANCE) return drawing;
        continue;
      }

      if (drawing.type === "vline") {
        const x = xForAbsoluteIndex(drawing.index);
        if (x != null && Math.abs(x - info.x) <= DRAWING_HIT_TOLERANCE) return drawing;
        continue;
      }

      if (drawing.type === "note") {
        const bounds = getNoteBounds(drawing, width);
        if (
          (bounds.anchorX != null && bounds.anchorY != null && Math.hypot(info.x - bounds.anchorX, info.y - bounds.anchorY) <= DRAWING_HIT_TOLERANCE + 4)
          || (
            info.x >= bounds.left - 4
            && info.x <= bounds.left + bounds.boxWidth + 4
            && info.y >= bounds.top - 4
            && info.y <= bounds.top + bounds.boxHeight + 4
          )
        ) {
          return drawing;
        }
        continue;
      }

      if (!["trendline", "arrow", "fib", "rect", "measure"].includes(drawing.type)) continue;
      const startX = xForAbsoluteIndex(drawing.startIndex);
      const endX = xForAbsoluteIndex(drawing.endIndex);
      const startY = yForPrice(drawing.startPrice);
      const endY = yForPrice(drawing.endPrice);
      if ([startX, endX, startY, endY].some((value) => value == null)) continue;

      const left = Math.min(startX, endX) - DRAWING_HIT_TOLERANCE;
      const right = Math.max(startX, endX) + DRAWING_HIT_TOLERANCE;
      const top = Math.min(startY, endY) - DRAWING_HIT_TOLERANCE;
      const bottom = Math.max(startY, endY) + DRAWING_HIT_TOLERANCE;

      if (drawing.type === "trendline" || drawing.type === "arrow") {
        if (distanceToSegment(info.x, info.y, startX, startY, endX, endY) <= DRAWING_HIT_TOLERANCE) return drawing;
        continue;
      }

      if (drawing.type === "fib") {
        if (info.x < left || info.x > right) continue;
        const high = Math.max(drawing.startPrice, drawing.endPrice);
        const low = Math.min(drawing.startPrice, drawing.endPrice);
        const direction = drawing.endPrice >= drawing.startPrice ? 1 : -1;
        for (const level of FIB_LEVELS) {
          const price = direction >= 0 ? high - (high - low) * level : low + (high - low) * level;
          const levelY = yForPrice(price);
          if (levelY != null && Math.abs(levelY - info.y) <= DRAWING_HIT_TOLERANCE) return drawing;
        }
        continue;
      }

      if (drawing.type === "rect") {
        if (info.x >= left && info.x <= right && info.y >= top && info.y <= bottom) return drawing;
        continue;
      }

      if (drawing.type === "measure") {
        if (
          distanceToSegment(info.x, info.y, startX, startY, endX, endY) <= DRAWING_HIT_TOLERANCE
          || (info.x >= left && info.x <= right && info.y >= top && info.y <= bottom)
        ) {
          return drawing;
        }
      }
    }

    return null;
  }

  function resetDragState() {
    dragState.drawingId = null;
    dragState.mode = null;
    dragState.startAbsoluteIndex = 0;
    dragState.startPrice = 0;
    dragState.originDrawing = null;
  }

  function startDrawingDrag(drawing, info) {
    if (!drawing || !info) return false;
    if (isDrawingLocked(drawing)) {
      emit("select-drawing", drawing.id);
      return false;
    }

    dragState.drawingId = drawing.id;
    dragState.mode = getDrawingEditMode(drawing, info);
    dragState.startAbsoluteIndex = info.absoluteIndex;
    dragState.startPrice = info.price;
    dragState.originDrawing = { ...drawing };

    if (!dragState.mode) {
      resetDragState();
      return false;
    }

    emit("select-drawing", drawing.id);
    emit("hide-crosshair");
    return true;
  }

  function updateDraggedDrawing(info) {
    const origin = dragState.originDrawing;
    const totalRows = Array.isArray(props.ohlcData) ? props.ohlcData.length : 0;
    if (!origin || !dragState.drawingId || !dragState.mode || !info || !totalRows) return;

    const maxIndex = totalRows - 1;
    const deltaBars = info.absoluteIndex - dragState.startAbsoluteIndex;
    const deltaPrice = info.price - dragState.startPrice;
    let patch = null;

    if (dragState.mode === "price") {
      patch = { price: info.price };
    } else if (dragState.mode === "index") {
      patch = { index: clamp((origin.index ?? 0) + deltaBars, 0, maxIndex) };
    } else if (dragState.mode === "point") {
      patch = {
        index: clamp((origin.index ?? 0) + deltaBars, 0, maxIndex),
        price: origin.price + deltaPrice,
      };
    } else if (dragState.mode === "start") {
      patch = {
        startIndex: clamp(info.absoluteIndex, 0, maxIndex),
        startPrice: info.price,
      };
    } else if (dragState.mode === "end") {
      patch = {
        endIndex: clamp(info.absoluteIndex, 0, maxIndex),
        endPrice: info.price,
      };
    } else if (dragState.mode === "move") {
      const shifted = normalizeIndexPair((origin.startIndex ?? 0) + deltaBars, (origin.endIndex ?? 0) + deltaBars, maxIndex);
      patch = {
        startIndex: shifted.startIndex,
        endIndex: shifted.endIndex,
        startPrice: origin.startPrice + deltaPrice,
        endPrice: origin.endPrice + deltaPrice,
      };
    }

    if (patch) {
      emit("update-drawing", dragState.drawingId, patch);
    }
  }

  function syncPriceLines() {
    priceLines.value.forEach((line) => {
      try {
        mainSeries.value?.removePriceLine?.(line);
      } catch (error) {
        console.error(error);
      }
    });
    priceLines.value = [];

    if (!mainSeries.value || !Array.isArray(props.drawings)) return;
    props.drawings
      .filter((drawing) => drawing?.type === "hline" && !isDrawingHidden(drawing) && Number.isFinite(Number(drawing.price)))
      .forEach((drawing) => {
        const priceLine = mainSeries.value.createPriceLine({
          price: Number(drawing.price),
          color: getDrawingStroke(drawing, "#f5a623"),
          lineWidth: getDrawingLineWidth(drawing, 1.2),
          lineStyle: drawing.lineStyle === "dot" ? 1 : drawing.lineStyle === "dash" ? 2 : 0,
          axisLabelVisible: true,
          title: drawing.label || "",
        });
        priceLines.value.push(priceLine);
      });
  }

  function syncMarkers() {
    if (!mainSeries.value || !Array.isArray(props.drawings)) return;
    const markers = props.drawings
      .filter((drawing) => (drawing?.type === "buy" || drawing?.type === "sell") && !isDrawingHidden(drawing))
      .map((drawing) => {
        const row = props.ohlcData?.[drawing.index];
        return row
          ? {
            time: toChartTime(row.date),
            position: drawing.type === "buy" ? "belowBar" : "aboveBar",
            color: drawing.type === "buy" ? "#00d9a3" : "#ff4d6a",
            shape: drawing.type === "buy" ? "arrowUp" : "arrowDown",
            text: drawing.label || (drawing.type === "buy" ? "Buy" : "Sell"),
          }
          : null;
      })
      .filter((marker) => marker?.time != null);

    try {
      if (typeof createSeriesMarkers === "function") {
        if (!markersApi.value) {
          markersApi.value = createSeriesMarkers(mainSeries.value, markers);
        } else {
          markersApi.value.setMarkers(markers);
        }
      } else if (typeof mainSeries.value?.setMarkers === "function") {
        mainSeries.value.setMarkers(markers);
      }
    } catch (error) {
      console.error(error);
    }
  }

  function appendText(parent, text, attrs = {}) {
    const node = createSvgNode("text", attrs);
    node.textContent = text;
    parent.appendChild(node);
    return node;
  }

  function renderInstitutionalOverlay(svg, width, height) {
    const overlay = props.institutionalOverlay;
    if (!overlay) return;

    const bandLow = Number(overlay.bandLow);
    const bandHigh = Number(overlay.bandHigh);
    const institutionPrice = Number(overlay.institutionPrice);
    const retailPrice = Number(overlay.retailPrice);

    if (Number.isFinite(bandLow) && Number.isFinite(bandHigh)) {
      const top = yForPrice(Math.max(bandLow, bandHigh));
      const bottom = yForPrice(Math.min(bandLow, bandHigh));
      if (top != null && bottom != null) {
        svg.appendChild(createSvgNode("rect", {
          x: 0,
          y: Math.min(top, bottom),
          width,
          height: Math.max(1, Math.abs(bottom - top)),
          fill: "rgba(255, 209, 102, 0.10)",
          stroke: "rgba(255, 209, 102, 0.46)",
          "stroke-width": 1,
          "stroke-dasharray": "6 4",
        }));
      }
    }

    [
      [institutionPrice, "#ffd166", "法"],
      [retailPrice, "#ff8c42", "散"],
    ].forEach(([price, color, prefix]) => {
      if (!Number.isFinite(price)) return;
      const y = yForPrice(price);
      if (y == null) return;
      svg.appendChild(createSvgNode("line", {
        x1: 0,
        x2: width,
        y1: y,
        y2: y,
        stroke: color,
        "stroke-width": 1,
        "stroke-dasharray": "5 3",
      }));
      appendText(svg, `${prefix} ${formatPrice(price)}`, {
        x: Math.max(8, width - 92),
        y: y - 4,
        fill: color,
        "font-size": 10,
        "font-family": "JetBrains Mono, monospace",
      });
    });

    const badgeLines = [
      overlay.label,
      [overlay.spotLabel, Number.isFinite(Number(overlay.basis)) ? `Basis ${Number(overlay.basis) >= 0 ? "+" : ""}${Number(overlay.basis).toFixed(2)}` : ""]
        .filter(Boolean)
        .join(" / "),
    ].filter(Boolean);

    if (!badgeLines.length) return;
    const badgeWidth = Math.min(width - 16, Math.max(170, badgeLines.reduce((max, line) => Math.max(max, line.length * 7.2), 0) + 16));
    const badgeHeight = 10 + badgeLines.length * 14;
    svg.appendChild(createSvgNode("rect", {
      x: 8,
      y: 8,
      width: badgeWidth,
      height: badgeHeight,
      fill: "rgba(13,20,32,0.82)",
      stroke: "rgba(255,209,102,0.34)",
      "stroke-width": 1,
      rx: 10,
      ry: 10,
    }));
    badgeLines.forEach((line, index) => {
      appendText(svg, line, {
        x: 16,
        y: 26 + index * 14,
        fill: index === 0 ? "#ffd166" : "#8ba3c0",
        "font-size": 10,
        "font-family": "JetBrains Mono, monospace",
      });
    });
  }

  function renderSelectedHandles(svg, points) {
    points
      .filter((point) => Number.isFinite(point?.x) && Number.isFinite(point?.y))
      .forEach((point) => {
        svg.appendChild(createSvgNode("circle", {
          cx: point.x,
          cy: point.y,
          r: 4,
          fill: "#ffffff",
          stroke: "rgba(8,12,18,0.9)",
          "stroke-width": 1,
        }));
      });
  }

  function renderDrawing(svg, drawing, width, height) {
    if (!drawing || isDrawingHidden(drawing)) return;
    const selected = isSelectedDrawing(drawing);
    const opacity = isDrawingLocked(drawing) ? 0.72 : 1;

    if (drawing.type === "vline") {
      const x = xForAbsoluteIndex(drawing.index);
      if (x == null) return;
      svg.appendChild(createSvgNode("line", {
        x1: x,
        x2: x,
        y1: 0,
        y2: height,
        stroke: getDrawingStroke(drawing, "#ff8c42"),
        "stroke-width": getDrawingLineWidth(drawing, 1.2),
        "stroke-dasharray": getLineDash(drawing.lineStyle || "dash"),
        opacity,
      }));
      if (selected) renderSelectedHandles(svg, [{ x, y: 24 }]);
      return;
    }

    if (drawing.type === "note") {
      const bounds = getNoteBounds(drawing, width);
      if (bounds.anchorX == null || bounds.anchorY == null) return;
      const color = getDrawingStroke(drawing, "#ffd166");
      svg.appendChild(createSvgNode("rect", {
        x: bounds.left,
        y: bounds.top,
        width: bounds.boxWidth,
        height: bounds.boxHeight,
        rx: 8,
        ry: 8,
        fill: toRgba("#080c12", getDrawingFillOpacity(drawing, 0.88)),
        stroke: color,
        "stroke-width": 1,
        opacity,
      }));
      appendText(svg, bounds.text, {
        x: bounds.left + 8,
        y: bounds.top + 14,
        fill: color,
        "font-size": 10,
        "font-family": "JetBrains Mono, monospace",
        opacity,
      });
      svg.appendChild(createSvgNode("line", {
        x1: bounds.anchorX,
        y1: bounds.anchorY,
        x2: bounds.left,
        y2: bounds.top + bounds.boxHeight,
        stroke: color,
        "stroke-width": 1,
        opacity,
      }));
      if (selected) renderSelectedHandles(svg, [{ x: bounds.anchorX, y: bounds.anchorY }]);
      return;
    }

    if (!["trendline", "arrow", "fib", "rect", "measure"].includes(drawing.type)) return;
    const startX = xForAbsoluteIndex(drawing.startIndex);
    const endX = xForAbsoluteIndex(drawing.endIndex);
    const startY = yForPrice(drawing.startPrice);
    const endY = yForPrice(drawing.endPrice);
    if ([startX, endX, startY, endY].some((value) => value == null)) return;

    const color = getDrawingStroke(drawing, drawing.type === "fib" ? "#ffd166" : "#00d4ff");
    const lineWidth = getDrawingLineWidth(drawing, drawing.type === "measure" ? 1.1 : 1.5);
    const dashArray = getLineDash(drawing.lineStyle || (drawing.type === "fib" || drawing.type === "rect" || drawing.type === "measure" ? "dash" : "solid"));

    if (drawing.type === "trendline" || drawing.type === "arrow") {
      svg.appendChild(createSvgNode("line", {
        x1: startX,
        y1: startY,
        x2: endX,
        y2: endY,
        stroke: color,
        "stroke-width": lineWidth,
        "stroke-dasharray": dashArray,
        opacity,
      }));

      if (drawing.type === "arrow") {
        const angle = Math.atan2(endY - startY, endX - startX);
        const headLength = 10;
        const arrowPath = [
          `M ${endX} ${endY}`,
          `L ${endX - headLength * Math.cos(angle - Math.PI / 6)} ${endY - headLength * Math.sin(angle - Math.PI / 6)}`,
          `M ${endX} ${endY}`,
          `L ${endX - headLength * Math.cos(angle + Math.PI / 6)} ${endY - headLength * Math.sin(angle + Math.PI / 6)}`,
        ].join(" ");
        svg.appendChild(createSvgNode("path", {
          d: arrowPath,
          stroke: color,
          "stroke-width": lineWidth,
          fill: "none",
          opacity,
        }));
      }

      if (selected) renderSelectedHandles(svg, [{ x: startX, y: startY }, { x: endX, y: endY }]);
      return;
    }

    if (drawing.type === "fib") {
      const leftX = Math.min(startX, endX);
      const rightX = Math.max(startX, endX);
      const high = Math.max(drawing.startPrice, drawing.endPrice);
      const low = Math.min(drawing.startPrice, drawing.endPrice);
      const direction = drawing.endPrice >= drawing.startPrice ? 1 : -1;

      FIB_LEVELS.forEach((level) => {
        const price = direction >= 0 ? high - (high - low) * level : low + (high - low) * level;
        const levelY = yForPrice(price);
        if (levelY == null) return;
        svg.appendChild(createSvgNode("line", {
          x1: leftX,
          y1: levelY,
          x2: rightX,
          y2: levelY,
          stroke: color,
          "stroke-width": lineWidth,
          "stroke-dasharray": dashArray,
          opacity,
        }));
        appendText(svg, `${Math.round(level * 100)}% ${formatPrice(price)}`, {
          x: Math.max(8, width - 112),
          y: levelY - 4,
          fill: color,
          "font-size": 9,
          "font-family": "JetBrains Mono, monospace",
          opacity,
        });
      });

      if (selected) renderSelectedHandles(svg, [{ x: startX, y: startY }, { x: endX, y: endY }]);
      return;
    }

    if (drawing.type === "rect") {
      const left = Math.min(startX, endX);
      const top = Math.min(startY, endY);
      const zoneWidth = Math.abs(endX - startX);
      const zoneHeight = Math.abs(endY - startY);
      svg.appendChild(createSvgNode("rect", {
        x: left,
        y: top,
        width: zoneWidth,
        height: zoneHeight,
        fill: toRgba(color, getDrawingFillOpacity(drawing, 0.12)),
        stroke: color,
        "stroke-width": lineWidth,
        "stroke-dasharray": dashArray,
        opacity,
      }));
      appendText(svg, `${formatPrice(Math.max(drawing.startPrice, drawing.endPrice))} / ${formatPrice(Math.min(drawing.startPrice, drawing.endPrice))}`, {
        x: Math.max(8, width - 128),
        y: top + 12,
        fill: color,
        "font-size": 9,
        "font-family": "JetBrains Mono, monospace",
        opacity,
      });
      if (selected) renderSelectedHandles(svg, [{ x: startX, y: startY }, { x: endX, y: endY }]);
      return;
    }

    if (drawing.type === "measure") {
      const left = Math.min(startX, endX);
      const top = Math.min(startY, endY);
      const boxWidth = Math.abs(endX - startX);
      const boxHeight = Math.abs(endY - startY);
      const bars = Math.abs((drawing.endIndex ?? 0) - (drawing.startIndex ?? 0)) + 1;
      const priceChange = Number(drawing.endPrice ?? 0) - Number(drawing.startPrice ?? 0);
      const pctChange = drawing.startPrice ? (priceChange / drawing.startPrice) * 100 : 0;

      svg.appendChild(createSvgNode("rect", {
        x: left,
        y: top,
        width: boxWidth,
        height: boxHeight,
        fill: "rgba(0,212,255,0.08)",
        stroke: color,
        "stroke-width": lineWidth,
        "stroke-dasharray": dashArray,
        opacity,
      }));
      svg.appendChild(createSvgNode("line", {
        x1: startX,
        y1: startY,
        x2: endX,
        y2: endY,
        stroke: color,
        "stroke-width": lineWidth,
        "stroke-dasharray": dashArray,
        opacity,
      }));
      appendText(svg, `${bars} bars | ${priceChange >= 0 ? "+" : ""}${formatPrice(priceChange)} | ${pctChange >= 0 ? "+" : ""}${pctChange.toFixed(2)}%`, {
        x: Math.min(left + 6, Math.max(8, width - 172)),
        y: top + 12,
        fill: color,
        "font-size": 9,
        "font-family": "JetBrains Mono, monospace",
        opacity,
      });
      if (selected) renderSelectedHandles(svg, [{ x: startX, y: startY }, { x: endX, y: endY }]);
    }
  }

  function renderOverlay() {
    clearRenderFrame();
    if (!overlaySvg.value) return;
    const { width, height } = getOverlayBounds();
    overlaySvg.value.setAttribute("viewBox", `0 0 ${width} ${height}`);
    overlaySvg.value.setAttribute("width", String(width));
    overlaySvg.value.setAttribute("height", String(height));
    overlaySvg.value.replaceChildren();

    renderInstitutionalOverlay(overlaySvg.value, width, height);
    (props.drawings || []).forEach((drawing) => renderDrawing(overlaySvg.value, drawing, width, height));
    if (draftDrawing.value) {
      renderDrawing(overlaySvg.value, { ...draftDrawing.value, color: "#7be7ff" }, width, height);
    }
  }

  function scheduleRender() {
    clearRenderFrame();
    renderFrame.value = window.requestAnimationFrame(() => {
      renderOverlay();
      syncMarkers();
      syncPriceLines();
    });
  }

  function handlePaneMouseDown(event) {
    if (event.button !== 0) return;
    const info = getPointerInfo(event);
    if (!info) return;

    if (props.activeTool === "cursor") {
      const hitDrawing = findDrawingAtPoint(info);
      if (hitDrawing) {
        event.preventDefault();
        event.stopPropagation();
        startDrawingDrag(hitDrawing, info);
      }
      return;
    }

    if (props.activeTool !== "boxzoom") {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  function handlePaneClick(event) {
    const info = getPointerInfo(event);
    if (!info) return;

    if (props.activeTool === "cursor") {
      const hitDrawing = findDrawingAtPoint(info);
      emit("select-drawing", hitDrawing?.id || null);
      scheduleRender();
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    if (props.activeTool === "hline") {
      emit("add-horizontal-line", info.price);
      return;
    }

    if (props.activeTool === "vline") {
      emit("add-drawing", { type: "vline", index: info.absoluteIndex, price: info.price });
      return;
    }

    if (props.activeTool === "note") {
      emit("add-drawing", { type: "note", index: info.absoluteIndex, price: info.price });
      scheduleRender();
      return;
    }

    const toolTypeMap = {
      tline: "trendline",
      arrow: "arrow",
      fib: "fib",
      rect: "rect",
      measure: "measure",
    };
    const draftType = toolTypeMap[props.activeTool];
    if (!draftType) return;

    if (!draftDrawing.value || draftDrawing.value.type !== draftType) {
      draftDrawing.value = {
        type: draftType,
        startIndex: info.absoluteIndex,
        endIndex: info.absoluteIndex,
        startPrice: info.price,
        endPrice: info.price,
      };
    } else {
      emit("add-drawing", {
        ...draftDrawing.value,
        endIndex: info.absoluteIndex,
        endPrice: info.price,
      });
      draftDrawing.value = null;
    }

    scheduleRender();
  }

  function handlePaneDoubleClick(event) {
    if (props.activeTool !== "cursor") return;
    event.preventDefault();
    event.stopPropagation();
    resetView?.();
  }

  function handlePaneMouseMove(event) {
    const info = getPointerInfo(event);
    if (!info) return;

    if (dragState.mode) {
      event.preventDefault();
      event.stopPropagation();
      updateDraggedDrawing(info);
      emit("hide-crosshair");
      scheduleRender();
      return;
    }

    if (
      draftDrawing.value
      && ["trendline", "arrow", "fib", "rect", "measure"].includes(draftDrawing.value.type)
    ) {
      draftDrawing.value = {
        ...draftDrawing.value,
        endIndex: info.absoluteIndex,
        endPrice: info.price,
      };
      scheduleRender();
    }
  }

  function handleWindowMouseUp() {
    if (!dragState.mode) return;
    resetDragState();
    emit("hide-crosshair");
    scheduleRender();
  }

  function handleVisibleRangeChange() {
    scheduleRender();
  }

  function teardownPaneEvents() {
    resizeObserver.value?.disconnect();
    resizeObserver.value = null;

    visibleRangeUnsubscribe.value?.();
    visibleRangeUnsubscribe.value = null;

    if (mainPaneElement.value) {
      mainPaneElement.value.removeEventListener("mousedown", handlePaneMouseDown, true);
      mainPaneElement.value.removeEventListener("click", handlePaneClick, true);
      mainPaneElement.value.removeEventListener("dblclick", handlePaneDoubleClick, true);
      mainPaneElement.value.removeEventListener("mousemove", handlePaneMouseMove, true);
    }
  }

  function mountPaneEvents() {
    const pane = getPaneElement();
    if (!pane || pane === mainPaneElement.value) return;

    teardownPaneEvents();
    mainPaneElement.value = pane;

    const computedStyle = window.getComputedStyle(pane);
    if (computedStyle.position === "static") {
      pane.style.position = "relative";
    }

    if (!overlayRoot.value) {
      overlayRoot.value = document.createElement("div");
      overlayRoot.value.className = "lwc-drawing-overlay";
      overlayRoot.value.style.position = "absolute";
      overlayRoot.value.style.inset = "0";
      overlayRoot.value.style.pointerEvents = "none";
      overlayRoot.value.style.zIndex = "8";

      overlaySvg.value = createSvgNode("svg", {
        width: "100%",
        height: "100%",
        preserveAspectRatio: "none",
      });
      overlaySvg.value.style.overflow = "visible";
      overlayRoot.value.appendChild(overlaySvg.value);
    }

    pane.appendChild(overlayRoot.value);
    pane.addEventListener("mousedown", handlePaneMouseDown, true);
    pane.addEventListener("click", handlePaneClick, true);
    pane.addEventListener("dblclick", handlePaneDoubleClick, true);
    pane.addEventListener("mousemove", handlePaneMouseMove, true);

    if (typeof ResizeObserver === "function") {
      resizeObserver.value = new ResizeObserver(() => scheduleRender());
      resizeObserver.value.observe(pane);
    }

    const timeScale = chartApi.value?.timeScale?.();
    if (timeScale?.subscribeVisibleLogicalRangeChange) {
      timeScale.subscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
      visibleRangeUnsubscribe.value = () => {
        timeScale.unsubscribeVisibleLogicalRangeChange(handleVisibleRangeChange);
      };
    }

    scheduleRender();
  }

  function cleanupOverlay() {
    clearRenderFrame();
    teardownPaneEvents();
    window.removeEventListener("mouseup", handleWindowMouseUp);

    priceLines.value.forEach((line) => {
      try {
        mainSeries.value?.removePriceLine?.(line);
      } catch (error) {
        console.error(error);
      }
    });
    priceLines.value = [];

    if (overlayRoot.value?.parentNode) {
      overlayRoot.value.parentNode.removeChild(overlayRoot.value);
    }

    overlayRoot.value = null;
    overlaySvg.value = null;
    mainPaneElement.value = null;
    markersApi.value = null;
    draftDrawing.value = null;
    resetDragState();
  }

  window.addEventListener("mouseup", handleWindowMouseUp);

  watch(
    () => [chartApi.value, mainSeries.value],
    () => {
      mountPaneEvents();
      scheduleHostSync?.();
    },
    { immediate: true },
  );

  watch(
    () => props.drawings,
    () => scheduleRender(),
    { deep: true },
  );

  watch(
    () => props.selectedDrawingId,
    () => scheduleRender(),
  );

  watch(
    () => props.institutionalOverlay,
    () => scheduleRender(),
    { deep: true },
  );

  watch(
    () => props.activeTool,
    () => {
      if (props.activeTool === "cursor") return;
      emit("select-drawing", null);
      if (!["tline", "arrow", "fib", "rect", "measure"].includes(props.activeTool)) {
        draftDrawing.value = null;
      }
      scheduleRender();
    },
  );

  watch(
    () => props.ohlcData,
    () => scheduleRender(),
    { deep: true },
  );

  onBeforeUnmount(() => {
    cleanupOverlay();
  });

  return {
    scheduleRender,
    cleanupOverlay,
  };
}
