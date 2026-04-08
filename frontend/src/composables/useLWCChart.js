import { computed, onBeforeUnmount, ref, shallowRef, watch } from "vue";
import {
  AreaSeries,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  PriceScaleMode,
  createChart,
} from "lightweight-charts";

import { fmtPrice, fmtVol } from "../utils/formatters";

const DEFAULT_VISIBLE_BARS = 120;
const MIN_VISIBLE_BARS = 20;
const PAN_STEP_RATIO = 0.18;

const SERIES_DEFINITIONS = {
  candles: {
    key: "Candlestick",
    definition: CandlestickSeries,
    options: {
      upColor: "#00d9a3",
      downColor: "#ff4d6a",
      wickUpColor: "#00d9a3",
      wickDownColor: "#ff4d6a",
      borderVisible: false,
      priceLineVisible: true,
      lastValueVisible: true,
    },
  },
  line: {
    key: "Line",
    definition: LineSeries,
    options: {
      color: "#7be7ff",
      lineWidth: 2,
      priceLineVisible: true,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
    },
  },
  area: {
    key: "Area",
    definition: AreaSeries,
    options: {
      lineColor: "#7be7ff",
      topColor: "rgba(123, 231, 255, 0.32)",
      bottomColor: "rgba(123, 231, 255, 0.04)",
      lineWidth: 2,
      priceLineVisible: true,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
    },
  },
};

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function normalizeChartMode(mode) {
  return ["candles", "line", "area"].includes(mode) ? mode : "candles";
}

function normalizePriceScaleMode(mode) {
  return mode === "log" ? "log" : "linear";
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

function formatRangeDate(dateString) {
  if (!dateString) return "—";
  const parsed = new Date(String(dateString).includes(" ") ? String(dateString).replace(" ", "T") : dateString);
  if (Number.isNaN(parsed.getTime())) return String(dateString).slice(0, 10);
  return parsed.toLocaleDateString("zh-TW");
}

function buildCrosshairPayload(row, absoluteIndex, point) {
  if (!row) return null;
  const referenceClose = row.open ?? row.close ?? 0;
  const candleChange = Number(row.close ?? 0) - Number(referenceClose ?? 0);
  const candleChangePct = referenceClose ? (candleChange / referenceClose) * 100 : 0;

  return {
    visible: true,
    canvasX: point?.x ?? null,
    canvasY: point?.y ?? null,
    date: row.date || "—",
    hoverPrice: fmtPrice(row.close),
    open: fmtPrice(row.open),
    high: fmtPrice(row.high),
    low: fmtPrice(row.low),
    close: fmtPrice(row.close),
    change: `${candleChange >= 0 ? "+" : ""}${fmtPrice(candleChange)}`,
    changePct: `${candleChangePct >= 0 ? "+" : ""}${candleChangePct.toFixed(2)}%`,
    volume: fmtVol(row.volume),
    absoluteIndex,
  };
}

export function useLWCChart({
  chartContainer,
  props,
  emit,
}) {
  const chartApi = shallowRef(null);
  const mainSeries = shallowRef(null);
  const volumeSeries = shallowRef(null);
  const resizeObserver = shallowRef(null);
  const chartMode = ref("candles");
  const priceScaleMode = ref("linear");
  const visibleLogicalRange = ref(null);
  const viewportStartIndex = computed(() => {
    if (!chartRows.value.length || !visibleLogicalRange.value) return 0;
    return clamp(Math.floor(visibleLogicalRange.value.from), 0, Math.max(chartRows.value.length - 1, 0));
  });

  const chartRows = computed(() => (
    Array.isArray(props.ohlcData)
      ? props.ohlcData
        .map((row, index) => {
          const time = toChartTime(row?.date);
          if (!time) return null;
          const open = Number(row.open ?? row.close);
          const high = Number(row.high ?? row.close);
          const low = Number(row.low ?? row.close);
          const close = Number(row.close ?? row.open);
          if (![open, high, low, close].every(Number.isFinite)) return null;
          return {
            index,
            raw: row,
            time,
            candle: { time, open, high, low, close },
            line: { time, value: close },
            area: { time, value: close },
            volume: {
              time,
              value: Math.max(0, Number(row.volume ?? 0)),
              color: close >= open ? "rgba(0, 217, 163, 0.76)" : "rgba(255, 77, 106, 0.76)",
            },
          };
        })
        .filter(Boolean)
      : []
  ));

  const visibleData = computed(() => {
    const rows = chartRows.value;
    if (!rows.length) return [];
    if (!visibleLogicalRange.value) return rows.map((entry) => entry.raw);
    const start = clamp(Math.floor(visibleLogicalRange.value.from), 0, Math.max(rows.length - 1, 0));
    const end = clamp(Math.ceil(visibleLogicalRange.value.to), start + 1, rows.length);
    return rows.slice(start, end).map((entry) => entry.raw);
  });

  const visibleRangeLabel = computed(() => {
    const rows = visibleData.value;
    if (!rows.length) return "可視範圍：—";
    return `可視範圍：${formatRangeDate(rows[0].date)} → ${formatRangeDate(rows[rows.length - 1].date)}`;
  });

  const visibleBarsLabel = computed(() => `可視 K 數：${visibleData.value.length} 根`);

  const visibleChangeLabel = computed(() => {
    const rows = visibleData.value;
    if (rows.length < 2) return "區間漲跌：—";
    const firstClose = Number(rows[0].close ?? 0);
    const lastClose = Number(rows[rows.length - 1].close ?? 0);
    if (!firstClose || !Number.isFinite(lastClose)) return "區間漲跌：—";
    const changePct = ((lastClose - firstClose) / firstClose) * 100;
    return `區間漲跌：${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`;
  });

  const visibleChangeClass = computed(() => {
    const label = visibleChangeLabel.value;
    if (label.includes("+")) return "up";
    if (label.includes("-")) return "dn";
    return "";
  });

  const zoomLabel = computed(() => `縮放：${visibleData.value.length || 0} 根`);
  const yScaleLabel = computed(() => "Y 軸：LWC");
  const priceScaleModeLabel = computed(() => (priceScaleMode.value === "log" ? "對數" : "線性"));
  const interactionHint = computed(() => (
    "LWC Phase A：主圖、成交量與十字線已接入；繪圖工具與子指標面板後續遷移。"
  ));
  const canvasClass = computed(() => "chart-canvas-lwc");
  const canUseLogScale = computed(() => chartRows.value.every((entry) => entry.candle.low > 0));
  const canGoBackHistory = computed(() => false);
  const canGoForwardHistory = computed(() => false);
  const canPanLeft = computed(() => {
    if (!visibleLogicalRange.value) return false;
    return visibleLogicalRange.value.from > 0;
  });
  const canPanRight = computed(() => {
    if (!visibleLogicalRange.value) return false;
    return visibleLogicalRange.value.to < chartRows.value.length;
  });
  const canZoomIn = computed(() => {
    if (!visibleLogicalRange.value) return chartRows.value.length > MIN_VISIBLE_BARS;
    return visibleLogicalRange.value.to - visibleLogicalRange.value.from > MIN_VISIBLE_BARS;
  });
  const canZoomOut = computed(() => {
    if (!visibleLogicalRange.value) return false;
    return visibleLogicalRange.value.to - visibleLogicalRange.value.from < chartRows.value.length + 8;
  });
  const canResetYScale = computed(() => Boolean(mainSeries.value));

  function destroyChart() {
    resizeObserver.value?.disconnect();
    resizeObserver.value = null;
    chartApi.value?.remove();
    chartApi.value = null;
    mainSeries.value = null;
    volumeSeries.value = null;
    visibleLogicalRange.value = null;
  }

  function applyPriceScaleOptions() {
    if (!mainSeries.value) return;
    const mode = priceScaleMode.value === "log" && canUseLogScale.value
      ? PriceScaleMode.Logarithmic
      : PriceScaleMode.Normal;
    mainSeries.value.priceScale().applyOptions({
      autoScale: true,
      mode,
    });
  }

  function handleVisibleLogicalRangeChange(range) {
    visibleLogicalRange.value = range;
  }

  function handleCrosshairMove(param) {
    if (!param?.point || param.time == null || param.logical == null) {
      emit("hide-crosshair");
      return;
    }

    const absoluteIndex = clamp(Math.round(param.logical), 0, Math.max(chartRows.value.length - 1, 0));
    const row = chartRows.value[absoluteIndex]?.raw || props.ohlcData?.[absoluteIndex] || null;
    const payload = buildCrosshairPayload(row, absoluteIndex, param.point);
    if (!payload) {
      emit("hide-crosshair");
      return;
    }
    emit("update-crosshair", payload);
  }

  function createMainSeries() {
    if (!chartApi.value) return;
    const currentRange = chartApi.value.timeScale().getVisibleLogicalRange();
    if (mainSeries.value) {
      chartApi.value.removeSeries(mainSeries.value);
      mainSeries.value = null;
    }

    const definition = SERIES_DEFINITIONS[chartMode.value] || SERIES_DEFINITIONS.candles;
    mainSeries.value = chartApi.value.addSeries(definition.definition, definition.options, 0);
    const data = chartRows.value.map((entry) => entry[chartMode.value]);
    mainSeries.value.setData(data);
    applyPriceScaleOptions();

    if (currentRange) {
      chartApi.value.timeScale().setVisibleLogicalRange(currentRange);
    }
  }

  function syncVolumeSeries() {
    if (!chartApi.value) return;
    if (props.cleanChartMode) {
      if (volumeSeries.value) {
        chartApi.value.removeSeries(volumeSeries.value);
        volumeSeries.value = null;
      }
      return;
    }

    if (!volumeSeries.value) {
      volumeSeries.value = chartApi.value.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceLineVisible: false,
        lastValueVisible: false,
      }, 1);
    }

    volumeSeries.value.setData(chartRows.value.map((entry) => entry.volume));

    const panes = chartApi.value.panes();
    if (panes[0]) panes[0].setStretchFactor(3);
    if (panes[1]) panes[1].setStretchFactor(1);
  }

  function applyDefaultVisibleRange() {
    if (!chartApi.value || !chartRows.value.length) return;
    const rowCount = chartRows.value.length;
    const from = Math.max(0, rowCount - DEFAULT_VISIBLE_BARS);
    const to = rowCount + 4;
    chartApi.value.timeScale().setVisibleLogicalRange({ from, to });
  }

  function resizeChart() {
    const container = chartContainer.value;
    if (!chartApi.value || !container) return;
    chartApi.value.resize(
      Math.max(1, Math.round(container.clientWidth)),
      Math.max(1, Math.round(container.clientHeight)),
    );
  }

  function initializeChart() {
    if (chartApi.value || !chartContainer.value) return;
    chartApi.value = createChart(chartContainer.value, {
      autoSize: true,
      layout: {
        background: { color: "#07121c" },
        textColor: "#98a7b7",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(26, 41, 56, 0.55)" },
        horzLines: { color: "rgba(26, 41, 56, 0.55)" },
      },
      rightPriceScale: {
        borderColor: "rgba(57, 79, 99, 0.58)",
      },
      timeScale: {
        borderColor: "rgba(57, 79, 99, 0.58)",
        fixLeftEdge: false,
        fixRightEdge: false,
        rightOffset: 4,
        timeVisible: false,
      },
      crosshair: {
        vertLine: {
          color: "rgba(255, 209, 102, 0.72)",
          labelBackgroundColor: "#80601c",
        },
        horzLine: {
          color: "rgba(255, 209, 102, 0.4)",
          labelBackgroundColor: "#3a4d63",
        },
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: {
          price: true,
          time: true,
        },
        mouseWheel: true,
        pinch: true,
      },
    });

    chartApi.value.timeScale().subscribeVisibleLogicalRangeChange(handleVisibleLogicalRangeChange);
    chartApi.value.subscribeCrosshairMove(handleCrosshairMove);

    createMainSeries();
    syncVolumeSeries();
    applyDefaultVisibleRange();

    if (typeof ResizeObserver === "function") {
      resizeObserver.value = new ResizeObserver(() => resizeChart());
      resizeObserver.value.observe(chartContainer.value);
    } else {
      window.addEventListener("resize", resizeChart);
    }
  }

  function getCurrentLogicalRange() {
    return chartApi.value?.timeScale().getVisibleLogicalRange() || null;
  }

  function setLogicalRange(range) {
    if (!chartApi.value || !range) return;
    chartApi.value.timeScale().setVisibleLogicalRange(range);
  }

  function zoomBy(factor) {
    const range = getCurrentLogicalRange();
    if (!range) return;
    const center = (range.from + range.to) / 2;
    const nextLength = clamp(
      (range.to - range.from) * factor,
      MIN_VISIBLE_BARS,
      Math.max(chartRows.value.length + 8, MIN_VISIBLE_BARS),
    );
    setLogicalRange({
      from: center - nextLength / 2,
      to: center + nextLength / 2,
    });
  }

  function panBy(ratio) {
    const range = getCurrentLogicalRange();
    if (!range) return;
    const length = range.to - range.from;
    const delta = length * ratio;
    setLogicalRange({
      from: range.from + delta,
      to: range.to + delta,
    });
  }

  function zoomPriceRange(factor) {
    if (!mainSeries.value) return;
    const scale = mainSeries.value.priceScale();
    const range = scale.getVisibleRange();
    if (!range) {
      scale.setAutoScale(true);
      return;
    }
    const center = (range.from + range.to) / 2;
    const halfRange = ((range.to - range.from) / 2) * factor;
    scale.setAutoScale(false);
    scale.setVisibleRange({
      from: center - halfRange,
      to: center + halfRange,
    });
  }

  function setChartMode(mode) {
    const nextMode = normalizeChartMode(mode);
    if (nextMode === chartMode.value) return;
    chartMode.value = nextMode;
  }

  function setPriceScaleMode(mode) {
    const nextMode = normalizePriceScaleMode(mode);
    if (nextMode === "log" && !canUseLogScale.value) return;
    priceScaleMode.value = nextMode;
  }

  function zoomIn() {
    zoomBy(0.82);
  }

  function zoomOut() {
    zoomBy(1.18);
  }

  function zoomYIn() {
    zoomPriceRange(0.82);
  }

  function zoomYOut() {
    zoomPriceRange(1.18);
  }

  function panLeft() {
    panBy(-PAN_STEP_RATIO);
  }

  function panRight() {
    panBy(PAN_STEP_RATIO);
  }

  function goHistoryBack() {}

  function goHistoryForward() {}

  function jumpToLatest() {
    chartApi.value?.timeScale().scrollToRealTime();
  }

  function resetView() {
    applyDefaultVisibleRange();
  }

  function resetYScale() {
    if (!mainSeries.value) return;
    mainSeries.value.priceScale().setAutoScale(true);
    applyPriceScaleOptions();
  }

  function onMouseDown() {}

  function onMouseMove() {}

  function onMouseLeave() {}

  function onMouseUp() {}

  function onWheel() {}

  function onChartClick() {}

  function onDoubleClick() {
    resetView();
  }

  watch(
    () => chartContainer.value,
    (value) => {
      if (value) initializeChart();
      else destroyChart();
    },
    { immediate: true },
  );

  watch(
    chartMode,
    () => {
      if (!chartApi.value) return;
      createMainSeries();
    },
  );

  watch(
    () => props.cleanChartMode,
    () => {
      if (!chartApi.value) return;
      syncVolumeSeries();
      resizeChart();
    },
  );

  watch(
    chartRows,
    (rows, previousRows) => {
      if (!chartApi.value) return;
      createMainSeries();
      syncVolumeSeries();
      if (!previousRows?.length || props.currentTicker !== previousTicker.value) {
        applyDefaultVisibleRange();
      }
      if (!rows.length) {
        emit("hide-crosshair");
      }
    },
    { deep: true },
  );

  const previousTicker = ref(props.currentTicker);
  watch(
    () => props.currentTicker,
    (ticker) => {
      previousTicker.value = ticker;
      if (chartApi.value) {
        applyDefaultVisibleRange();
      }
      emit("hide-crosshair");
    },
  );

  watch(
    priceScaleMode,
    () => applyPriceScaleOptions(),
  );

  onBeforeUnmount(() => {
    if (!resizeObserver.value) {
      window.removeEventListener("resize", resizeChart);
    }
    if (chartApi.value) {
      chartApi.value.timeScale().unsubscribeVisibleLogicalRangeChange(handleVisibleLogicalRangeChange);
      chartApi.value.unsubscribeCrosshairMove(handleCrosshairMove);
    }
    destroyChart();
  });

  return {
    chartMode,
    priceScaleMode,
    visibleData,
    viewportStartIndex,
    canvasClass,
    visibleRangeLabel,
    visibleBarsLabel,
    visibleChangeLabel,
    visibleChangeClass,
    zoomLabel,
    yScaleLabel,
    priceScaleModeLabel,
    interactionHint,
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
