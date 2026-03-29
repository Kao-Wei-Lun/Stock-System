import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import {
  calcATRSeries,
  calcADX,
  calcAroon,
  calcBB,
  calcBBPercent,
  calcBBWidth,
  calcCCIValues,
  calcCMF,
  calcDonchianChannels,
  calcEMA,
  calcIchimoku,
  calcMACD,
  calcMA,
  calcMFI,
  calcOBV,
  calcParabolicSAR,
  calcROC,
  calcRSI,
  calcStoch,
  calcSuperTrend,
  calcTrix,
  calcVWAP,
  calcKeltnerChannels,
  calcWilliamsR,
} from "../utils/indicatorUtils";
import { fmtPrice, fmtVol } from "../utils/formatters";

const PAD = { top: 20, right: 70, bottom: 22, left: 10 };
const DEFAULT_VISIBLE_BARS = 90;
const MIN_VISIBLE_BARS = 20;
const PAN_STEP_RATIO = 0.18;
const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
const AUTO_Y_PADDING_RATIO = 0.14;
const AUTO_Y_MIN_PADDING_RATIO = 0.04;
const DRAWING_HIT_TOLERANCE = 10;
const VIEW_HISTORY_LIMIT = 80;
const CHART_PREFS_KEY = "quantvision.chart.prefs.v1";
const DRAWING_LINE_STYLES = {
  solid: [],
  dash: [6, 4],
  dot: [2, 4],
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const clampPositive = (value) => Math.max(value, Number.EPSILON);
const isFiniteNumber = (value) => Number.isFinite(value);

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
    if (!isFiniteNumber(value)) return;
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
    if (isFiniteNumber(values[index])) return index;
  }
  return -1;
};

const drawArea = (ctx, values, xAt, scale, baseY, strokeColor, fillColor) => {
  const safeFirstIndex = values.findIndex((value) => isFiniteNumber(value));
  const lastIndex = findLastDefinedIndex(values);
  if (safeFirstIndex < 0 || lastIndex < 0) return;

  ctx.beginPath();
  ctx.moveTo(xAt(safeFirstIndex), scale(values[safeFirstIndex]));
  for (let index = safeFirstIndex + 1; index <= lastIndex; index += 1) {
    if (!isFiniteNumber(values[index])) continue;
    ctx.lineTo(xAt(index), scale(values[index]));
  }
  ctx.lineTo(xAt(lastIndex), baseY);
  ctx.lineTo(xAt(safeFirstIndex), baseY);
  ctx.closePath();
  ctx.fillStyle = fillColor;
  ctx.fill();

  drawLine(ctx, values, xAt, scale, strokeColor, 1.8);
};

const fillBetweenSeries = (ctx, upperValues, lowerValues, xAt, scale, fillAbove, fillBelow) => {
  const flushSegment = (segment, isAbove) => {
    if (segment.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(xAt(segment[0].index), scale(segment[0].upper));
    segment.forEach((point, pointIndex) => {
      if (pointIndex === 0) return;
      ctx.lineTo(xAt(point.index), scale(point.upper));
    });
    for (let index = segment.length - 1; index >= 0; index -= 1) {
      const point = segment[index];
      ctx.lineTo(xAt(point.index), scale(point.lower));
    }
    ctx.closePath();
    ctx.fillStyle = isAbove ? fillAbove : fillBelow;
    ctx.fill();
  };

  let segment = [];
  let currentAbove = null;

  upperValues.forEach((upper, index) => {
    const lower = lowerValues[index];
    if (!isFiniteNumber(upper) || !isFiniteNumber(lower)) {
      flushSegment(segment, currentAbove);
      segment = [];
      currentAbove = null;
      return;
    }

    const isAbove = upper >= lower;
    if (!segment.length || currentAbove === isAbove) {
      currentAbove = isAbove;
      segment.push({ index, upper, lower });
      return;
    }

    flushSegment(segment, currentAbove);
    segment = [{ index: Math.max(index - 1, 0), upper: upperValues[Math.max(index - 1, 0)], lower: lowerValues[Math.max(index - 1, 0)] }];
    currentAbove = isAbove;
    segment.push({ index, upper, lower });
  });

  flushSegment(segment, currentAbove);
};

const volumeMa = (data, period = 20) => calcMA(data.map((row) => ({ close: row.volume })), period);

export function useChartEngine({
  mainCanvas,
  volumeCanvas,
  compareCanvas,
  rsiCanvas,
  aroonCanvas,
  trixCanvas,
  williamsrCanvas,
  mfiCanvas,
  rocCanvas,
  bbPercentCanvas,
  bbWidthCanvas,
  macdCanvas,
  stochCanvas,
  atrCanvas,
  cciCanvas,
  obvCanvas,
  adxCanvas,
  cmfCanvas,
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
  const drawingDragState = reactive({
    drawingId: null,
    mode: null,
    startAbsoluteIndex: 0,
    startPrice: 0,
    originDrawing: null,
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
    if (props.activeTool === "arrow") {
      return draftDrawing.value?.type === "arrow"
        ? "箭頭線：移動滑鼠預覽，再點一下完成"
        : "箭頭線：先點起點，再點終點";
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
    if (props.activeTool === "note") return "註記：點一下放置，再在屬性面板編輯文字";
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

  const getPaddedPriceRange = (rawMin, rawMax, scaleMode = "linear") => {
    let min = rawMin;
    let max = rawMax;

    if (rawMin === rawMax) {
      const singlePad = Math.max(Math.abs(rawMin) * 0.08, 1);
      min = rawMin - singlePad;
      max = rawMax + singlePad;
    } else {
      const range = rawMax - rawMin;
      const edgeMagnitude = Math.max(Math.abs(rawMax), Math.abs(rawMin));
      const padding = Math.max(range * AUTO_Y_PADDING_RATIO, edgeMagnitude * AUTO_Y_MIN_PADDING_RATIO, 0.05);
      min = rawMin - padding;
      max = rawMax + padding;
    }

    if (scaleMode === "log" && rawMin > 0) {
      min = Math.max(min, rawMin * 0.42);
      max = Math.max(max, clampPositive(rawMax) * 1.08);
    }

    return { min, max };
  };

  const getVisiblePriceScale = (data, extras = [], scaleMode = "linear") => {
    const pricePoints = data.flatMap((row) => [row.high, row.low]).filter(isFiniteNumber);
    extras.forEach((value) => {
      if (Array.isArray(value)) {
        value.forEach((item) => {
          if (isFiniteNumber(item)) pricePoints.push(item);
        });
      } else if (isFiniteNumber(value)) {
        pricePoints.push(value);
      }
    });

    if (!pricePoints.length) {
      return { min: 0, max: 1 };
    }

    const rawMin = Math.min(...pricePoints);
    const rawMax = Math.max(...pricePoints);
    return getPaddedPriceRange(rawMin, rawMax, scaleMode);
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

  const getDrawingDash = (drawing, fallback = []) =>
    drawing?.lineStyle && DRAWING_LINE_STYLES[drawing.lineStyle]
      ? DRAWING_LINE_STYLES[drawing.lineStyle]
      : fallback;

  const getDrawingWidth = (drawing, fallback = 1.2) =>
    Number.isFinite(Number(drawing?.lineWidth)) ? Number(drawing.lineWidth) : fallback;

  const getDrawingFill = (drawing, fallbackColor = "#9b6dff", fallbackOpacity = 0.12) => {
    const color = drawing?.color || fallbackColor;
    const opacity = Number.isFinite(Number(drawing?.fillOpacity))
      ? Number(drawing.fillOpacity)
      : fallbackOpacity;
    return { color, opacity };
  };

  const withOpacity = (color, opacity) => {
    if (!color) return `rgba(155,109,255,${opacity})`;
    const normalized = Math.max(0, Math.min(opacity, 1));
    if (color.startsWith("#")) {
      const hex = color.slice(1);
      const full = hex.length === 3
        ? hex.split("").map((char) => `${char}${char}`).join("")
        : hex;
      if (full.length === 6) {
        const red = parseInt(full.slice(0, 2), 16);
        const green = parseInt(full.slice(2, 4), 16);
        const blue = parseInt(full.slice(4, 6), 16);
        return `rgba(${red},${green},${blue},${normalized})`;
      }
    }
    if (color.startsWith("rgb")) {
      const parts = color.replace(/rgba?\(|\)/g, "").split(",").map((part) => part.trim()).slice(0, 3);
      if (parts.length === 3) return `rgba(${parts.join(",")},${normalized})`;
    }
    return color;
  };

  const parseDateValue = (value) => {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  };

  const getDataRangeDays = (data) => {
    if (!data?.length) return 0;
    const first = parseDateValue(data[0]?.date);
    const last = parseDateValue(data[data.length - 1]?.date);
    if (!first || !last) return 0;
    return Math.abs((last - first) / 86400000);
  };

  const formatAxisDateLabel = (value, rangeDays = 0) => {
    const date = parseDateValue(value);
    if (!date) return String(value || "").slice(5);
    if (rangeDays >= 730) {
      return `${String(date.getFullYear()).slice(2)}/${String(date.getMonth() + 1).padStart(2, "0")}`;
    }
    return `${String(date.getFullYear()).slice(2)}/${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")}`;
  };

  const getTimeTickIndices = (data, targetTickCount = 6) => {
    if (!data.length) return [];
    const indices = new Set([0, data.length - 1]);
    const step = Math.max(1, Math.floor((data.length - 1) / Math.max(targetTickCount - 1, 1)));
    for (let index = 0; index < data.length; index += step) {
      indices.add(index);
    }
    return [...indices].sort((left, right) => left - right);
  };

  const drawTimeAxis = (ctx, canvas, data, layout, options = {}) => {
    if (!data.length) return;
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const bottom = options.bottom ?? (height - PAD.bottom + 12);
    const top = options.top ?? PAD.top;
    const rangeDays = getDataRangeDays(data);
    const tickIndices = getTimeTickIndices(data, options.tickCount ?? 6);

    ctx.save();
    ctx.fillStyle = options.labelColor || "rgba(77,102,128,0.92)";
    ctx.font = options.font || "9px JetBrains Mono";
    tickIndices.forEach((index) => {
      const x = layout.barX(index);
      if (options.showVerticals !== false) {
        ctx.strokeStyle = options.gridColor || "rgba(30,45,61,0.55)";
        ctx.lineWidth = 0.5;
        ctx.beginPath();
        ctx.moveTo(x, top);
        ctx.lineTo(x, options.verticalBottom ?? (height - PAD.bottom));
        ctx.stroke();
      }
      const label = formatAxisDateLabel(data[index].date, rangeDays);
      ctx.fillText(label, Math.max(PAD.left, x - Math.max(18, label.length * 3.4)), bottom);
    });
    ctx.restore();
  };

  const isAuxPanelVisible = (key) => {
    if (props.cleanChartMode) {
      return !!props.activePanels?.[key];
    }
    if (!props.isFullscreen && (key === "macd" || key === "stoch")) {
      return true;
    }
    return !!props.activePanels?.[key];
  };

  const drawCrosshairGuide = (ctx, x, top, bottom, dateLabel = "", width = 0) => {
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
      const left = Math.min(Math.max(PAD.left, x - labelWidth / 2), width - PAD.right - labelWidth);
      ctx.fillStyle = "rgba(255,209,102,0.14)";
      ctx.strokeStyle = "rgba(255,209,102,0.88)";
      ctx.fillRect(left, 2, labelWidth, 14);
      ctx.strokeRect(left, 2, labelWidth, 14);
      ctx.fillStyle = "#ffd166";
      ctx.font = "9px JetBrains Mono";
      ctx.fillText(dateLabel, left + 5, 12);
    }
    ctx.restore();
  };

  const drawHorizontalCrosshairGuide = (ctx, y, left, right, label = "", width = 0, top = PAD.top, bottom = 0) => {
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
  };

  const getCrosshairMarker = (layout, data = visibleData.value) => {
    const absoluteIndex = props.crosshair?.absoluteIndex;
    if (!props.crosshair?.visible || !Number.isInteger(absoluteIndex)) return null;
    if (absoluteIndex < viewport.startIndex || absoluteIndex >= viewport.startIndex + data.length) return null;
    const localIndex = absoluteIndex - viewport.startIndex;
    const rangeDays = getDataRangeDays(data);
    return {
      absoluteIndex,
      localIndex,
      x: layout.barX(localIndex),
      dateLabel: formatAxisDateLabel(data[localIndex]?.date, rangeDays),
    };
  };

  const drawPanelAxisAndCrosshair = (ctx, canvas, data, layout, options = {}) => {
    if (!data?.length) return;
    const panelHeight = canvasHeight(canvas);
    const panelWidth = canvasWidth(canvas);
    const top = options.top ?? 4;
    const verticalBottom = options.verticalBottom ?? (panelHeight - 18);

    drawTimeAxis(ctx, canvas, data, layout, {
      bottom: options.bottom ?? (panelHeight - 4),
      top,
      verticalBottom,
      tickCount: options.tickCount ?? 5,
      labelColor: options.labelColor || "rgba(77,102,128,0.92)",
      gridColor: options.gridColor || "rgba(30,45,61,0.45)",
    });

    const marker = getCrosshairMarker(layout, data);
    if (marker) {
      drawCrosshairGuide(ctx, marker.x, top, verticalBottom, marker.dateLabel, panelWidth);
    }
  };

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

    drawTimeAxis(ctx, canvas, data, { barX: (index) => PAD.left + (index + 0.5) * (mainMetrics.step || 1) }, {
      bottom: height - 8,
      top: PAD.top,
      verticalBottom: height - PAD.bottom,
    });
  };

  const renderBoundedOscillatorPanel = (canvas, values, config = {}) => {
    if (!canvas || !visibleData.value.length) return;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, visibleData.value.length);
    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const min = config.min ?? 0;
    const max = config.max ?? 100;
    const scale = (value) => plotTop + (1 - (value - min) / (max - min || 1)) * chartHeight;

    (config.bands || []).forEach((band) => {
      const topValue = Math.max(band.from, band.to);
      const bottomValue = Math.min(band.from, band.to);
      const topY = scale(topValue);
      const bottomY = scale(bottomValue);
      ctx.fillStyle = band.color;
      ctx.fillRect(PAD.left, topY, width - PAD.left - PAD.right, bottomY - topY);
    });

    (config.levels || []).forEach((level) => {
      ctx.strokeStyle = level.color || "rgba(77,102,128,0.4)";
      ctx.lineWidth = 0.5;
      ctx.setLineDash(level.dash || []);
      ctx.beginPath();
      ctx.moveTo(PAD.left, scale(level.value));
      ctx.lineTo(width - PAD.right, scale(level.value));
      ctx.stroke();
      ctx.setLineDash([]);
      if (level.label !== false) {
        ctx.fillStyle = level.labelColor || "rgba(77,102,128,0.65)";
        ctx.font = "8px JetBrains Mono";
        ctx.fillText(level.text || level.value, width - PAD.right + 2, scale(level.value) + 3);
      }
    });

    (config.lines || []).forEach((line) => {
      drawLine(
        ctx,
        line.values,
        layout.barX,
        scale,
        line.color,
        line.lineWidth ?? 1.4,
        line.dash || [],
      );
    });

    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderRangePanel = (canvas, values, config = {}) => {
    if (!canvas || !visibleData.value.length) return;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const filteredValues = values.filter((value) => value != null);
    if (!filteredValues.length) return;

    const layout = getBarLayout(canvas, visibleData.value.length);
    let min = config.min ?? Math.min(...filteredValues);
    let max = config.max ?? Math.max(...filteredValues);

    if (config.ensureLevels?.length) {
      min = Math.min(min, ...config.ensureLevels);
      max = Math.max(max, ...config.ensureLevels);
    }

    if (min === max) {
      const pad = Math.max(Math.abs(max) * 0.08, config.minPad ?? 1);
      min -= pad;
      max += pad;
    } else {
      const pad = Math.max((max - min) * (config.paddingRatio ?? 0.1), config.minPad ?? 0);
      min -= pad;
      max += pad;
    }

    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotTop + (1 - (value - min) / (max - min || 1)) * chartHeight;

    (config.bands || []).forEach((band) => {
      const topValue = Math.max(band.from, band.to);
      const bottomValue = Math.min(band.from, band.to);
      const topY = scale(topValue);
      const bottomY = scale(bottomValue);
      ctx.fillStyle = band.color;
      ctx.fillRect(PAD.left, topY, width - PAD.left - PAD.right, bottomY - topY);
    });

    (config.levels || []).forEach((level) => {
      ctx.strokeStyle = level.color || "rgba(77,102,128,0.4)";
      ctx.lineWidth = 0.5;
      ctx.setLineDash(level.dash || []);
      ctx.beginPath();
      ctx.moveTo(PAD.left, scale(level.value));
      ctx.lineTo(width - PAD.right, scale(level.value));
      ctx.stroke();
      ctx.setLineDash([]);
      if (level.label !== false) {
        ctx.fillStyle = level.labelColor || "rgba(77,102,128,0.65)";
        ctx.font = "8px JetBrains Mono";
        ctx.fillText(level.text || level.value, width - PAD.right + 2, scale(level.value) + 3);
      }
    });

    if (config.zeroLine) {
      ctx.strokeStyle = "rgba(77,102,128,0.4)";
      ctx.lineWidth = 0.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(PAD.left, scale(0));
      ctx.lineTo(width - PAD.right, scale(0));
      ctx.stroke();
      ctx.setLineDash([]);
    }

    if (config.area) {
      drawArea(
        ctx,
        values,
        layout.barX,
        scale,
        plotBottom,
        config.area.strokeColor,
        config.area.fillColor,
      );
    }

    (config.lines || []).forEach((line) => {
      drawLine(
        ctx,
        line.values,
        layout.barX,
        scale,
        line.color,
        line.lineWidth ?? 1.4,
        line.dash || [],
      );
    });

    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
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

  const drawInstitutionalCostBand = (ctx, canvas, scale, overlay) => {
    if (!overlay) return;
    const width = canvasWidth(canvas);
    const plotWidth = width - PAD.left - PAD.right;
    const bandLow = Number(overlay.bandLow);
    const bandHigh = Number(overlay.bandHigh);
    const institutionPrice = Number(overlay.institutionPrice);
    const retailPrice = Number(overlay.retailPrice);

    if (Number.isFinite(bandLow) && Number.isFinite(bandHigh)) {
      const top = Math.min(scale(bandHigh), scale(bandLow));
      const bottom = Math.max(scale(bandHigh), scale(bandLow));
      ctx.save();
      ctx.fillStyle = "rgba(255, 209, 102, 0.10)";
      ctx.strokeStyle = "rgba(255, 209, 102, 0.46)";
      ctx.lineWidth = 1;
      ctx.setLineDash([6, 4]);
      ctx.fillRect(PAD.left, top, plotWidth, Math.max(1, bottom - top));
      ctx.strokeRect(PAD.left, top, plotWidth, Math.max(1, bottom - top));
      ctx.setLineDash([]);
      ctx.restore();
    }

    if (Number.isFinite(institutionPrice)) {
      drawPriceLabel(ctx, canvas, institutionPrice, scale, "#ffd166", "法 ");
    }
    if (Number.isFinite(retailPrice)) {
      drawPriceLabel(ctx, canvas, retailPrice, scale, "#ff8c42", "散 ");
    }

    const basisText = Number.isFinite(Number(overlay.basis))
      ? `Basis ${Number(overlay.basis) >= 0 ? "+" : ""}${Number(overlay.basis).toFixed(2)}`
      : (overlay.resolvedDate ? `資料日 ${overlay.resolvedDate}` : "");
    const badgeLines = [
      overlay.label,
      [overlay.spotLabel, basisText].filter(Boolean).join(" / "),
    ].filter(Boolean);
    const badgeHeight = 8 + badgeLines.length * 12;
    const badgeWidth = Math.min(plotWidth - 12, Math.max(170, badgeLines.reduce((maxWidth, line) => Math.max(maxWidth, line.length * 7.2), 0) + 16));

    ctx.save();
    ctx.fillStyle = "rgba(13,20,32,0.82)";
    ctx.strokeStyle = "rgba(255,209,102,0.34)";
    ctx.lineWidth = 1;
    ctx.fillRect(PAD.left + 8, PAD.top + 8, badgeWidth, badgeHeight);
    ctx.strokeRect(PAD.left + 8, PAD.top + 8, badgeWidth, badgeHeight);
    ctx.font = "10px JetBrains Mono";
    badgeLines.forEach((line, index) => {
      ctx.fillStyle = index === 0 ? "#ffd166" : "#8ba3c0";
      ctx.fillText(line, PAD.left + 16, PAD.top + 22 + index * 12);
    });
    ctx.restore();
  };

  const drawTrendLine = (ctx, layout, drawing, scale, color = "#00d4ff", dash = []) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = getDrawingWidth(drawing, 1.5);
    ctx.setLineDash(dash);
    ctx.beginPath();
    ctx.moveTo(xForAbsoluteIndex(layout, drawing.startIndex), scale(drawing.startPrice));
    ctx.lineTo(xForAbsoluteIndex(layout, drawing.endIndex), scale(drawing.endPrice));
    ctx.stroke();
    ctx.setLineDash([]);
  };

  const drawArrowLine = (ctx, layout, drawing, scale, color = "#7be7ff", dash = []) => {
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
    ctx.lineTo(endX - headLength * Math.cos(angle - Math.PI / 6), endY - headLength * Math.sin(angle - Math.PI / 6));
    ctx.moveTo(endX, endY);
    ctx.lineTo(endX - headLength * Math.cos(angle + Math.PI / 6), endY - headLength * Math.sin(angle + Math.PI / 6));
    ctx.stroke();
    ctx.restore();
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
    ctx.lineWidth = getDrawingWidth(drawing, 1.2);
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

const drawVerticalLine = (ctx, x, height, color = "#ff8c42", dash = [5, 3], lineWidth = 1) => {
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.setLineDash(dash);
  ctx.beginPath();
  ctx.moveTo(x, PAD.top);
  ctx.lineTo(x, height - PAD.bottom);
  ctx.stroke();
  ctx.setLineDash([]);
};

const drawRectZone = (ctx, xAtAbsolute, drawing, scale, strokeStyle, fillStyle, width, dash = [6, 4]) => {
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
  ctx.lineWidth = getDrawingWidth(drawing, 1.2);
  ctx.setLineDash(dash);
  ctx.fillRect(left, top, zoneWidth, zoneHeight);
  ctx.strokeRect(left, top, zoneWidth, zoneHeight);
  ctx.setLineDash([]);

  const high = Math.max(drawing.startPrice, drawing.endPrice);
  const low = Math.min(drawing.startPrice, drawing.endPrice);
  ctx.fillStyle = strokeStyle;
  ctx.font = "9px JetBrains Mono";
  ctx.fillText(`${high.toFixed(2)} / ${low.toFixed(2)}`, width - PAD.right + 2, top + 10);
};

const drawMeasureTool = (ctx, xAtAbsolute, drawing, scale, width, strokeStyle = "#00d4ff", dash = [4, 3]) => {
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
  ctx.lineWidth = getDrawingWidth(drawing, 1);
  ctx.setLineDash(dash);
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
  const boxWidth = Math.min(textWidth, width - PAD.right - 12);
  const boxHeight = 22;
  const left = Math.min(Math.max(PAD.left, x + 8), width - PAD.right - boxWidth - 6);
  const top = Math.max(PAD.top + 6, y - boxHeight - 8);
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

  const isDrawingSelected = (drawing) =>
    !!drawing?.id && drawing.id === props.selectedDrawingId;

  const isDrawingHidden = (drawing) => Boolean(drawing?.hidden);
  const isDrawingLocked = (drawing) => Boolean(drawing?.locked);

  const drawSelectionHandles = (ctx, points, color = "#ffffff") => {
    ctx.save();
    ctx.fillStyle = color;
    ctx.strokeStyle = "rgba(8,12,18,0.9)";
    ctx.lineWidth = 1;
    points.forEach((point) => {
      if (!point || !Number.isFinite(point.x) || !Number.isFinite(point.y)) return;
      ctx.beginPath();
      ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    });
    ctx.restore();
  };

  const distanceToSegment = (pointX, pointY, x1, y1, x2, y2) => {
    const dx = x2 - x1;
    const dy = y2 - y1;
    if (!dx && !dy) return Math.hypot(pointX - x1, pointY - y1);
    const t = clamp(((pointX - x1) * dx + (pointY - y1) * dy) / (dx * dx + dy * dy), 0, 1);
    const projX = x1 + t * dx;
    const projY = y1 + t * dy;
    return Math.hypot(pointX - projX, pointY - projY);
  };

  const xAtAbsoluteIndex = (absoluteIndex) =>
    PAD.left + (absoluteIndex - viewport.startIndex + 0.5) * mainMetrics.step;

  const scalePriceAtPoint = (value) =>
    scaleY(value, mainMetrics.min, mainMetrics.max, PAD.top, mainMetrics.chartHeight, priceScaleMode.value);

  const findDrawingAtPoint = (info) => {
    if (!props.drawings?.length) return null;

    for (let index = props.drawings.length - 1; index >= 0; index -= 1) {
      const drawing = props.drawings[index];
      if (isDrawingHidden(drawing)) continue;

      if (drawing.type === "buy" || drawing.type === "sell") {
        if (drawing.index < viewport.startIndex || drawing.index >= viewport.startIndex + visibleData.value.length) continue;
        const row = props.ohlcData[drawing.index];
        const markerX = xAtAbsoluteIndex(drawing.index);
        const markerY = drawing.type === "buy" ? scalePriceAtPoint(row.low) + 8 : scalePriceAtPoint(row.high) - 8;
        if (Math.hypot(info.x - markerX, info.y - markerY) <= DRAWING_HIT_TOLERANCE + 2) return drawing;
        continue;
      }

      if (drawing.type === "hline") {
        if (Math.abs(scalePriceAtPoint(drawing.price) - info.y) <= DRAWING_HIT_TOLERANCE) return drawing;
        continue;
      }

      if (drawing.type === "vline") {
        if (drawing.index < viewport.startIndex || drawing.index >= viewport.startIndex + visibleData.value.length) continue;
        if (Math.abs(xAtAbsoluteIndex(drawing.index) - info.x) <= DRAWING_HIT_TOLERANCE) return drawing;
        continue;
      }

      if (drawing.type === "note") {
        if (drawing.index < viewport.startIndex || drawing.index >= viewport.startIndex + visibleData.value.length) continue;
        const x = xAtAbsoluteIndex(drawing.index);
        const y = scalePriceAtPoint(drawing.price);
        const text = drawing.text || drawing.label || "註記";
        const boxWidth = Math.min(180, Math.max(44, text.length * 7 + 16));
        const canvasLimit = mainCanvas.value ? canvasWidth(mainCanvas.value) : (PAD.left + mainMetrics.chartWidth + PAD.right);
        const left = Math.min(Math.max(PAD.left, x + 8), canvasLimit - PAD.right - boxWidth - 6);
        const top = Math.max(PAD.top + 6, y - 30);
        if (
          Math.hypot(info.x - x, info.y - y) <= DRAWING_HIT_TOLERANCE + 3
          || (info.x >= left - 4 && info.x <= left + boxWidth + 4 && info.y >= top - 4 && info.y <= top + 26)
        ) {
          return drawing;
        }
        continue;
      }

      if (!["trendline", "arrow", "fib", "rect", "measure"].includes(drawing.type)) continue;

      const startX = xAtAbsoluteIndex(drawing.startIndex);
      const endX = xAtAbsoluteIndex(drawing.endIndex);
      const startY = scalePriceAtPoint(drawing.startPrice);
      const endY = scalePriceAtPoint(drawing.endPrice);
      const left = Math.min(startX, endX) - DRAWING_HIT_TOLERANCE;
      const right = Math.max(startX, endX) + DRAWING_HIT_TOLERANCE;
      const top = Math.min(startY, endY) - DRAWING_HIT_TOLERANCE;
      const bottom = Math.max(startY, endY) + DRAWING_HIT_TOLERANCE;

      if (drawing.type === "trendline" || drawing.type === "arrow") {
        if (distanceToSegment(info.x, info.y, startX, startY, endX, endY) <= DRAWING_HIT_TOLERANCE) return drawing;
        continue;
      }

      if (drawing.type === "fib") {
        const leftX = Math.min(startX, endX);
        const rightX = Math.max(startX, endX);
        const high = Math.max(drawing.startPrice, drawing.endPrice);
        const low = Math.min(drawing.startPrice, drawing.endPrice);
        const direction = drawing.endPrice >= drawing.startPrice ? 1 : -1;
        if (info.x < leftX - DRAWING_HIT_TOLERANCE || info.x > rightX + DRAWING_HIT_TOLERANCE) continue;
        for (const level of FIB_LEVELS) {
          const price = direction >= 0 ? high - (high - low) * level : low + (high - low) * level;
          const levelY = scalePriceAtPoint(price);
          if (Math.abs(levelY - info.y) <= DRAWING_HIT_TOLERANCE) return drawing;
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
  };

  const clampAbsoluteIndex = (value) =>
    clamp(value, 0, Math.max(props.ohlcData.length - 1, 0));

  const normalizeIndexPair = (startIndex, endIndex) => {
    const maxIndex = Math.max(props.ohlcData.length - 1, 0);
    const lower = Math.min(startIndex, endIndex);
    const upper = Math.max(startIndex, endIndex);
    let adjust = 0;

    if (lower < 0) adjust = -lower;
    if (upper + adjust > maxIndex) adjust += maxIndex - (upper + adjust);

    return {
      startIndex: clampAbsoluteIndex(startIndex + adjust),
      endIndex: clampAbsoluteIndex(endIndex + adjust),
    };
  };

  const getDrawingEditMode = (drawing, info) => {
    if (!drawing || !info) return null;

    if (drawing.type === "hline") return "price";
    if (drawing.type === "note") return "point";
    if (drawing.type === "vline" || drawing.type === "buy" || drawing.type === "sell") return "index";
    if (!["trendline", "arrow", "fib", "rect", "measure"].includes(drawing.type)) return null;

    const startX = xAtAbsoluteIndex(drawing.startIndex);
    const endX = xAtAbsoluteIndex(drawing.endIndex);
    const startY = scalePriceAtPoint(drawing.startPrice);
    const endY = scalePriceAtPoint(drawing.endPrice);

    if (Math.hypot(info.x - startX, info.y - startY) <= DRAWING_HIT_TOLERANCE + 4) return "start";
    if (Math.hypot(info.x - endX, info.y - endY) <= DRAWING_HIT_TOLERANCE + 4) return "end";
    return "move";
  };

  const resetDrawingDragState = () => {
    drawingDragState.drawingId = null;
    drawingDragState.mode = null;
    drawingDragState.startAbsoluteIndex = 0;
    drawingDragState.startPrice = 0;
    drawingDragState.originDrawing = null;
  };

  const startDrawingDrag = (drawing, info) => {
    if (!drawing || !info) return false;
    if (isDrawingLocked(drawing)) {
      emit("select-drawing", drawing.id);
      scheduleRender();
      return false;
    }
    drawingDragState.drawingId = drawing.id;
    drawingDragState.mode = getDrawingEditMode(drawing, info);
    drawingDragState.startAbsoluteIndex = info.absoluteIndex;
    drawingDragState.startPrice = info.price;
    drawingDragState.originDrawing = { ...drawing };
    if (!drawingDragState.mode) {
      resetDrawingDragState();
      return false;
    }
    emit("select-drawing", drawing.id);
    isDragging.value = true;
    dragMode.value = "edit-drawing";
    emit("hide-crosshair");
    return true;
  };

  const updateDraggedDrawing = (info) => {
    const origin = drawingDragState.originDrawing;
    if (!origin || !drawingDragState.drawingId || !drawingDragState.mode) return;

    const deltaBars = info.absoluteIndex - drawingDragState.startAbsoluteIndex;
    const deltaPrice = info.price - drawingDragState.startPrice;
    let nextPatch = null;

    if (drawingDragState.mode === "price") {
      nextPatch = { price: info.price };
    } else if (drawingDragState.mode === "index") {
      nextPatch = { index: clampAbsoluteIndex(origin.index + deltaBars) };
    } else if (drawingDragState.mode === "point") {
      nextPatch = {
        index: clampAbsoluteIndex(origin.index + deltaBars),
        price: origin.price + deltaPrice,
      };
    } else if (drawingDragState.mode === "start") {
      nextPatch = {
        startIndex: clampAbsoluteIndex(info.absoluteIndex),
        startPrice: info.price,
      };
    } else if (drawingDragState.mode === "end") {
      nextPatch = {
        endIndex: clampAbsoluteIndex(info.absoluteIndex),
        endPrice: info.price,
      };
    } else if (drawingDragState.mode === "move") {
      const shifted = normalizeIndexPair(origin.startIndex + deltaBars, origin.endIndex + deltaBars);
      nextPatch = {
        startIndex: shifted.startIndex,
        endIndex: shifted.endIndex,
        startPrice: origin.startPrice + deltaPrice,
        endPrice: origin.endPrice + deltaPrice,
      };
    }

    if (!nextPatch) return;
    emit("update-drawing", drawingDragState.drawingId, nextPatch);
  };

  const getDrawingPriceValues = (drawing) => {
    if (!drawing || isDrawingHidden(drawing)) return [];
    const viewStart = viewport.startIndex;
    const viewEnd = viewport.startIndex + visibleData.value.length - 1;

    if (drawing.type === "hline") {
      return drawing.price != null ? [drawing.price] : [];
    }

    if (drawing.type === "note") {
      return drawing.price != null ? [drawing.price] : [];
    }

    if (drawing.type === "trendline" || drawing.type === "arrow" || drawing.type === "fib" || drawing.type === "rect" || drawing.type === "measure") {
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
    const fullCycleWeek = props.activeInd.cycleMa ? calcMA(fullData, 5) : [];
    const fullCycleMonth = props.activeInd.cycleMa ? calcMA(fullData, 20) : [];
    const fullCycleQuarter = props.activeInd.cycleMa ? calcMA(fullData, 60) : [];
    const fullCycleYear = props.activeInd.cycleMa ? calcMA(fullData, 240) : [];
    const fullMa20 = props.activeInd.ma20 ? calcMA(fullData, props.indicatorSettings.ma20Period) : [];
    const fullMa50 = props.activeInd.ma50 ? calcMA(fullData, props.indicatorSettings.ma50Period) : [];
    const fullMa200 = props.activeInd.ma200 ? calcMA(fullData, props.indicatorSettings.ma200Period) : [];
    const fullEma12 = props.activeInd.ema12 ? calcEMA(fullData, props.indicatorSettings.emaPeriod) : [];
    const fullVwap = props.activeInd.vwap ? calcVWAP(fullData) : [];
    const fullBb = props.activeInd.bb
      ? calcBB(fullData, props.indicatorSettings.bbPeriod, props.indicatorSettings.bbMultiplier)
      : [];
    const fullPsar = props.activeInd.psar
      ? calcParabolicSAR(fullData, props.indicatorSettings.psarStep, props.indicatorSettings.psarMax)
      : [];
    const fullKeltner = props.activeInd.keltner
      ? calcKeltnerChannels(fullData, props.indicatorSettings.kcPeriod, props.indicatorSettings.kcMultiplier)
      : [];
    const fullDonchian = props.activeInd.donchian
      ? calcDonchianChannels(fullData, props.indicatorSettings.donchianPeriod)
      : [];
    const fullIchimoku = props.activeInd.ichimoku
      ? calcIchimoku(
        fullData,
        props.indicatorSettings.ichimokuConversion,
        props.indicatorSettings.ichimokuBase,
        props.indicatorSettings.ichimokuSpanB,
        props.indicatorSettings.ichimokuDisplacement,
      )
      : null;
    const fullSuperTrend = props.activeInd.supertrend
      ? calcSuperTrend(fullData, props.indicatorSettings.supertrendPeriod, props.indicatorSettings.supertrendMultiplier)
      : null;

    const cycleWeek = sliceSeries(fullCycleWeek);
    const cycleMonth = sliceSeries(fullCycleMonth);
    const cycleQuarter = sliceSeries(fullCycleQuarter);
    const cycleYear = sliceSeries(fullCycleYear);
    const ma20 = sliceSeries(fullMa20);
    const ma50 = sliceSeries(fullMa50);
    const ma200 = sliceSeries(fullMa200);
    const ema12 = sliceSeries(fullEma12);
    const vwap = sliceSeries(fullVwap);
    const bbSlice = fullBb.slice(viewport.startIndex, viewport.startIndex + count);
    const psarSlice = sliceSeries(fullPsar);
    const keltnerSlice = fullKeltner.slice(viewport.startIndex, viewport.startIndex + count);
    const donchianSlice = fullDonchian.slice(viewport.startIndex, viewport.startIndex + count);
    const ichimokuConversion = fullIchimoku ? sliceSeries(fullIchimoku.conversion) : [];
    const ichimokuBase = fullIchimoku ? sliceSeries(fullIchimoku.base) : [];
    const ichimokuSpanA = fullIchimoku ? sliceSeries(fullIchimoku.spanA) : [];
    const ichimokuSpanB = fullIchimoku ? sliceSeries(fullIchimoku.spanB) : [];
    const superTrendLine = fullSuperTrend ? sliceSeries(fullSuperTrend.line) : [];
    const superTrendUp = fullSuperTrend
      ? sliceSeries(fullSuperTrend.line.map((value, index) => (fullSuperTrend.trend[index] === 1 ? value : null)))
      : [];
    const superTrendDown = fullSuperTrend
      ? sliceSeries(fullSuperTrend.line.map((value, index) => (fullSuperTrend.trend[index] === -1 ? value : null)))
      : [];
    const overlayValues = [];
    if (props.activeInd.cycleMa) {
      overlayValues.push(cycleWeek, cycleMonth, cycleQuarter, cycleYear);
    }
    if (props.activeInd.ma20) overlayValues.push(ma20);
    if (props.activeInd.ma50) overlayValues.push(ma50);
    if (props.activeInd.ma200) overlayValues.push(ma200);
    if (props.activeInd.ema12) overlayValues.push(ema12);
    if (props.activeInd.vwap) overlayValues.push(vwap);
    if (props.activeInd.ichimoku) {
      overlayValues.push(ichimokuConversion, ichimokuBase, ichimokuSpanA, ichimokuSpanB);
    }
    if (props.activeInd.supertrend) {
      overlayValues.push(superTrendLine);
    }
    if (bbSlice.length) {
      overlayValues.push(bbSlice.map((item) => item.u));
      overlayValues.push(bbSlice.map((item) => item.l));
      overlayValues.push(bbSlice.map((item) => item.m));
    }
    if (psarSlice.length) {
      overlayValues.push(psarSlice);
    }
    if (keltnerSlice.length) {
      overlayValues.push(keltnerSlice.map((item) => item.u));
      overlayValues.push(keltnerSlice.map((item) => item.l));
      overlayValues.push(keltnerSlice.map((item) => item.m));
    }
    if (donchianSlice.length) {
      overlayValues.push(donchianSlice.map((item) => item.u));
      overlayValues.push(donchianSlice.map((item) => item.l));
      overlayValues.push(donchianSlice.map((item) => item.m));
    }
    if (props.institutionalOverlay) {
      overlayValues.push([
        props.institutionalOverlay.bandLow,
        props.institutionalOverlay.bandHigh,
        props.institutionalOverlay.institutionPrice,
        props.institutionalOverlay.retailPrice,
      ]);
    }
    props.drawings.forEach((drawing) => {
      if (!isDrawingHidden(drawing)) overlayValues.push(getDrawingPriceValues(drawing));
    });
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

    if (props.activeInd.cycleMa) {
      drawLine(ctx, cycleWeek, layout.barX, scale, "#7be7ff", 1.1);
      drawLine(ctx, cycleMonth, layout.barX, scale, "#ffd166", 1.15);
      drawLine(ctx, cycleQuarter, layout.barX, scale, "#9b6dff", 1.1);
      drawLine(ctx, cycleYear, layout.barX, scale, "#ff6b6b", 1.2);
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

    if (props.activeInd.psar && psarSlice.length) {
      psarSlice.forEach((value, index) => {
        if (value == null) return;
        const color = data[index].close >= value ? "#00d9a3" : "#ff6b6b";
        ctx.save();
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.95;
        ctx.beginPath();
        ctx.arc(layout.barX(index), scale(value), 2.3, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      });
    }

    if (props.activeInd.keltner && keltnerSlice.length) {
      drawLine(ctx, keltnerSlice.map((item) => item.u), layout.barX, scale, "#7be7ff", 1);
      drawLine(ctx, keltnerSlice.map((item) => item.l), layout.barX, scale, "#7be7ff", 1);
      drawLine(ctx, keltnerSlice.map((item) => item.m), layout.barX, scale, "rgba(123,231,255,0.68)", 0.7, [5, 4]);
    }

    if (props.activeInd.donchian && donchianSlice.length) {
      drawLine(ctx, donchianSlice.map((item) => item.u), layout.barX, scale, "#9b6dff", 1, [6, 3]);
      drawLine(ctx, donchianSlice.map((item) => item.l), layout.barX, scale, "#9b6dff", 1, [6, 3]);
      drawLine(ctx, donchianSlice.map((item) => item.m), layout.barX, scale, "rgba(155,109,255,0.6)", 0.7, [2, 4]);
    }

    if (props.activeInd.ichimoku) {
      fillBetweenSeries(
        ctx,
        ichimokuSpanA,
        ichimokuSpanB,
        layout.barX,
        scale,
        "rgba(0,217,163,0.08)",
        "rgba(255,77,106,0.08)",
      );
      drawLine(ctx, ichimokuConversion, layout.barX, scale, "#7be7ff", 1);
      drawLine(ctx, ichimokuBase, layout.barX, scale, "#9b6dff", 1);
      drawLine(ctx, ichimokuSpanA, layout.barX, scale, "rgba(0,217,163,0.8)", 0.9);
      drawLine(ctx, ichimokuSpanB, layout.barX, scale, "rgba(255,77,106,0.8)", 0.9);
    }

    if (props.activeInd.supertrend) {
      drawLine(ctx, superTrendUp, layout.barX, scale, "#00d9a3", 1.7);
      drawLine(ctx, superTrendDown, layout.barX, scale, "#ff4d6a", 1.7);
    }

    drawInstitutionalCostBand(ctx, canvas, scale, props.institutionalOverlay);

    props.drawings.forEach((drawing) => {
      if (isDrawingHidden(drawing)) return;
      const selected = isDrawingSelected(drawing);
      const locked = isDrawingLocked(drawing);
      if (drawing.type === "buy" || drawing.type === "sell") {
        if (drawing.index < viewport.startIndex || drawing.index >= viewport.startIndex + count) return;
        const localIndex = drawing.index - viewport.startIndex;
        const x = layout.barX(localIndex);
        const color = drawing.type === "buy" ? "#00d9a3" : "#ff4d6a";
        ctx.save();
        ctx.globalAlpha = locked ? 0.72 : 1;
        if (selected) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 12;
        }
        ctx.fillStyle = color;
        ctx.font = selected ? "bold 16px sans-serif" : "bold 13px sans-serif";
        const row = fullData[drawing.index];
        const y = drawing.type === "buy" ? scale(row.low) + 14 : scale(row.high) - 6;
        ctx.fillText(drawing.type === "buy" ? "▲" : "▼", x - (selected ? 6 : 5), y);
        ctx.restore();
        return;
      }

      if (drawing.type === "hline") {
        const color = drawing.color || "#f5a623";
        const y = scale(drawing.price);
        ctx.save();
        ctx.globalAlpha = locked ? 0.72 : 1;
        if (selected) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 10;
        }
        ctx.strokeStyle = color;
        ctx.lineWidth = selected ? getDrawingWidth(drawing, 1) + 0.8 : getDrawingWidth(drawing, 1);
        ctx.setLineDash(getDrawingDash(drawing, locked ? [2, 4] : selected ? [7, 3] : [5, 3]));
        ctx.beginPath();
        ctx.moveTo(PAD.left, y);
        ctx.lineTo(width - PAD.right, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = color;
        ctx.font = selected ? "bold 9px JetBrains Mono" : "9px JetBrains Mono";
        ctx.fillText(drawing.price.toFixed(2), width - PAD.right + 2, y + 3);
        drawDrawingLabel(ctx, drawing.label, PAD.left + 8, y - 4, color);
        ctx.restore();
        return;
      }

      if (drawing.type === "vline") {
        const color = drawing.color || "#ff8c42";
        const x = xForAbsoluteIndex(layout, drawing.index);
        ctx.save();
        ctx.globalAlpha = locked ? 0.72 : 1;
        if (selected) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 10;
        }
        drawVerticalLine(
          ctx,
          x,
          height,
          color,
          getDrawingDash(drawing, locked ? [2, 4] : selected ? [7, 2] : [5, 3]),
          selected ? getDrawingWidth(drawing, 1) + 0.8 : getDrawingWidth(drawing, 1),
        );
        drawDrawingLabel(ctx, drawing.label, x + 6, PAD.top + 18, color);
        if (selected) {
          drawSelectionHandles(ctx, [{ x, y: PAD.top + 14 }], color);
        }
        ctx.restore();
        return;
      }

      if (drawing.type === "trendline") {
        const color = drawing.color || "#00d4ff";
        ctx.save();
        ctx.globalAlpha = locked ? 0.72 : 1;
        if (selected) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 10;
        }
        drawTrendLine(ctx, layout, drawing, scale, color, getDrawingDash(drawing, locked ? [2, 4] : selected ? [3, 2] : []));
        drawDrawingLabel(
          ctx,
          drawing.label,
          xForAbsoluteIndex(layout, drawing.endIndex) + 6,
          scale(drawing.endPrice) - 4,
          color,
        );
        if (selected) {
          drawSelectionHandles(ctx, [
            { x: xForAbsoluteIndex(layout, drawing.startIndex), y: scale(drawing.startPrice) },
            { x: xForAbsoluteIndex(layout, drawing.endIndex), y: scale(drawing.endPrice) },
          ], color);
        }
        ctx.restore();
        return;
      }

      if (drawing.type === "arrow") {
        const color = drawing.color || "#7be7ff";
        ctx.save();
        ctx.globalAlpha = locked ? 0.72 : 1;
        if (selected) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 10;
        }
        drawArrowLine(ctx, layout, drawing, scale, color, getDrawingDash(drawing, locked ? [2, 4] : selected ? [3, 2] : []));
        drawDrawingLabel(
          ctx,
          drawing.label,
          xForAbsoluteIndex(layout, drawing.endIndex) + 6,
          scale(drawing.endPrice) - 4,
          color,
        );
        if (selected) {
          drawSelectionHandles(ctx, [
            { x: xForAbsoluteIndex(layout, drawing.startIndex), y: scale(drawing.startPrice) },
            { x: xForAbsoluteIndex(layout, drawing.endIndex), y: scale(drawing.endPrice) },
          ], color);
        }
        ctx.restore();
        return;
      }

      if (drawing.type === "fib") {
        const color = drawing.color || "#ffd166";
        ctx.save();
        ctx.globalAlpha = locked ? 0.72 : 1;
        if (selected) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 10;
        }
        drawFib(ctx, layout, drawing, scale, width, color, getDrawingDash(drawing, locked ? [2, 4] : selected ? [4, 2] : [6, 4]));
        drawDrawingLabel(
          ctx,
          drawing.label,
          xForAbsoluteIndex(layout, drawing.endIndex) + 6,
          scale(drawing.endPrice) - 4,
          color,
        );
        if (selected) {
          drawSelectionHandles(ctx, [
            { x: xForAbsoluteIndex(layout, drawing.startIndex), y: scale(drawing.startPrice) },
            { x: xForAbsoluteIndex(layout, drawing.endIndex), y: scale(drawing.endPrice) },
          ], color);
        }
        ctx.restore();
        return;
      }

      if (drawing.type === "rect") {
        const color = drawing.color || "#9b6dff";
        const fill = getDrawingFill(drawing, color, 0.12);
        const startX = xForAbsoluteIndex(layout, drawing.startIndex);
        const endX = xForAbsoluteIndex(layout, drawing.endIndex);
        const startY = scale(drawing.startPrice);
        const endY = scale(drawing.endPrice);
        const left = Math.min(startX, endX);
        const top = Math.min(startY, endY);
        const boxWidth = Math.abs(endX - startX);
        const boxHeight = Math.abs(endY - startY);
        ctx.save();
        ctx.globalAlpha = locked ? 0.72 : 1;
        if (selected) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 10;
        }
        ctx.fillStyle = withOpacity(fill.color, Math.min(fill.opacity, 0.95));
        ctx.fillRect(left, top, boxWidth, boxHeight);
        drawRectZone(
          ctx,
          (absoluteIndex) => xForAbsoluteIndex(layout, absoluteIndex),
          drawing,
          scale,
          color,
          "rgba(0,0,0,0)",
          width,
          getDrawingDash(drawing, locked ? [2, 4] : selected ? [4, 2] : [6, 4]),
        );
        drawDrawingLabel(ctx, drawing.label, left + 6, top + 16, color);
        if (selected) {
          drawSelectionHandles(ctx, [
            { x: xForAbsoluteIndex(layout, drawing.startIndex), y: scale(drawing.startPrice) },
            { x: xForAbsoluteIndex(layout, drawing.endIndex), y: scale(drawing.endPrice) },
          ], color);
        }
        ctx.restore();
        return;
      }

      if (drawing.type === "measure") {
        const color = drawing.color || "#00d4ff";
        ctx.save();
        ctx.globalAlpha = locked ? 0.72 : 1;
        if (selected) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 10;
        }
        drawMeasureTool(
          ctx,
          (absoluteIndex) => xForAbsoluteIndex(layout, absoluteIndex),
          drawing,
          scale,
          width,
          color,
          getDrawingDash(drawing, locked ? [2, 4] : selected ? [4, 2] : [4, 3]),
        );
        drawDrawingLabel(
          ctx,
          drawing.label,
          xForAbsoluteIndex(layout, drawing.endIndex) + 6,
          scale(drawing.endPrice) - 4,
          color,
        );
        if (selected) {
          drawSelectionHandles(ctx, [
            { x: xForAbsoluteIndex(layout, drawing.startIndex), y: scale(drawing.startPrice) },
            { x: xForAbsoluteIndex(layout, drawing.endIndex), y: scale(drawing.endPrice) },
          ], color);
        }
        ctx.restore();
        return;
      }

      if (drawing.type === "note") {
        const color = drawing.color || "#ffd166";
        ctx.save();
        ctx.globalAlpha = locked ? 0.72 : 1;
        if (selected) {
          ctx.shadowColor = color;
          ctx.shadowBlur = 10;
        }
        drawNote(ctx, (absoluteIndex) => xForAbsoluteIndex(layout, absoluteIndex), drawing, scale, width);
        if (selected) {
          drawSelectionHandles(ctx, [
            { x: xForAbsoluteIndex(layout, drawing.index), y: scale(drawing.price) },
          ], color);
        }
        ctx.restore();
      }
    });

    if (draftDrawing.value?.type === "trendline") {
      drawTrendLine(ctx, layout, draftDrawing.value, scale, "rgba(0,212,255,0.75)", [6, 4]);
    }

    if (draftDrawing.value?.type === "arrow") {
      drawArrowLine(ctx, layout, draftDrawing.value, scale, "rgba(123,231,255,0.82)", [6, 4]);
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
    const crosshairMarker = getCrosshairMarker(layout, data);
    if (crosshairMarker) {
      drawCrosshairGuide(ctx, crosshairMarker.x, PAD.top, height - PAD.bottom, crosshairMarker.dateLabel, width);
      if (Number.isFinite(props.crosshair?.canvasY)) {
        drawHorizontalCrosshairGuide(
          ctx,
          clamp(props.crosshair.canvasY, PAD.top, height - PAD.bottom),
          PAD.left,
          width - PAD.right,
          props.crosshair.hoverPrice || "",
          width,
          PAD.top,
          height - PAD.bottom,
        );
      }
    }
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

    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotTop + (1 - (value - min) / (max - min || 1)) * chartHeight;

    ctx.strokeStyle = "rgba(30,45,61,0.7)";
    ctx.lineWidth = 0.5;
    ctx.fillStyle = "rgba(77,102,128,0.7)";
    ctx.font = "8px JetBrains Mono";
    for (let index = 0; index <= 4; index += 1) {
      const y = plotTop + index * (chartHeight / 4);
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

    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderVolume = () => {
    if (!volumeCanvas.value || !visibleData.value.length || props.cleanChartMode) return;
    const canvas = volumeCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const data = visibleData.value;

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, data.length);
    const maxVolume = Math.max(...data.map((row) => row.volume || 0), 1);
    const plotTop = 2;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotBottom - (value / maxVolume) * chartHeight;
    const visibleVolumeMa = sliceSeries(volumeMa(props.ohlcData, props.indicatorSettings.volumeMaPeriod));

    data.forEach((row, index) => {
      const barHeight = (row.volume / maxVolume) * chartHeight;
      ctx.fillStyle = row.close >= row.open ? "rgba(0,217,163,0.4)" : "rgba(255,77,106,0.4)";
      ctx.fillRect(
        layout.barX(index) - (layout.barWidth * 0.78) / 2,
        plotBottom - barHeight,
        layout.barWidth * 0.78,
        barHeight,
      );
    });

    drawLine(ctx, visibleVolumeMa, layout.barX, scale, "#f5a623", 1);

    ctx.fillStyle = "rgba(77,102,128,0.6)";
    ctx.font = "9px JetBrains Mono";
    ctx.fillText(`VOL / MA${props.indicatorSettings.volumeMaPeriod}`, 2, 12);
    drawPanelAxisAndCrosshair(ctx, canvas, data, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderRsi = () => {
    if (!rsiCanvas.value || !visibleData.value.length || !props.activePanels.rsi) return;
    const canvas = rsiCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const values = sliceSeries(calcRSI(props.ohlcData, props.indicatorSettings.rsiPeriod));

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, visibleData.value.length);
    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotTop + (1 - value / 100) * chartHeight;

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
    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderAroon = () => {
    if (!aroonCanvas.value || !visibleData.value.length || !props.activePanels.aroon) return;
    const { up, down } = calcAroon(props.ohlcData, props.indicatorSettings.aroonPeriod).reduce(
      (accumulator, item) => {
        accumulator.up.push(item?.up ?? null);
        accumulator.down.push(item?.down ?? null);
        return accumulator;
      },
      { up: [], down: [] },
    );
    renderBoundedOscillatorPanel(aroonCanvas.value, sliceSeries(up), {
      min: 0,
      max: 100,
      levels: [
        { value: 70 },
        { value: 50, dash: [4, 4] },
        { value: 30 },
      ],
      lines: [
        { values: sliceSeries(up), color: "#00d9a3", lineWidth: 1.4 },
        { values: sliceSeries(down), color: "#ff4d6a", lineWidth: 1.4 },
      ],
    });
  };

  const renderTrix = () => {
    if (!trixCanvas.value || !visibleData.value.length || !props.activePanels.trix) return;
    const { trix, signal } = calcTrix(
      props.ohlcData,
      props.indicatorSettings.trixPeriod,
      props.indicatorSettings.trixSignal,
    );
    renderRangePanel(trixCanvas.value, sliceSeries(trix), {
      zeroLine: true,
      minPad: 0.02,
      paddingRatio: 0.14,
      lines: [
        { values: sliceSeries(trix), color: "#8dc1ff", lineWidth: 1.5 },
        { values: sliceSeries(signal), color: "#ffd166", lineWidth: 1.1 },
      ],
    });
  };

  const renderWilliamsR = () => {
    if (!williamsrCanvas.value || !visibleData.value.length || !props.activePanels.williamsr) return;
    const values = sliceSeries(calcWilliamsR(props.ohlcData, props.indicatorSettings.williamsrPeriod));
    renderBoundedOscillatorPanel(williamsrCanvas.value, values, {
      min: -100,
      max: 0,
      bands: [
        { from: 0, to: -20, color: "rgba(255,77,106,0.05)" },
        { from: -80, to: -100, color: "rgba(0,217,163,0.05)" },
      ],
      levels: [
        { value: -20 },
        { value: -50, dash: [4, 4] },
        { value: -80 },
      ],
      lines: [{ values, color: "#7be7ff", lineWidth: 1.45 }],
    });
  };

  const renderMfi = () => {
    if (!mfiCanvas.value || !visibleData.value.length || !props.activePanels.mfi) return;
    const values = sliceSeries(calcMFI(props.ohlcData, props.indicatorSettings.mfiPeriod));
    renderBoundedOscillatorPanel(mfiCanvas.value, values, {
      min: 0,
      max: 100,
      bands: [
        { from: 100, to: 80, color: "rgba(255,77,106,0.05)" },
        { from: 20, to: 0, color: "rgba(0,217,163,0.05)" },
      ],
      levels: [
        { value: 80 },
        { value: 50, dash: [4, 4] },
        { value: 20 },
      ],
      lines: [{ values, color: "#ffd166", lineWidth: 1.45 }],
    });
  };

  const renderRoc = () => {
    if (!rocCanvas.value || !visibleData.value.length || !props.activePanels.roc) return;
    const values = sliceSeries(calcROC(props.ohlcData, props.indicatorSettings.rocPeriod));
    renderRangePanel(rocCanvas.value, values, {
      zeroLine: true,
      minPad: 1,
      paddingRatio: 0.12,
      lines: [{ values, color: "#00d4ff", lineWidth: 1.45 }],
    });
  };

  const renderBbPercent = () => {
    if (!bbPercentCanvas.value || !visibleData.value.length || !props.activePanels.bbPercent) return;
    const values = sliceSeries(
      calcBBPercent(props.ohlcData, props.indicatorSettings.bbPeriod, props.indicatorSettings.bbMultiplier),
    );
    renderRangePanel(bbPercentCanvas.value, values, {
      min: -20,
      max: 120,
      ensureLevels: [0, 50, 100],
      bands: [
        { from: 120, to: 100, color: "rgba(255,77,106,0.05)" },
        { from: 0, to: -20, color: "rgba(0,217,163,0.05)" },
      ],
      levels: [
        { value: 100 },
        { value: 50, dash: [4, 4] },
        { value: 0 },
      ],
      lines: [{ values, color: "#ffd166", lineWidth: 1.45 }],
    });
  };

  const renderBbWidth = () => {
    if (!bbWidthCanvas.value || !visibleData.value.length || !props.activePanels.bbWidth) return;
    const values = sliceSeries(
      calcBBWidth(props.ohlcData, props.indicatorSettings.bbPeriod, props.indicatorSettings.bbMultiplier),
    );
    renderRangePanel(bbWidthCanvas.value, values, {
      minPad: 0.5,
      paddingRatio: 0.16,
      area: {
        strokeColor: "#f5a623",
        fillColor: "rgba(245,166,35,0.12)",
      },
    });
  };

  const renderMacd = () => {
    if (!macdCanvas.value || !visibleData.value.length || !isAuxPanelVisible("macd")) return;
    const canvas = macdCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const { macd, signal, hist } = calcMACD(
      props.ohlcData,
      props.indicatorSettings.macdFast,
      props.indicatorSettings.macdSlow,
      props.indicatorSettings.macdSignal,
    );
    const visibleMacd = sliceSeries(macd);
    const visibleSignal = sliceSeries(signal);
    const visibleHist = sliceSeries(hist);

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, visibleData.value.length);
    const values = [...visibleHist, ...visibleMacd, ...visibleSignal].filter((value) => value != null);
    const min = Math.min(...values, -1);
    const max = Math.max(...values, 1);
    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotTop + (1 - (value - min) / (max - min || 1)) * chartHeight;

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
    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderStoch = () => {
    if (!stochCanvas.value || !visibleData.value.length || !isAuxPanelVisible("stoch")) return;
    const canvas = stochCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const { k, d } = calcStoch(props.ohlcData, props.indicatorSettings.stochK, props.indicatorSettings.stochD);
    const visibleK = sliceSeries(k);
    const visibleD = sliceSeries(d);

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, visibleData.value.length);
    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotTop + (1 - value / 100) * chartHeight;

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
    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderAtr = () => {
    if (!atrCanvas.value || !visibleData.value.length || !props.activePanels.atr) return;
    const canvas = atrCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const atrSeries = calcATRSeries(props.ohlcData, props.indicatorSettings.atrPeriod);
    const visibleAtr = sliceSeries(atrSeries);
    const values = visibleAtr.filter((value) => value != null);

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);
    if (!values.length) return;

    const layout = getBarLayout(canvas, visibleData.value.length);
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
      const pad = Math.max(Math.abs(max) * 0.08, 0.5);
      min = Math.max(0, min - pad);
      max += pad;
    } else {
      const pad = (max - min) * 0.12;
      min = Math.max(0, min - pad);
      max += pad;
    }

    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotTop + (1 - (value - min) / (max - min || 1)) * chartHeight;

    [0, 0.33, 0.66, 1].forEach((ratio) => {
      const level = min + (max - min) * ratio;
      const y = scale(level);
      ctx.strokeStyle = "rgba(77,102,128,0.35)";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(width - PAD.right, y);
      ctx.stroke();
      ctx.fillStyle = "rgba(77,102,128,0.65)";
      ctx.font = "8px JetBrains Mono";
      ctx.fillText(level.toFixed(2), width - PAD.right + 2, y + 3);
    });

    drawArea(
      ctx,
      visibleAtr,
      layout.barX,
      scale,
      plotBottom,
      "#ff8c42",
      "rgba(255,140,66,0.12)",
    );
    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderCci = () => {
    if (!cciCanvas.value || !visibleData.value.length || !props.activePanels.cci) return;
    const canvas = cciCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const visibleCci = sliceSeries(calcCCIValues(props.ohlcData, props.indicatorSettings.cciPeriod));

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const values = visibleCci.filter((value) => value != null);
    if (!values.length) return;

    const layout = getBarLayout(canvas, visibleData.value.length);
    let min = Math.min(-200, ...values);
    let max = Math.max(200, ...values);
    if (min === max) {
      min -= 20;
      max += 20;
    } else {
      const pad = (max - min) * 0.08;
      min -= pad;
      max += pad;
    }

    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotTop + (1 - (value - min) / (max - min || 1)) * chartHeight;

    ctx.fillStyle = "rgba(255,77,106,0.05)";
    ctx.fillRect(PAD.left, scale(max), width - PAD.left - PAD.right, scale(100) - scale(max));
    ctx.fillStyle = "rgba(0,217,163,0.05)";
    ctx.fillRect(PAD.left, scale(-100), width - PAD.left - PAD.right, scale(min) - scale(-100));

    [200, 100, 0, -100, -200].forEach((level) => {
      ctx.strokeStyle = "rgba(77,102,128,0.4)";
      ctx.lineWidth = 0.5;
      ctx.setLineDash(level === 0 ? [4, 4] : []);
      ctx.beginPath();
      ctx.moveTo(PAD.left, scale(level));
      ctx.lineTo(width - PAD.right, scale(level));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(77,102,128,0.65)";
      ctx.font = "8px JetBrains Mono";
      ctx.fillText(level, width - PAD.right + 2, scale(level) + 3);
    });

    drawLine(ctx, visibleCci, layout.barX, scale, "#9b6dff", 1.5);
    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderObv = () => {
    if (!obvCanvas.value || !visibleData.value.length || !props.activePanels.obv) return;
    const canvas = obvCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const visibleObv = sliceSeries(calcOBV(props.ohlcData));

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const values = visibleObv.filter((value) => value != null);
    if (!values.length) return;

    const layout = getBarLayout(canvas, visibleData.value.length);
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
      min -= 1;
      max += 1;
    } else {
      const pad = (max - min) * 0.08;
      min -= pad;
      max += pad;
    }

    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotTop + (1 - (value - min) / (max - min || 1)) * chartHeight;

    [0, 0.5, 1].forEach((ratio) => {
      const level = min + (max - min) * ratio;
      const y = scale(level);
      ctx.strokeStyle = "rgba(77,102,128,0.35)";
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(width - PAD.right, y);
      ctx.stroke();
    });

    drawArea(
      ctx,
      visibleObv,
      layout.barX,
      scale,
      plotBottom,
      "#00d4ff",
      "rgba(0,212,255,0.10)",
    );
    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderAdx = () => {
    if (!adxCanvas.value || !visibleData.value.length || !props.activePanels.adx) return;
    const canvas = adxCanvas.value;
    const ctx = canvas.getContext("2d");
    const width = canvasWidth(canvas);
    const height = canvasHeight(canvas);
    const { plusDI, minusDI, adx } = calcADX(props.ohlcData, props.indicatorSettings.adxPeriod);
    const visiblePlus = sliceSeries(plusDI);
    const visibleMinus = sliceSeries(minusDI);
    const visibleAdx = sliceSeries(adx);

    setupCtx(ctx);
    ctx.clearRect(0, 0, width, height);

    const layout = getBarLayout(canvas, visibleData.value.length);
    const plotTop = 4;
    const plotBottom = height - 18;
    const chartHeight = plotBottom - plotTop;
    const scale = (value) => plotTop + (1 - value / 100) * chartHeight;

    [50, 25, 0].forEach((level) => {
      ctx.strokeStyle = "rgba(77,102,128,0.4)";
      ctx.lineWidth = 0.5;
      ctx.setLineDash(level === 25 ? [4, 4] : []);
      ctx.beginPath();
      ctx.moveTo(PAD.left, scale(level));
      ctx.lineTo(width - PAD.right, scale(level));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(77,102,128,0.65)";
      ctx.font = "8px JetBrains Mono";
      ctx.fillText(level, width - PAD.right + 2, scale(level) + 3);
    });

    drawLine(ctx, visibleAdx, layout.barX, scale, "#ffd166", 1.4);
    drawLine(ctx, visiblePlus, layout.barX, scale, "#00d9a3", 1.1);
    drawLine(ctx, visibleMinus, layout.barX, scale, "#ff4d6a", 1.1);
    drawPanelAxisAndCrosshair(ctx, canvas, visibleData.value, layout, {
      top: plotTop,
      verticalBottom: plotBottom,
      bottom: height - 4,
    });
  };

  const renderCmf = () => {
    if (!cmfCanvas.value || !visibleData.value.length || !props.activePanels.cmf) return;
    const values = sliceSeries(calcCMF(props.ohlcData, props.indicatorSettings.cmfPeriod));
    renderRangePanel(cmfCanvas.value, values, {
      ensureLevels: [-0.2, 0, 0.2],
      zeroLine: true,
      minPad: 0.02,
      paddingRatio: 0.12,
      bands: [
        { from: 0.2, to: 0, color: "rgba(0,217,163,0.04)" },
        { from: 0, to: -0.2, color: "rgba(255,77,106,0.04)" },
      ],
      levels: [
        { value: 0.2 },
        { value: 0, dash: [4, 4] },
        { value: -0.2 },
      ],
      lines: [{ values, color: "#00d9a3", lineWidth: 1.4 }],
    });
  };

  const clearAll = () => {
    [
      mainCanvas.value,
      compareCanvas.value,
      volumeCanvas.value,
      rsiCanvas.value,
      aroonCanvas.value,
      trixCanvas.value,
      williamsrCanvas.value,
      mfiCanvas.value,
      rocCanvas.value,
      bbPercentCanvas.value,
      bbWidthCanvas.value,
      macdCanvas.value,
      stochCanvas.value,
      atrCanvas.value,
      cciCanvas.value,
      obvCanvas.value,
      adxCanvas.value,
      cmfCanvas.value,
    ]
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
    renderAroon();
    renderTrix();
    renderWilliamsR();
    renderMfi();
    renderRoc();
    renderBbPercent();
    renderBbWidth();
    renderMacd();
    renderStoch();
    renderAtr();
    renderCci();
    renderObv();
    renderAdx();
    renderCmf();
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
    resizeCanvas(aroonCanvas.value, aroonCanvas.value?.parentElement);
    resizeCanvas(trixCanvas.value, trixCanvas.value?.parentElement);
    resizeCanvas(williamsrCanvas.value, williamsrCanvas.value?.parentElement);
    resizeCanvas(mfiCanvas.value, mfiCanvas.value?.parentElement);
    resizeCanvas(rocCanvas.value, rocCanvas.value?.parentElement);
    resizeCanvas(bbPercentCanvas.value, bbPercentCanvas.value?.parentElement);
    resizeCanvas(bbWidthCanvas.value, bbWidthCanvas.value?.parentElement);
    resizeCanvas(macdCanvas.value, macdCanvas.value?.parentElement);
    resizeCanvas(stochCanvas.value, stochCanvas.value?.parentElement);
    resizeCanvas(atrCanvas.value, atrCanvas.value?.parentElement);
    resizeCanvas(cciCanvas.value, cciCanvas.value?.parentElement);
    resizeCanvas(obvCanvas.value, obvCanvas.value?.parentElement);
    resizeCanvas(adxCanvas.value, adxCanvas.value?.parentElement);
    resizeCanvas(cmfCanvas.value, cmfCanvas.value?.parentElement);
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
      || !["trendline", "arrow", "fib", "rect", "measure"].includes(draftDrawing.value.type)
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
      const paddedRange = getPaddedPriceRange(
        Math.min(priceBottom, priceTop),
        Math.max(priceBottom, priceTop),
        priceScaleMode.value,
      );
      setManualYRange(paddedRange.min, paddedRange.max, { render: false });
      changed = true;
    }

    selectionBox.active = false;
    return changed;
  };

  const onMouseDown = (event) => {
    if (event.button !== 0 || !visibleData.value.length) return;
    const info = getPointerData(event);
    if (!info) return;

    if (props.activeTool === "cursor") {
      const hitDrawing = findDrawingAtPoint(info);
      if (hitDrawing) {
        interactionStartView.value = createViewSnapshot();
        startDrawingDrag(hitDrawing, info);
        return;
      }
    }

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

    if (isDragging.value && dragMode.value === "edit-drawing") {
      updateDraggedDrawing(info);
      emit("hide-crosshair");
      return;
    }

    const prevRow = props.ohlcData[info.absoluteIndex - 1];
    const referenceClose = prevRow?.close ?? info.row.open ?? info.row.close;
    const candleChange = (info.row.close ?? 0) - (referenceClose ?? 0);
    const candleChangePct = referenceClose ? (candleChange / referenceClose) * 100 : 0;

    emit("update-crosshair", {
      visible: true,
      canvasX: info.x,
      canvasY: info.y,
      date: info.row.date,
      hoverPrice: fmtPrice(info.price),
      open: fmtPrice(info.row.open),
      high: fmtPrice(info.row.high),
      low: fmtPrice(info.row.low),
      close: fmtPrice(info.row.close),
      change: `${candleChange >= 0 ? "+" : ""}${fmtPrice(candleChange)}`,
      changePct: `${candleChangePct >= 0 ? "+" : ""}${candleChangePct.toFixed(2)}%`,
      volume: fmtVol(info.row.volume),
      absoluteIndex: info.absoluteIndex,
    });

    scheduleRender();
    updateDraftDrawing(info);
  };

  const onMouseLeave = () => {
    if (!isDragging.value && !selectionBox.active) emit("hide-crosshair");
  };

  const onMouseUp = () => {
    const hadSelection = selectionBox.active;
    const changed = hadSelection ? finishSelectionZoom() : false;
    const startSnapshot = interactionStartView.value;
    const wasEditingDrawing = dragMode.value === "edit-drawing";
    dragMode.value = "none";
    isDragging.value = false;
    interactionStartView.value = null;
    resetDrawingDragState();
    emit("hide-crosshair");
    if (startSnapshot && !sameViewSnapshot(startSnapshot, createViewSnapshot())) {
      rememberViewState();
    }
    if (changed || hadSelection || wasEditingDrawing) scheduleRender();
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

    if (props.activeTool === "cursor") {
      emit("select-drawing", findDrawingAtPoint(info)?.id || null);
      scheduleRender();
      return;
    }

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

    if (props.activeTool === "note") {
      emit("add-drawing", {
        type: "note",
        index: info.absoluteIndex,
        price: info.price,
      });
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
      resetDrawingDragState();
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
    () => props.selectedDrawingId,
    () => scheduleRender(),
  );

  watch(
    () => props.activeInd,
    () => scheduleRender(),
    { deep: true },
  );

  watch(
    () => props.indicatorSettings,
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
    () => [
      props.crosshair?.visible,
      props.crosshair?.absoluteIndex,
      props.crosshair?.canvasY,
      props.crosshair?.hoverPrice,
    ],
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
      if (!["tline", "arrow", "fib", "rect", "measure"].includes(nextTool)) {
        draftDrawing.value = null;
      }
      if (nextTool !== "boxzoom") {
        selectionBox.active = false;
      }
      dragMode.value = "none";
      isDragging.value = false;
      resetDrawingDragState();
      scheduleRender();
    },
  );

  watch(
    () => [
      props.activePanels.rsi,
      props.activePanels.aroon,
      props.activePanels.trix,
      props.activePanels.williamsr,
      props.activePanels.mfi,
      props.activePanels.roc,
      props.activePanels.bbPercent,
      props.activePanels.bbWidth,
      props.activePanels.macd,
      props.activePanels.stoch,
      props.activePanels.atr,
      props.activePanels.cci,
      props.activePanels.obv,
      props.activePanels.adx,
      props.activePanels.cmf,
      props.compareSeries.length,
      props.isFullscreen,
      props.cleanChartMode,
    ],
    () => nextTick(() => resizeAll()),
  );

  return {
    chartMode,
    priceScaleMode,
    visibleData,
    viewportStartIndex: computed(() => viewport.startIndex),
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
