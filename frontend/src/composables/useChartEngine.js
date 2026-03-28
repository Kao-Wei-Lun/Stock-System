import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import {
  calcBB,
  calcEMA,
  calcMACD,
  calcMA,
  calcRSI,
  calcStoch,
  calcVWAP,
} from "../utils/indicatorUtils";
import { fmtPrice, fmtVol } from "../utils/formatters";

const PAD = { top: 20, right: 70, bottom: 22, left: 10 };
const DEFAULT_VISIBLE_BARS = 90;
const MIN_VISIBLE_BARS = 20;
const PAN_STEP_RATIO = 0.18;
const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
const AUTO_Y_PADDING_RATIO = 0.08;
const AUTO_Y_MIN_PADDING_RATIO = 0.02;
const VIEW_HISTORY_LIMIT = 80;
const CHART_PREFS_KEY = "quantvision.chart.prefs.v1";

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const clampPositive = (value) => Math.max(value, Number.EPSILON);

const getDpr = () => window.devicePixelRatio || 1;
const canvasWidth = (canvas) => canvas.width / getDpr();
const canvasHeight = (canvas) => canvas.height / getDpr();
const setupCtx = (ctx) => ctx.setTransform(getDpr(), 0, 0, getDpr(), 0, 0);

const readChartPrefs = () => {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(CHART_PREFS_KEY) || "{}");
  } catch (error) {
    return {};
  }
};

const writeChartPrefs = (value) => {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CHART_PREFS_KEY, JSON.stringify(value));
};

const drawLine = (ctx, values, xAt, scale, color, lineWidth = 1.5, dash = []) => {
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.setLineDash(dash);
  ctx.beginPath();
  let started = false;
  values.forEach((value, index) => {
    if (value == null) return;
    if (!started) {
      ctx.moveTo(xAt(index), scale(value));
      started = true;
    } else {
      ctx.lineTo(xAt(index), scale(value));
    }
  });
  ctx.stroke();
  ctx.setLineDash([]);
};

const findLastDefinedIndex = (values) => {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    if (values[index] != null) return index;
  }
  return -1;
};

const drawArea = (ctx, values, xAt, scale, baseY, strokeColor, fillColor) => {
  const firstIndex = values.findIndex((value) => value != null);
  const lastIndex = findLastDefinedIndex(values);
  if (firstIndex < 0 || lastIndex < 0) return;

  ctx.beginPath();
  ctx.moveTo(xAt(firstIndex), scale(values[firstIndex]));
  for (let index = firstIndex + 1; index <= lastIndex; index += 1) {
    if (values[index] == null) continue;
    ctx.lineTo(xAt(index), scale(values[index]));
  }
  ctx.lineTo(xAt(lastIndex), baseY);
  ctx.lineTo(xAt(firstIndex), baseY);
  ctx.closePath();
  ctx.fillStyle = fillColor;
  ctx.fill();

  drawLine(ctx, values, xAt, scale, strokeColor, 1.8);
};

const volumeMa = (data, period = 20) => calcMA(data.map((row) => ({ close: row.volume })), period);

export function useChartEngine({
  mainCanvas,
  volumeCanvas,
  compareCanvas,
  rsiCanvas,
  macdCanvas,
  stochCanvas,
  chartAreaRef,
  props,
  emit,
}) {
  const storedChartPrefs = readChartPrefs();
  const chartMode = ref(["candles", "line", "area"].includes(storedChartPrefs.chartMode) ? storedChartPrefs.chartMode : "candles");
  const priceScaleMode = ref(storedChartPrefs.priceScaleMode === "log" ? "log" : "linear");
  let renderFrame = 0;
  let historyCommitTimer = 0;
  const dragMode = ref("none");
  const viewport = reactive({
    startIndex: 0,
    visibleCount: DEFAULT_VISIBLE_BARS,
  });
  const mainMetrics = reactive({
    autoMin: 0,
    autoMax: 1,
    min: 0,
    max: 1,
    chartWidth: 1,
    chartHeight: 1,
    step: 1,
  });
  const yAxis = reactive({
    mode: "auto",
    min: null,
    max: null,
  });
  const draftDrawing = ref(null);
  const isDragging = ref(false);
  const viewHistory = ref([]);
  const viewHistoryIndex = ref(-1);
  const interactionStartView = ref(null);
  const applyingHistory = ref(false);
  const selectionBox = reactive({
    active: false,
    startX: 0,
    startY: 0,
    currentX: 0,
    currentY: 0,
  });
  const dragState = reactive({
    startX: 0,
    startY: 0,
    startIndex: 0,
    startMin: 0,
    startMax: 1,
  });

  const visibleCountFloor = computed(() => Math.min(MIN_VISIBLE_BARS, Math.max(1, props.ohlcData.length)));
  const visibleData = computed(() => {
    if (!props.ohlcData.length) return [];
    const visibleCount = clamp(viewport.visibleCount, visibleCountFloor.value, props.ohlcData.length);
    const maxStart = Math.max(0, props.ohlcData.length - visibleCount);
    const startIndex = clamp(viewport.startIndex, 0, maxStart);
    return props.ohlcData.slice(startIndex, startIndex + visibleCount);
  });
  const dataSignature = computed(() => {
    if (!props.ohlcData.length) return "empty";
    const first = props.ohlcData[0];
    const last = props.ohlcData[props.ohlcData.length - 1];
    return [
      props.ohlcData.length,
      first?.date ?? "",
      first?.close ?? "",
      last?.date ?? "",
      last?.close ?? "",
    ].join("|");
  });

  const visibleRangeLabel = computed(() => {
    if (!visibleData.value.length) return "無資料";
    return `${visibleData.value[0].date} → ${visibleData.value[visibleData.value.length - 1].date}`;
  });

  const visibleBarsLabel = computed(() => `${visibleData.value.length || 0} 根`);

  const visibleChange = computed(() => {
    if (visibleData.value.length < 2) return null;
    const first = visibleData.value[0].close;
    const last = visibleData.value[visibleData.value.length - 1].close;
    if (!first) return null;
    return ((last - first) / first) * 100;
  });

  const visibleChangeLabel = computed(() => {
    if (visibleChange.value == null) return "區間變化 —";
    const sign = visibleChange.value >= 0 ? "+" : "";
    return `區間變化 ${sign}${visibleChange.value.toFixed(2)}%`;
  });

  const visibleChangeClass = computed(() => {
    if (visibleChange.value == null) return "";
    return visibleChange.value >= 0 ? "up" : "dn";
  });

  const zoomLabel = computed(() => {
    if (!props.ohlcData.length) return "縮放 —";
    return `視窗 ${Math.round((visibleData.value.length / props.ohlcData.length) * 100)}%`;
  });

  const canPanLeft = computed(() => viewport.startIndex > 0);
  const canPanRight = computed(
    () => viewport.startIndex + visibleData.value.length < props.ohlcData.length,
  );
  const canZoomIn = computed(
    () => visibleData.value.length > visibleCountFloor.value,
  );
  const canZoomOut = computed(
    () => visibleData.value.length < props.ohlcData.length,
  );
  const canUseLogScale = computed(() =>
    visibleData.value.every((row) => Number(row.low ?? row.close ?? 0) > 0),
  );
  const canGoBackHistory = computed(() => viewHistoryIndex.value > 0);
  const canGoForwardHistory = computed(
    () => viewHistoryIndex.value >= 0 && viewHistoryIndex.value < viewHistory.value.length - 1,
  );
  const yScaleLabel = computed(() => {
    if (!visibleData.value.length) return "Y 軸 自動";
    const min = yAxis.mode === "manual" && yAxis.min != null ? yAxis.min : mainMetrics.autoMin;
    const max = yAxis.mode === "manual" && yAxis.max != null ? yAxis.max : mainMetrics.autoMax;
    const modeLabel = yAxis.mode === "manual" ? "Y 軸 手動" : "Y 軸 自動";
    return `${modeLabel} ${fmtPrice(min)} - ${fmtPrice(max)}`;
  });
  const priceScaleModeLabel = computed(
    () => `價格尺度 ${priceScaleMode.value === "log" ? "對數" : "線性"}`,
  );
  const canResetYScale = computed(() => yAxis.mode === "manual");
  const interactionHintText = computed(() => {
    if (selectionBox.active) return "框選中：放開滑鼠後縮放到所選區間";
    if (dragMode.value === "pan-x") return "拖曳中：左右平移時間視窗";
    if (dragMode.value === "pan-y") return "拖曳中：調整價格軸顯示範圍";
    if (props.activeTool === "cursor") {
      return "滾輪縮放時間、價格軸滾輪縮放 Y 軸、拖曳平移、雙擊重置";
    }
    if (props.activeTool === "boxzoom") {
      return "按住拖曳框出區間，放開後放大所選時間與價格範圍";
    }
    if (props.activeTool === "hline") return "點一下加入水平壓力/支撐線";
    if (props.activeTool === "vline") return "點一下加入事件垂直線";
    if (props.activeTool === "tline") {
      return draftDrawing.value?.type === "trendline"
        ? "趨勢線：移動滑鼠預覽，再點一下完成"
        : "趨勢線：先點起點，再點終點";
    }
    if (props.activeTool === "fib") {
      return draftDrawing.value?.type === "fib"
        ? "費波那契：移動滑鼠預覽，再點一下完成"
        : "費波那契：先點低/高點，再點另一端";
    }
    if (props.activeTool === "rect") {
      return draftDrawing.value?.type === "rect"
        ? "區間框：移動滑鼠預覽，再點一下完成"
        : "區間框：先點第一個角，再點第二個角";
    }
    if (props.activeTool === "measure") {
      return draftDrawing.value?.type === "measure"
        ? "測距尺：移動滑鼠預覽，再點一下完成"
        : "測距尺：先點起點，再點終點";
    }
    return "可使用圖表工具進行分析";
  });
  const resolvedCanvasClass = computed(() => {
    if (isDragging.value || selectionBox.active || dragMode.value !== "none") {
      return "chart-canvas is-grabbing";
    }
    if (props.activeTool === "cursor") return "chart-canvas is-grab";
    if (props.activeTool === "boxzoom") return "chart-canvas is-zoom";
    return "chart-canvas is-draw";
  });

  const getBarLayout = (canvas, count) => {
    const width = canvasWidth(canvas) - PAD.left - PAD.right;
    const step = width / Math.max(count, 1);
    return {
      width,
      step,
      barWidth: Math.max(1.5, step * 0.72),
      barX: (index) => PAD.left + (index + 0.5) * step,
    };
  };

  const getVisiblePriceScale = (data, extras = [], scaleMode = "linear") => {
    const pricePoints = data.flatMap((row) => [row.high, row.low]);
    extras.forEach((value) => {
      if (Array.isArray(value)) {
        value.forEach((item) => {
          if (item != null) pricePoints.push(item);
        });
      } else if (value != null) {
        pricePoints.push(value);
      }
    });

    if (!pricePoints.length) {
      return { min: 0, max: 1 };
    }

    const rawMin = Math.min(...pricePoints);
    const rawMax = Math.max(...pricePoints);
    let min = rawMin;
    let max = rawMax;

    if (rawMin === rawMax) {
      const singlePad = Math.max(Math.abs(rawMin) * 0.06, 0.5);
      min = rawMin - singlePad;
      max = rawMax + singlePad;
    } else {
      const range = rawMax - rawMin;
      const padding = Math.max(range * AUTO_Y_PADDING_RATIO, Math.abs(rawMax) * AUTO_Y_MIN_PADDING_RATIO, 0.02);
      min = rawMin - padding;
      max = rawMax + padding;
    }

    if (scaleMode === "log" && rawMin > 0) {
      min = Math.max(min, rawMin * 0.55);
      max = Math.max(max, clampPositive(rawMax));
    }

    return { min, max };
  };

  const scaleY = (value, min, max, topPad, chartHeight, scaleMode = "linear") => {
    if (scaleMode === "log" && min > 0 && max > 0 && value > 0) {
      const logMin = Math.log(clampPositive(min));
      const logMax = Math.log(clampPositive(max));
      const logValue = Math.log(clampPositive(value));
      return topPad + (1 - (logValue - logMin) / (logMax - logMin || 1)) * chartHeight;
    }
    return topPad + (1 - (value - min) / (max - min || 1)) * chartHeight;
  };

  const invertY = (pixelY, min, max, topPad, chartHeight, scaleMode = "linear") => {
    const ratio = 1 - (pixelY - topPad) / (chartHeight || 1);
    if (scaleMode === "log" && min > 0 && max > 0) {
      const logMin = Math.log(clampPositive(min));
      const logMax = Math.log(clampPositive(max));
      return Math.exp(logMin + ratio * (logMax - logMin));
    }
    return min + ratio * (max - min);
  };

  const getCurrentYRange = () => {
    const min = yAxis.mode === "manual" && yAxis.min != null ? yAxis.min : mainMetrics.autoMin;
    const max = yAxis.mode === "manual" && yAxis.max != null ? yAxis.max : mainMetrics.autoMax;
    return { min, max };
  };

  const setManualYRange = (nextMin, nextMax, { render = true } = {}) => {
    if (!Number.isFinite(nextMin) || !Number.isFinite(nextMax)) return;

    let min = nextMin;
    let max = nextMax;
    if (min > max) [min, max] = [max, min];

    if (min === max) {
      const pad = Math.max(Math.abs(min) * 0.003, 0.01);
      min -= pad;
      max += pad;
    }

    yAxis.mode = "manual";
    yAxis.min = min;
    yAxis.max = max;

    if (render) scheduleRender();
  };

  const resetYScale = ({ render = true, commit = true } = {}) => {
    yAxis.mode = "auto";
    yAxis.min = null;
    yAxis.max = null;
    if (render) scheduleRender();
    if (commit) rememberViewState();
  };

  const zoomY = (factor, anchorPrice = null, { commit = true } = {}) => {
    const { min, max } = getCurrentYRange();
    if (!Number.isFinite(min) || !Number.isFinite(max)) return;
    const safeAnchor = Number.isFinite(anchorPrice) ? anchorPrice : (min + max) / 2;
    const nextMin = safeAnchor - (safeAnchor - min) * factor;
    const nextMax = safeAnchor + (max - safeAnchor) * factor;
    setManualYRange(nextMin, nextMax);
    if (commit) rememberViewState();
  };

  const zoomYIn = () => zoomY(0.84);
  const zoomYOut = () => zoomY(1.18);

  const panYAxis = (deltaPrice, { render = true } = {}) => {
    const { min, max } = getCurrentYRange();
    if (!Number.isFinite(min) || !Number.isFinite(max)) return;
    setManualYRange(min + deltaPrice, max + deltaPrice, { render });
  };

  const setPriceScaleMode = (mode, { commit = true } = {}) => {
    const nextMode = mode === "log" && canUseLogScale.value ? "log" : "linear";
    if (nextMode === priceScaleMode.value) return;
    priceScaleMode.value = nextMode;
    resetYScale({ render: false, commit: false });
    scheduleRender();
    if (commit) rememberViewState();
  };

  const syncViewport = ({ anchorLatest = false } = {}) => {
    if (!props.ohlcData.length) {
      viewport.startIndex = 0;
      viewport.visibleCount = DEFAULT_VISIBLE_BARS;
      return;
    }

    viewport.visibleCount = clamp(
      viewport.visibleCount,
      visibleCountFloor.value,
      props.ohlcData.length,
    );

    if (anchorLatest) {
      viewport.startIndex = Math.max(0, props.ohlcData.length - viewport.visibleCount);
      return;
    }

    viewport.startIndex = clamp(
      viewport.startIndex,
      0,
      Math.max(0, props.ohlcData.length - viewport.visibleCount),
    );
  };

  const createViewSnapshot = () => ({
    startIndex: viewport.startIndex,
    visibleCount: viewport.visibleCount,
    yMode: yAxis.mode,
    yMin: yAxis.min,
    yMax: yAxis.max,
    priceScaleMode: priceScaleMode.value,
  });

  const sameViewSnapshot = (left, right) =>
    !!left
    && !!right
    && left.startIndex === right.startIndex
    && left.visibleCount === right.visibleCount
    && left.yMode === right.yMode
    && left.yMin === right.yMin
    && left.yMax === right.yMax
    && left.priceScaleMode === right.priceScaleMode;

  const rememberViewState = () => {
    if (applyingHistory.value || !props.ohlcData.length) return;
    const snapshot = createViewSnapshot();
    const currentSnapshot = viewHistory.value[viewHistoryIndex.value];
    if (sameViewSnapshot(snapshot, currentSnapshot)) return;

    const nextHistory = viewHistory.value.slice(0, viewHistoryIndex.value + 1);
    nextHistory.push(snapshot);
    if (nextHistory.length > VIEW_HISTORY_LIMIT) {
      nextHistory.splice(0, nextHistory.length - VIEW_HISTORY_LIMIT);
    }

    viewHistory.value = nextHistory;
    viewHistoryIndex.value = nextHistory.length - 1;
  };

  const queueViewStateCommit = (delay = 220) => {
    if (historyCommitTimer) window.clearTimeout(historyCommitTimer);
    historyCommitTimer = window.setTimeout(() => {
      historyCommitTimer = 0;
      rememberViewState();
    }, delay);
  };

  const applyViewSnapshot = (snapshot) => {
    if (!snapshot) return;
    applyingHistory.value = true;
    viewport.startIndex = snapshot.startIndex;
    viewport.visibleCount = snapshot.visibleCount;
    yAxis.mode = snapshot.yMode;
    yAxis.min = snapshot.yMin;
    yAxis.max = snapshot.yMax;
    priceScaleMode.value = snapshot.priceScaleMode === "log" ? "log" : "linear";
    syncViewport();
    scheduleRender();
    window.requestAnimationFrame(() => {
      applyingHistory.value = false;
    });
  };

  const goHistoryBack = () => {
    if (!canGoBackHistory.value) return;
    const nextIndex = viewHistoryIndex.value - 1;
    viewHistoryIndex.value = nextIndex;
    applyViewSnapshot(viewHistory.value[nextIndex]);
  };

  const goHistoryForward = () => {
    if (!canGoForwardHistory.value) return;
    const nextIndex = viewHistoryIndex.value + 1;
    viewHistoryIndex.value = nextIndex;
    applyViewSnapshot(viewHistory.value[nextIndex]);
  };

  const xForAbsoluteIndex = (layout, absoluteIndex) =>
    layout.barX(absoluteIndex - viewport.startIndex);

  const sliceSeries = (series) =>
    series.slice(viewport.startIndex, viewport.startIndex + visibleData.value.length);

  const drawGrid = (ctx, canvas, min, max, data, scaleMode = "linear") => {
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const chartHeight = height - PAD.top - PAD.bottom;

    ctx.strokeStyle = "rgba(30,45,61,0.7)";
    ctx.lineWidth = 0.5;
    ctx.fillStyle = "rgba(77,102,128,0.7)";
    ctx.font = "9px JetBrains Mono";

    for (let index = 0; index <= 5; index += 1) {
      const y = PAD.top + index * (chartHeight / 5);
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(width - PAD.right, y);
      ctx.stroke();
      const price = scaleMode === "log" && min > 0 && max > 0
        ? Math.exp(Math.log(clampPositive(max)) - (index * (Math.log(clampPositive(max)) - Math.log(clampPositive(min)))) / 5)
        : max - (index * (max - min)) / 5;
      ctx.fillText(price.toFixed(2), width - PAD.right + 4, y + 3);
    }

    const step = Math.max(1, Math.floor(data.length / 6));
    data.forEach((row, index) => {
      if (index % step !== 0 && index !== data.length - 1) return;
      ctx.fillText(row.date.slice(5), PAD.left + index * (mainMetrics.step || 1), height - 8);
    });
  };

  const drawPriceLabel = (ctx, canvas, price, scale, color, prefix = "") => {
    const width = canvasWidth(canvas);
    const y = scale(price);

    ctx.strokeStyle = color;
    ctx.lineWidth = 0.8;
    ctx.setLineDash([5, 3]);
    ctx.beginPath();
    ctx.moveTo(PAD.left, y);
    ctx.lineTo(width - PAD.right, y);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = color;
    ctx.font = "9px JetBrains Mono";
    ctx.fillText(`${prefix}${price.toFixed(2)}`, width - PAD.right + 3, y + 3);
  };

  const drawTrendLine = (ctx, layout, drawing, scale, color = "#00d4ff", dash = []) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.setLineDash(dash);
    ctx.beginPath();
    ctx.moveTo(xForAbsoluteIndex(layout, drawing.startIndex), scale(drawing.startPrice));
    ctx.lineTo(xForAbsoluteIndex(layout, drawing.endIndex), scale(drawing.endPrice));
    ctx.stroke();
    ctx.setLineDash([]);
  };

const drawFib = (ctx, layout, drawing, scale, width, color = "#ffd166", dash = []) => {
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
    ctx.setLineDash(dash);

    FIB_LEVELS.forEach((level) => {
      const price = direction >= 0
        ? high - (high - low) * level
        : low + (high - low) * level;
      const y = scale(price);

      ctx.beginPath();
      ctx.moveTo(leftX, y);
      ctx.lineTo(rightX, y);
      ctx.stroke();
      ctx.fillText(`${Math.round(level * 100)}% ${price.toFixed(2)}`, width - PAD.right + 3, y + 3);
    });

  ctx.setLineDash([]);
};

const drawVerticalLine = (ctx, x, height, color = "#ff8c42", dash = [5, 3]) => {
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.setLineDash(dash);
  ctx.beginPath();
  ctx.moveTo(x, PAD.top);
  ctx.lineTo(x, height - PAD.bottom);
  ctx.stroke();
  ctx.setLineDash([]);
};

const drawRectZone = (ctx, xAtAbsolute, drawing, scale, strokeStyle, fillStyle, width) => {
  const x1 = xAtAbsolute(drawing.startIndex);
  const x2 = xAtAbsolute(drawing.endIndex);
  const y1 = scale(drawing.startPrice);
  const y2 = scale(drawing.endPrice);
  const left = Math.min(x1, x2);
  const top = Math.min(y1, y2);
  const zoneWidth = Math.abs(x2 - x1);
  const zoneHeight = Math.abs(y2 - y1);

  ctx.fillStyle = fillStyle;
  ctx.strokeStyle = strokeStyle;
  ctx.lineWidth = 1.2;
  ctx.setLineDash([6, 4]);
  ctx.fillRect(left, top, zoneWidth, zoneHeight);
  ctx.strokeRect(left, top, zoneWidth, zoneHeight);
  ctx.setLineDash([]);

  const high = Math.max(drawing.startPrice, drawing.endPrice);
  const low = Math.min(drawing.startPrice, drawing.endPrice);
  ctx.fillStyle = strokeStyle;
  ctx.font = "9px JetBrains Mono";
  ctx.fillText(`${high.toFixed(2)} / ${low.toFixed(2)}`, width - PAD.right + 2, top + 10);
};

const drawMeasureTool = (ctx, xAtAbsolute, drawing, scale, width, strokeStyle = "#00d4ff") => {
  const x1 = xAtAbsolute(drawing.startIndex);
  const x2 = xAtAbsolute(drawing.endIndex);
  const y1 = scale(drawing.startPrice);
  const y2 = scale(drawing.endPrice);
  const left = Math.min(x1, x2);
  const top = Math.min(y1, y2);
  const boxWidth = Math.abs(x2 - x1);
  const boxHeight = Math.abs(y2 - y1);
  const bars = Math.abs(drawing.endIndex - drawing.startIndex) + 1;
  const priceChange = drawing.endPrice - drawing.startPrice;
  const pctChange = drawing.startPrice ? (priceChange / drawing.startPrice) * 100 : 0;

  ctx.strokeStyle = strokeStyle;
  ctx.fillStyle = "rgba(0,212,255,0.08)";
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 3]);
  ctx.fillRect(left, top, boxWidth, boxHeight);
  ctx.strokeRect(left, top, boxWidth, boxHeight);
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = strokeStyle;
  ctx.font = "9px JetBrains Mono";
  ctx.fillText(
    `${bars} bars | ${priceChange >= 0 ? "+" : ""}${priceChange.toFixed(2)} | ${pctChange >= 0 ? "+" : ""}${pctChange.toFixed(2)}%`,
    Math.min(left + 6, width - PAD.right - 150),
    top + 12,
  );
};

  const getDrawingPriceValues = (drawing) => {
    if (!drawing) return [];
    const viewStart = viewport.startIndex;
    const viewEnd = viewport.startIndex + visibleData.value.length - 1;

    if (drawing.type === "hline") {
      return drawing.price != null ? [drawing.price] : [];
    }

    if (drawing.type === "trendline" || drawing.type === "fib" || drawing.type === "rect" || drawing.type === "measure") {
      const drawingStart = Math.min(drawing.startIndex, drawing.endIndex);
      const drawingEnd = Math.max(drawing.startIndex, drawing.endIndex);
      if (drawingEnd < viewStart || drawingStart > viewEnd) return [];
      return [drawing.startPrice, drawing.endPrice].filter((price) => price != null);
    }

    return [];
  };

  const renderMain = () => {
    if (!mainCanvas.value || !visibleData.value.length) return;
    const canvas = mainCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const data = visibleData.value;
    const fullData = props.ohlcData;
    const count = data.length;

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const chartHeight = height - PAD.top - PAD.bottom;
    const layout = getBarLayout(canvas, count);
    const fullMa20 = props.activeInd.ma20 ? calcMA(fullData, 20) : [];
    const fullMa50 = props.activeInd.ma50 ? calcMA(fullData, 50) : [];
    const fullMa200 = props.activeInd.ma200 ? calcMA(fullData, 200) : [];
    const fullEma12 = props.activeInd.ema12 ? calcEMA(fullData, 12) : [];
    const fullVwap = props.activeInd.vwap ? calcVWAP(fullData) : [];
    const fullBb = props.activeInd.bb ? calcBB(fullData) : [];

    const ma20 = sliceSeries(fullMa20);
    const ma50 = sliceSeries(fullMa50);
    const ma200 = sliceSeries(fullMa200);
    const ema12 = sliceSeries(fullEma12);
    const vwap = sliceSeries(fullVwap);
    const bbSlice = fullBb.slice(viewport.startIndex, viewport.startIndex + count);
    const overlayValues = [];
    if (props.activeInd.ma20) overlayValues.push(ma20);
    if (props.activeInd.ma50) overlayValues.push(ma50);
    if (props.activeInd.ma200) overlayValues.push(ma200);
    if (props.activeInd.ema12) overlayValues.push(ema12);
    if (props.activeInd.vwap) overlayValues.push(vwap);
    if (bbSlice.length) {
      overlayValues.push(bbSlice.map((item) => item.u));
      overlayValues.push(bbSlice.map((item) => item.l));
      overlayValues.push(bbSlice.map((item) => item.m));
    }
    props.drawings.forEach((drawing) => overlayValues.push(getDrawingPriceValues(drawing)));
    if (draftDrawing.value) overlayValues.push(getDrawingPriceValues(draftDrawing.value));

    const { min: autoMin, max: autoMax } = getVisiblePriceScale(data, overlayValues, priceScaleMode.value);
    const min = yAxis.mode === "manual" && yAxis.min != null ? yAxis.min : autoMin;
    const max = yAxis.mode === "manual" && yAxis.max != null ? yAxis.max : autoMax;
    const scale = (value) => scaleY(value, min, max, PAD.top, chartHeight, priceScaleMode.value);

    mainMetrics.autoMin = autoMin;
    mainMetrics.autoMax = autoMax;
    mainMetrics.min = min;
    mainMetrics.max = max;
    mainMetrics.chartHeight = chartHeight;
    mainMetrics.chartWidth = layout.width;
    mainMetrics.step = layout.step;

    drawGrid(ctx, canvas, min, max, data, priceScaleMode.value);

    if (chartMode.value === "candles") {
      data.forEach((row, index) => {
        const x = layout.barX(index);
        const isUp = row.close >= row.open;
        const color = isUp ? "#00d9a3" : "#ff4d6a";
        ctx.strokeStyle = color;
        ctx.fillStyle = isUp ? "rgba(0,217,163,0.85)" : "rgba(255,77,106,0.85)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, scale(row.high));
        ctx.lineTo(x, scale(row.low));
        ctx.stroke();
        const top = scale(Math.max(row.open, row.close));
        const bottom = scale(Math.min(row.open, row.close));
        ctx.fillRect(x - layout.barWidth / 2, top, layout.barWidth, Math.max(1, bottom - top));
      });
    } else {
      const closes = data.map((row) => row.close);
      if (chartMode.value === "line") {
        drawLine(ctx, closes, layout.barX, scale, "#00d4ff", 1.8);
      } else {
        drawArea(
          ctx,
          closes,
          layout.barX,
          scale,
          height - PAD.bottom,
          "#00d4ff",
          "rgba(0,212,255,0.14)",
        );
      }
    }

    if (props.activeInd.ma20) drawLine(ctx, ma20, layout.barX, scale, "#3b8bff", 1.5);
    if (props.activeInd.ma50) drawLine(ctx, ma50, layout.barX, scale, "#f5a623", 1.5);
    if (props.activeInd.ma200) drawLine(ctx, ma200, layout.barX, scale, "#9b6dff", 1.4);
    if (props.activeInd.ema12) drawLine(ctx, ema12, layout.barX, scale, "#00d4ff", 1.1);
    if (props.activeInd.vwap) drawLine(ctx, vwap, layout.barX, scale, "#ff8c42", 1.1, [4, 3]);

    if (bbSlice.length) {
      drawLine(ctx, bbSlice.map((item) => item.u), layout.barX, scale, "#ffd166", 0.9);
      drawLine(ctx, bbSlice.map((item) => item.l), layout.barX, scale, "#ffd166", 0.9);
      drawLine(ctx, bbSlice.map((item) => item.m), layout.barX, scale, "rgba(255,209,102,0.65)", 0.6, [4, 4]);
    }

    props.drawings.forEach((drawing) => {
      if (drawing.type === "buy" || drawing.type === "sell") {
        if (drawing.index < viewport.startIndex || drawing.index >= viewport.startIndex + count) return;
        const localIndex = drawing.index - viewport.startIndex;
        const x = layout.barX(localIndex);
        ctx.fillStyle = drawing.type === "buy" ? "#00d9a3" : "#ff4d6a";
        ctx.font = "bold 13px sans-serif";
        const row = fullData[drawing.index];
        const y = drawing.type === "buy" ? scale(row.low) + 14 : scale(row.high) - 6;
        ctx.fillText(drawing.type === "buy" ? "▲" : "▼", x - 5, y);
        return;
      }

      if (drawing.type === "hline") {
        ctx.strokeStyle = "#f5a623";
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 3]);
        ctx.beginPath();
        ctx.moveTo(PAD.left, scale(drawing.price));
        ctx.lineTo(width - PAD.right, scale(drawing.price));
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "#f5a623";
        ctx.font = "9px JetBrains Mono";
        ctx.fillText(drawing.price.toFixed(2), width - PAD.right + 2, scale(drawing.price) + 3);
        return;
      }

      if (drawing.type === "vline") {
        drawVerticalLine(ctx, xForAbsoluteIndex(layout, drawing.index), height, "#ff8c42");
        return;
      }

      if (drawing.type === "trendline") {
        drawTrendLine(ctx, layout, drawing, scale, "#00d4ff");
        return;
      }

      if (drawing.type === "fib") {
        drawFib(ctx, layout, drawing, scale, width, "#ffd166", [6, 4]);
        return;
      }

      if (drawing.type === "rect") {
        drawRectZone(
          ctx,
          (absoluteIndex) => xForAbsoluteIndex(layout, absoluteIndex),
          drawing,
          scale,
          "#9b6dff",
          "rgba(155,109,255,0.12)",
          width,
        );
        return;
      }

      if (drawing.type === "measure") {
        drawMeasureTool(
          ctx,
          (absoluteIndex) => xForAbsoluteIndex(layout, absoluteIndex),
          drawing,
          scale,
          width,
          "#00d4ff",
        );
        return;
      }
    });

    if (draftDrawing.value?.type === "trendline") {
      drawTrendLine(ctx, layout, draftDrawing.value, scale, "rgba(0,212,255,0.75)", [6, 4]);
    }

    if (draftDrawing.value?.type === "fib") {
      drawFib(ctx, layout, draftDrawing.value, scale, width, "rgba(255,209,102,0.8)", [4, 4]);
    }

    if (draftDrawing.value?.type === "rect") {
      drawRectZone(
        ctx,
        (absoluteIndex) => xForAbsoluteIndex(layout, absoluteIndex),
        draftDrawing.value,
        scale,
        "rgba(155,109,255,0.9)",
        "rgba(155,109,255,0.1)",
        width,
      );
    }

    if (draftDrawing.value?.type === "measure") {
      drawMeasureTool(
        ctx,
        (absoluteIndex) => xForAbsoluteIndex(layout, absoluteIndex),
        draftDrawing.value,
        scale,
        width,
        "rgba(0,212,255,0.85)",
      );
    }

    if (selectionBox.active) {
      const left = Math.min(selectionBox.startX, selectionBox.currentX);
      const top = Math.min(selectionBox.startY, selectionBox.currentY);
      const boxWidth = Math.abs(selectionBox.currentX - selectionBox.startX);
      const boxHeight = Math.abs(selectionBox.currentY - selectionBox.startY);
      ctx.fillStyle = "rgba(59,139,255,0.16)";
      ctx.strokeStyle = "rgba(59,139,255,0.9)";
      ctx.lineWidth = 1;
      ctx.setLineDash([6, 4]);
      ctx.fillRect(left, top, boxWidth, boxHeight);
      ctx.strokeRect(left, top, boxWidth, boxHeight);
      ctx.setLineDash([]);
    }

    const lastRow = data[data.length - 1];
    const prevRow = data[data.length - 2] || lastRow;
    drawPriceLabel(
      ctx,
      canvas,
      lastRow.close,
      scale,
      lastRow.close >= prevRow.close ? "#00d9a3" : "#ff4d6a",
    );
  };

  const renderCompare = () => {
    if (!compareCanvas.value) return;

    const canvas = compareCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    if (!visibleData.value.length || !props.compareSeries?.length) return;

    const baseDates = visibleData.value.map((row) => row.date);
    const layout = getBarLayout(canvas, visibleData.value.length);

    const toSeriesValues = (rows, mode) => {
      const closeByDate = new Map(rows.map((row) => [row.date, row.close]));
      const rawValues = baseDates.map((date) => closeByDate.get(date) ?? null);
      if (mode === "price") return rawValues;
      const baseValue = rawValues.find((value) => value != null);
      if (baseValue == null) return rawValues;
      return rawValues.map((value) => (value == null ? null : ((value - baseValue) / baseValue) * 100));
    };

    const seriesList = [
      {
        ticker: props.currentTicker,
        color: "#00d4ff",
        values: toSeriesValues(visibleData.value, props.comparisonMode),
      },
      ...props.compareSeries.map((series) => ({
        ticker: series.ticker,
        color: series.color,
        values: toSeriesValues(series.data || [], props.comparisonMode),
      })),
    ].filter((series) => series.values.some((value) => value != null));

    if (!seriesList.length) return;

    const points = seriesList.flatMap((series) => series.values.filter((value) => value != null));
    let min = Math.min(...points);
    let max = Math.max(...points);
    if (min === max) {
      min -= 1;
      max += 1;
    } else {
      const pad = (max - min) * 0.08;
      min -= pad;
      max += pad;
    }

    const chartHeight = height - 10;
    const scale = (value) => 4 + (1 - (value - min) / (max - min || 1)) * chartHeight;

    ctx.strokeStyle = "rgba(30,45,61,0.7)";
    ctx.lineWidth = 0.5;
    ctx.fillStyle = "rgba(77,102,128,0.7)";
    ctx.font = "8px JetBrains Mono";
    for (let index = 0; index <= 4; index += 1) {
      const y = 4 + index * (chartHeight / 4);
      const axisValue = max - ((max - min) * index) / 4;
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(width - PAD.right, y);
      ctx.stroke();
      const label = props.comparisonMode === "percent" ? `${axisValue.toFixed(1)}%` : axisValue.toFixed(2);
      ctx.fillText(label, width - PAD.right + 2, y + 3);
    }

    seriesList.forEach((series) => {
      drawLine(ctx, series.values, layout.barX, scale, series.color, 1.5);
      const lastIndex = findLastDefinedIndex(series.values);
      if (lastIndex < 0) return;
      const lastValue = series.values[lastIndex];
      const label = props.comparisonMode === "percent"
        ? `${series.ticker} ${lastValue >= 0 ? "+" : ""}${lastValue.toFixed(2)}%`
        : `${series.ticker} ${lastValue.toFixed(2)}`;
      ctx.fillStyle = series.color;
      ctx.font = "8px JetBrains Mono";
      ctx.fillText(label, 8, 12 + seriesList.indexOf(series) * 11);
    });
  };

  const renderVolume = () => {
    if (!volumeCanvas.value || !visibleData.value.length) return;
    const canvas = volumeCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const data = visibleData.value;

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, data.length);
    const maxVolume = Math.max(...data.map((row) => row.volume || 0), 1);
    const chartHeight = height - 4;
    const scale = (value) => chartHeight - (value / maxVolume) * chartHeight + 2;
    const visibleVolumeMa = sliceSeries(volumeMa(props.ohlcData, 20));

    data.forEach((row, index) => {
      const barHeight = (row.volume / maxVolume) * chartHeight;
      ctx.fillStyle = row.close >= row.open ? "rgba(0,217,163,0.4)" : "rgba(255,77,106,0.4)";
      ctx.fillRect(
        layout.barX(index) - (layout.barWidth * 0.78) / 2,
        chartHeight - barHeight + 2,
        layout.barWidth * 0.78,
        barHeight,
      );
    });

    drawLine(ctx, visibleVolumeMa, layout.barX, scale, "#f5a623", 1);

    ctx.fillStyle = "rgba(77,102,128,0.6)";
    ctx.font = "9px JetBrains Mono";
    ctx.fillText("VOL / MA20", 2, 12);
  };

  const renderRsi = () => {
    if (!rsiCanvas.value || !visibleData.value.length || !props.activePanels.rsi) return;
    const canvas = rsiCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const values = sliceSeries(calcRSI(props.ohlcData));

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, visibleData.value.length);
    const chartHeight = height - 8;
    const scale = (value) => 4 + (1 - value / 100) * chartHeight;

    ctx.fillStyle = "rgba(255,77,106,0.05)";
    ctx.fillRect(PAD.left, scale(100), width - PAD.left - PAD.right, scale(70) - scale(100));
    ctx.fillStyle = "rgba(0,217,163,0.05)";
    ctx.fillRect(PAD.left, scale(30), width - PAD.left - PAD.right, scale(0) - scale(30));

    [70, 50, 30].forEach((level) => {
      ctx.strokeStyle = "rgba(77,102,128,0.4)";
      ctx.lineWidth = 0.5;
      ctx.setLineDash(level === 50 ? [4, 4] : []);
      ctx.beginPath();
      ctx.moveTo(PAD.left, scale(level));
      ctx.lineTo(width - PAD.right, scale(level));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(77,102,128,0.6)";
      ctx.font = "8px JetBrains Mono";
      ctx.fillText(level, width - PAD.right + 2, scale(level) + 3);
    });

    drawLine(ctx, values, layout.barX, scale, "#00d9a3", 1.5);
  };

  const renderMacd = () => {
    if (!macdCanvas.value || !visibleData.value.length || !props.activePanels.macd) return;
    const canvas = macdCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const { macd, signal, hist } = calcMACD(props.ohlcData);
    const visibleMacd = sliceSeries(macd);
    const visibleSignal = sliceSeries(signal);
    const visibleHist = sliceSeries(hist);

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, visibleData.value.length);
    const values = [...visibleHist, ...visibleMacd, ...visibleSignal].filter((value) => value != null);
    const min = Math.min(...values, -1);
    const max = Math.max(...values, 1);
    const chartHeight = height - 8;
    const scale = (value) => 4 + (1 - (value - min) / (max - min || 1)) * chartHeight;

    ctx.strokeStyle = "rgba(77,102,128,0.4)";
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(PAD.left, scale(0));
    ctx.lineTo(width - PAD.right, scale(0));
    ctx.stroke();

    visibleHist.forEach((value, index) => {
      if (value == null) return;
      ctx.fillStyle = value >= 0 ? "rgba(0,217,163,0.5)" : "rgba(255,77,106,0.5)";
      const top = scale(Math.max(0, value));
      const bottom = scale(Math.min(0, value));
      ctx.fillRect(layout.barX(index) - layout.barWidth / 2, top, layout.barWidth, Math.max(1, bottom - top));
    });

    drawLine(ctx, visibleMacd, layout.barX, scale, "#3b8bff", 1.2);
    drawLine(ctx, visibleSignal, layout.barX, scale, "#f5a623", 1.2);
  };

  const renderStoch = () => {
    if (!stochCanvas.value || !visibleData.value.length || !props.activePanels.stoch) return;
    const canvas = stochCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const { k, d } = calcStoch(props.ohlcData);
    const visibleK = sliceSeries(k);
    const visibleD = sliceSeries(d);

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, visibleData.value.length);
    const chartHeight = height - 8;
    const scale = (value) => 4 + (1 - value / 100) * chartHeight;

    [80, 50, 20].forEach((level) => {
      ctx.strokeStyle = "rgba(77,102,128,0.4)";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(PAD.left, scale(level));
      ctx.lineTo(width - PAD.right, scale(level));
      ctx.stroke();
    });

    drawLine(ctx, visibleK, layout.barX, scale, "#00d9a3", 1.5);
    drawLine(ctx, visibleD, layout.barX, scale, "#f5a623", 1);
  };

  const clearAll = () => {
    [mainCanvas.value, compareCanvas.value, volumeCanvas.value, rsiCanvas.value, macdCanvas.value, stochCanvas.value]
      .filter(Boolean)
      .forEach((canvas) => {
        const ctx = canvas.getContext("2d");
        setupCtx(ctx);
        ctx.clearRect(0, 0, canvasWidth(canvas), canvasHeight(canvas));
      });
  };

  const scheduleRender = () => {
    if (renderFrame) cancelAnimationFrame(renderFrame);
    renderFrame = window.requestAnimationFrame(() => {
      renderFrame = 0;
      renderAll();
    });
  };

  const renderAll = () => {
    if (!visibleData.value.length) {
      clearAll();
      return;
    }
    renderMain();
    renderCompare();
    renderVolume();
    renderRsi();
    renderMacd();
    renderStoch();
  };

  const resizeCanvas = (canvas, element) => {
    if (!canvas || !element) return;
    const dpr = getDpr();
    canvas.width = Math.max(1, element.offsetWidth * dpr);
    canvas.height = Math.max(1, element.offsetHeight * dpr);
    canvas.style.width = `${element.offsetWidth}px`;
    canvas.style.height = `${element.offsetHeight}px`;
  };

  const resizeAll = () => {
    resizeCanvas(mainCanvas.value, chartAreaRef.value);
    resizeCanvas(compareCanvas.value, compareCanvas.value?.parentElement);
    resizeCanvas(volumeCanvas.value, volumeCanvas.value?.parentElement);
    resizeCanvas(rsiCanvas.value, rsiCanvas.value?.parentElement);
    resizeCanvas(macdCanvas.value, macdCanvas.value?.parentElement);
    resizeCanvas(stochCanvas.value, stochCanvas.value?.parentElement);
    scheduleRender();
  };

  const getPointerData = (event) => {
    if (!mainCanvas.value || !visibleData.value.length) return null;
    const rect = mainCanvas.value.getBoundingClientRect();
    const chartWidth = rect.width - PAD.left - PAD.right;
    const rawX = event.clientX - rect.left;
    const rawY = event.clientY - rect.top;
    const x = clamp(rawX, PAD.left, rect.width - PAD.right - 1);
    const y = clamp(rawY, PAD.top, rect.height - PAD.bottom - 1);
    const localIndex = clamp(
      Math.floor((x - PAD.left) / (chartWidth / visibleData.value.length)),
      0,
      visibleData.value.length - 1,
    );
    const absoluteIndex = viewport.startIndex + localIndex;
    const row = props.ohlcData[absoluteIndex];
    const price = invertY(
      y,
      mainMetrics.min,
      mainMetrics.max,
      PAD.top,
      mainMetrics.chartHeight,
      priceScaleMode.value,
    );

    return {
      x,
      y,
      rawX,
      rawY,
      rectWidth: rect.width,
      rectHeight: rect.height,
      isOnPriceAxis: rawX >= rect.width - PAD.right && rawX <= rect.width,
      localIndex,
      absoluteIndex,
      row,
      price,
    };
  };

  const panByBars = (delta, { commit = true } = {}) => {
    if (!props.ohlcData.length) return;
    viewport.startIndex = clamp(
      viewport.startIndex + delta,
      0,
      Math.max(0, props.ohlcData.length - visibleData.value.length),
    );
    scheduleRender();
    if (commit) rememberViewState();
  };

  const zoomTo = (nextVisibleCount, anchorRatio = 0.5, { commit = true } = {}) => {
    if (!props.ohlcData.length) return;
    const currentVisibleCount = visibleData.value.length;
    const clampedVisibleCount = clamp(
      nextVisibleCount,
      visibleCountFloor.value,
      props.ohlcData.length,
    );
    if (clampedVisibleCount === currentVisibleCount) return;

    const anchorIndex = viewport.startIndex + Math.round(anchorRatio * Math.max(currentVisibleCount - 1, 0));
    viewport.visibleCount = clampedVisibleCount;
    viewport.startIndex = clamp(
      Math.round(anchorIndex - anchorRatio * Math.max(clampedVisibleCount - 1, 0)),
      0,
      Math.max(0, props.ohlcData.length - clampedVisibleCount),
    );
    scheduleRender();
    if (commit) rememberViewState();
  };

  const zoomIn = () => zoomTo(Math.round(visibleData.value.length * 0.8));
  const zoomOut = () => zoomTo(Math.round(visibleData.value.length * 1.25));
  const panLeft = () => panByBars(-Math.max(1, Math.round(visibleData.value.length * PAN_STEP_RATIO)));
  const panRight = () => panByBars(Math.max(1, Math.round(visibleData.value.length * PAN_STEP_RATIO)));
  const jumpToLatest = () => {
    syncViewport({ anchorLatest: true });
    scheduleRender();
    rememberViewState();
  };
  const resetView = () => {
    viewport.visibleCount = DEFAULT_VISIBLE_BARS;
    draftDrawing.value = null;
    dragMode.value = "none";
    isDragging.value = false;
    selectionBox.active = false;
    syncViewport({ anchorLatest: true });
    resetYScale({ render: false, commit: false });
    scheduleRender();
    rememberViewState();
  };
  const setChartMode = (mode) => {
    chartMode.value = mode;
    scheduleRender();
  };

  const updateDraftDrawing = (info) => {
    if (
      !draftDrawing.value
      || !info
      || !["trendline", "fib", "rect", "measure"].includes(draftDrawing.value.type)
    ) {
      return;
    }
    draftDrawing.value = {
      ...draftDrawing.value,
      endIndex: info.absoluteIndex,
      endPrice: info.price,
    };
    scheduleRender();
  };

  const finishSelectionZoom = () => {
    if (!selectionBox.active) return false;

    const leftX = Math.min(selectionBox.startX, selectionBox.currentX);
    const rightX = Math.max(selectionBox.startX, selectionBox.currentX);
    const topY = Math.min(selectionBox.startY, selectionBox.currentY);
    const bottomY = Math.max(selectionBox.startY, selectionBox.currentY);
    const boxWidth = rightX - leftX;
    const boxHeight = bottomY - topY;
    let changed = false;

    if (boxWidth >= 12) {
      const leftIndex = clamp(
        Math.floor((leftX - PAD.left) / Math.max(mainMetrics.step, 1)),
        0,
        visibleData.value.length - 1,
      );
      const rightIndex = clamp(
        Math.ceil((rightX - PAD.left) / Math.max(mainMetrics.step, 1)) - 1,
        0,
        visibleData.value.length - 1,
      );
      const startAbsoluteIndex = viewport.startIndex + Math.min(leftIndex, rightIndex);
      const endAbsoluteIndex = viewport.startIndex + Math.max(leftIndex, rightIndex);
      const selectedCount = endAbsoluteIndex - startAbsoluteIndex + 1;
      const nextVisibleCount = clamp(
        selectedCount,
        visibleCountFloor.value,
        props.ohlcData.length,
      );

      viewport.visibleCount = nextVisibleCount;
      if (selectedCount < nextVisibleCount) {
        const centerIndex = Math.round((startAbsoluteIndex + endAbsoluteIndex) / 2);
        viewport.startIndex = clamp(
          centerIndex - Math.floor(nextVisibleCount / 2),
          0,
          Math.max(0, props.ohlcData.length - nextVisibleCount),
        );
      } else {
        viewport.startIndex = clamp(
          startAbsoluteIndex,
          0,
          Math.max(0, props.ohlcData.length - nextVisibleCount),
        );
      }
      changed = true;
    }

    if (boxHeight >= 12) {
      const priceTop = invertY(
        topY,
        mainMetrics.min,
        mainMetrics.max,
        PAD.top,
        mainMetrics.chartHeight,
        priceScaleMode.value,
      );
      const priceBottom = invertY(
        bottomY,
        mainMetrics.min,
        mainMetrics.max,
        PAD.top,
        mainMetrics.chartHeight,
        priceScaleMode.value,
      );
      setManualYRange(priceBottom, priceTop, { render: false });
      changed = true;
    }

    selectionBox.active = false;
    return changed;
  };

  const onMouseDown = (event) => {
    if (event.button !== 0 || !visibleData.value.length) return;
    const info = getPointerData(event);
    if (!info) return;

    if (props.activeTool === "boxzoom") {
      interactionStartView.value = createViewSnapshot();
      selectionBox.active = true;
      selectionBox.startX = info.x;
      selectionBox.startY = info.y;
      selectionBox.currentX = info.x;
      selectionBox.currentY = info.y;
      emit("hide-crosshair");
      scheduleRender();
      return;
    }

    if (props.activeTool !== "cursor") return;

    interactionStartView.value = createViewSnapshot();
    isDragging.value = true;
    if (info.isOnPriceAxis) {
      dragMode.value = "pan-y";
      dragState.startY = event.clientY;
      dragState.startMin =
        yAxis.mode === "manual" && yAxis.min != null ? yAxis.min : mainMetrics.autoMin;
      dragState.startMax =
        yAxis.mode === "manual" && yAxis.max != null ? yAxis.max : mainMetrics.autoMax;
    } else {
      dragMode.value = "pan-x";
      dragState.startX = event.clientX;
      dragState.startIndex = viewport.startIndex;
    }
    emit("hide-crosshair");
  };

  const onMouseMove = (event) => {
    if (!visibleData.value.length) return;

    const info = getPointerData(event);
    if (!info) return;

    if (selectionBox.active) {
      selectionBox.currentX = info.x;
      selectionBox.currentY = info.y;
      emit("hide-crosshair");
      scheduleRender();
      return;
    }

    if (isDragging.value && dragMode.value === "pan-x") {
      const barsMoved = Math.round((event.clientX - dragState.startX) / Math.max(mainMetrics.step, 1));
      viewport.startIndex = clamp(
        dragState.startIndex - barsMoved,
        0,
        Math.max(0, props.ohlcData.length - visibleData.value.length),
      );
      emit("hide-crosshair");
      scheduleRender();
      return;
    }

    if (isDragging.value && dragMode.value === "pan-y") {
      const pricePerPixel =
        (dragState.startMax - dragState.startMin) / Math.max(mainMetrics.chartHeight, 1);
      const deltaPrice = (event.clientY - dragState.startY) * pricePerPixel;
      setManualYRange(dragState.startMin + deltaPrice, dragState.startMax + deltaPrice);
      emit("hide-crosshair");
      return;
    }

    emit("update-crosshair", {
      visible: true,
      date: info.row.date,
      open: fmtPrice(info.row.open),
      high: fmtPrice(info.row.high),
      low: fmtPrice(info.row.low),
      close: fmtPrice(info.row.close),
      volume: fmtVol(info.row.volume),
    });

    updateDraftDrawing(info);
  };

  const onMouseLeave = () => {
    if (!isDragging.value && !selectionBox.active) emit("hide-crosshair");
  };

  const onMouseUp = () => {
    const hadSelection = selectionBox.active;
    const changed = hadSelection ? finishSelectionZoom() : false;
    const startSnapshot = interactionStartView.value;
    dragMode.value = "none";
    isDragging.value = false;
    interactionStartView.value = null;
    emit("hide-crosshair");
    if (startSnapshot && !sameViewSnapshot(startSnapshot, createViewSnapshot())) {
      rememberViewState();
    }
    if (changed || hadSelection) scheduleRender();
  };

  const onWheel = (event) => {
    if (!visibleData.value.length) return;
    const info = getPointerData(event);
    if (!info) return;
    if (info.isOnPriceAxis) {
      zoomY(event.deltaY < 0 ? 0.88 : 1.14, info.price, { commit: false });
      queueViewStateCommit();
      return;
    }
    const rect = mainCanvas.value.getBoundingClientRect();
    const chartWidth = rect.width - PAD.left - PAD.right;
    const localX = clamp(event.clientX - rect.left, PAD.left, rect.width - PAD.right);
    const anchorRatio = clamp((localX - PAD.left) / Math.max(chartWidth, 1), 0, 1);
    const factor = event.deltaY < 0 ? 0.85 : 1.15;
    zoomTo(Math.round(visibleData.value.length * factor), anchorRatio, { commit: false });
    queueViewStateCommit();
  };

  const onChartClick = (event) => {
    const info = getPointerData(event);
    if (!info) return;

    if (props.activeTool === "hline") {
      emit("add-horizontal-line", info.price);
      return;
    }

    if (props.activeTool === "vline") {
      emit("add-drawing", {
        type: "vline",
        index: info.absoluteIndex,
        price: info.price,
      });
      return;
    }

    const toolTypeMap = {
      tline: "trendline",
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
  };

  const onDoubleClick = () => {
    resetView();
  };

  const handleResize = () => nextTick(() => resizeAll());
  const handleWindowMouseMove = (event) => {
    if (isDragging.value || selectionBox.active) onMouseMove(event);
  };
  const handleWindowMouseUp = () => onMouseUp();

  onMounted(() => {
    syncViewport({ anchorLatest: true });
    nextTick(() => {
      resizeAll();
      rememberViewState();
    });
    window.addEventListener("resize", handleResize);
    window.addEventListener("mousemove", handleWindowMouseMove);
    window.addEventListener("mouseup", handleWindowMouseUp);
  });

  onBeforeUnmount(() => {
    if (renderFrame) cancelAnimationFrame(renderFrame);
    if (historyCommitTimer) window.clearTimeout(historyCommitTimer);
    window.removeEventListener("resize", handleResize);
    window.removeEventListener("mousemove", handleWindowMouseMove);
    window.removeEventListener("mouseup", handleWindowMouseUp);
  });

  watch(
    () => props.ohlcData.length,
    (nextLength, previousLength) => {
      const wasAnchoredToLatest =
        previousLength === 0
        || viewport.startIndex + Math.min(viewport.visibleCount, previousLength) >= previousLength - 1;
      syncViewport({ anchorLatest: wasAnchoredToLatest || nextLength <= viewport.visibleCount });
      scheduleRender();
    },
  );

  watch(
    dataSignature,
    (nextSignature, previousSignature) => {
      if (!previousSignature || nextSignature === previousSignature) return;
      draftDrawing.value = null;
      selectionBox.active = false;
      dragMode.value = "none";
      isDragging.value = false;
      viewHistory.value = [];
      viewHistoryIndex.value = -1;
      resetYScale({ render: false, commit: false });
      scheduleRender();
      nextTick(() => rememberViewState());
    },
  );

  watch(
    () => props.ohlcData,
    () => scheduleRender(),
    { deep: true },
  );

  watch(
    () => props.drawings,
    () => scheduleRender(),
    { deep: true },
  );

  watch(
    () => props.activeInd,
    () => scheduleRender(),
    { deep: true },
  );

  watch(
    () => props.compareSeries,
    () => nextTick(() => resizeAll()),
    { deep: true },
  );

  watch(
    () => props.comparisonMode,
    () => scheduleRender(),
  );

  watch(
    () => canUseLogScale.value,
    (nextValue) => {
      if (!nextValue && priceScaleMode.value === "log") {
        setPriceScaleMode("linear");
      }
    },
  );

  watch(
    () => [viewport.startIndex, viewport.visibleCount, chartMode.value],
    () => scheduleRender(),
  );

  watch(
    () => [chartMode.value, priceScaleMode.value],
    () => {
      writeChartPrefs({
        chartMode: chartMode.value,
        priceScaleMode: priceScaleMode.value,
      });
    },
  );

  watch(
    () => [yAxis.mode, yAxis.min, yAxis.max],
    () => scheduleRender(),
  );

  watch(
    () => props.activeTool,
    (nextTool) => {
      if (!["tline", "fib", "rect", "measure"].includes(nextTool)) {
        draftDrawing.value = null;
      }
      if (nextTool !== "boxzoom") {
        selectionBox.active = false;
      }
      dragMode.value = "none";
      isDragging.value = false;
      scheduleRender();
    },
  );

  watch(
    () => [props.activePanels.rsi, props.activePanels.macd, props.activePanels.stoch, props.compareSeries.length],
    () => nextTick(() => resizeAll()),
  );

  return {
    chartMode,
    priceScaleMode,
    canvasClass: resolvedCanvasClass,
    visibleRangeLabel,
    visibleBarsLabel,
    visibleChangeLabel,
    visibleChangeClass,
    zoomLabel,
    yScaleLabel,
    priceScaleModeLabel,
    interactionHint: interactionHintText,
    canPanLeft,
    canPanRight,
    canZoomIn,
    canZoomOut,
    canUseLogScale,
    canGoBackHistory,
    canGoForwardHistory,
    canResetYScale,
    setChartMode,
    setPriceScaleMode,
    zoomIn,
    zoomOut,
    zoomYIn,
    zoomYOut,
    panLeft,
    panRight,
    goHistoryBack,
    goHistoryForward,
    jumpToLatest,
    resetView,
    resetYScale,
    onMouseDown,
    onMouseMove,
    onMouseLeave,
    onMouseUp,
    onWheel,
    onChartClick,
    onDoubleClick,
  };
}
