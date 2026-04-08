<template>
  <div class="center" :class="{ 'is-chart-fullscreen': isFullscreen }">
    <ChartWorkspaceHeader
      v-if="!isFullscreen"
      :current-ticker="currentTicker"
      :current-name="currentName"
      :quote="quote"
      :display-price="displayPrice"
      :display-change="displayChange"
      :quote-freshness-state="quoteFreshnessState"
      :quote-freshness-hint="quoteFreshnessHint"
      :show-macro-regime-banner="showMacroRegimeBanner"
      :macro-regime-class="macroRegimeClass"
      :macro-risk-label="macroRiskLabel"
      :macro-posture-label="macroPostureLabel"
      :macro-decision-hint="macroDecisionHint"
    />

    <ChartToolbar
      :active-tool="activeTool"
      :can-go-back-history="canGoBackHistory"
      :can-go-forward-history="canGoForwardHistory"
      :can-pan-left="canPanLeft"
      :can-pan-right="canPanRight"
      :can-zoom-in="canZoomIn"
      :can-zoom-out="canZoomOut"
      :can-reset-y-scale="canResetYScale"
      :price-scale-mode="priceScaleMode"
      :can-use-log-scale="canUseLogScale"
      :timeframe-options="timeframeOptions"
      :current-period="currentPeriod"
      :current-interval="currentInterval"
      :chart-mode="chartMode"
      :engine-mode="engineMode"
      :kline-display-mode="klineDisplayMode"
      :is-fullscreen="isFullscreen"
      :chart-layout="chartLayout"
      :syncing-current="syncingCurrent"
      :current-ticker="currentTicker"
      :quote="quote"
      @set-tool="emit('set-tool', $event)"
      @add-signal="emit('add-signal', $event)"
      @remove-last-drawing="emit('remove-last-drawing')"
      @clear-drawings="emit('clear-drawings')"
      @go-history-back="goHistoryBack"
      @go-history-forward="goHistoryForward"
      @pan-left="panLeft"
      @pan-right="panRight"
      @zoom-in="zoomIn"
      @zoom-out="zoomOut"
      @jump-to-latest="jumpToLatest"
      @reset-view="resetView"
      @set-timeframe="emit('set-timeframe', $event)"
      @zoom-y-in="zoomYIn"
      @zoom-y-out="zoomYOut"
      @reset-y-scale="resetYScale"
      @set-price-scale-mode="setPriceScaleMode"
      @set-chart-mode="setChartMode"
      @set-engine-mode="emit('set-engine-mode', $event)"
      @set-kline-display-mode="emit('set-kline-display-mode', $event)"
      @clear-indicators="handleClearIndicators"
      @toggle-fullscreen="emit('toggle-fullscreen')"
      @set-chart-layout="emit('set-chart-layout', $event)"
      @sync-current="emit('sync-current')"
      @open-journal-entry="emit('open-journal-entry', $event)"
    />

    <ChartWorkspaceMetaBar
      v-if="!isFullscreen"
      :visible-range-label="visibleRangeLabel"
      :visible-bars-label="visibleBarsLabel"
      :visible-change-label="visibleChangeLabel"
      :visible-change-class="visibleChangeClass"
      :zoom-label="zoomLabel"
      :y-scale-label="yScaleLabel"
      :price-scale-mode-label="priceScaleModeLabel"
      :quote-timestamp-label="quoteTimestampLabel"
      :quote-source-label="quoteSourceLabel"
      :quote-delay-label="quoteDelayLabel"
      :quote-freshness-label="quoteFreshnessLabel"
      :quote-freshness-chip-class="quoteFreshnessChipClass"
      :institutional-overlay="institutionalOverlay"
      :interaction-hint="interactionHint"
      :quote="quote"
    />

    <ChartWorkspaceControls
      v-if="!isFullscreen"
      v-model:workspace-preset-name="workspacePresetName"
      v-model:workspace-selection="workspaceSelection"
      v-model:compare-input="compareInput"
      :workspace-presets="workspacePresets"
      :comparison-mode="comparisonMode"
      :compare-series="compareSeries"
      :show-compare-panel="showComparePanel"
      @save-workspace="saveWorkspace"
      @load-workspace="loadWorkspace"
      @delete-workspace="deleteWorkspace"
      @submit-compare="submitCompare"
      @set-compare-mode="emit('set-compare-mode', $event)"
      @clear-compare="emit('clear-compare')"
      @remove-compare="emit('remove-compare', $event)"
    />

    <DrawingManager
      v-if="!isFullscreen"
      :drawings="drawings"
      :selected-drawing-id="selectedDrawingId"
      :selected-drawing="selectedDrawing"
      :supports-line-width="supportsLineWidth"
      :supports-line-style="supportsLineStyle"
      :supports-fill-opacity="supportsFillOpacity"
      :supports-text="supportsText"
      :drawing-type-label="drawingTypeLabel"
      :drawing-label="drawingLabel"
      @select-drawing="emit('select-drawing', $event)"
      @toggle-drawing-visibility="emit('toggle-drawing-visibility', $event)"
      @toggle-drawing-lock="emit('toggle-drawing-lock', $event)"
      @remove-drawing="emit('remove-drawing', $event)"
      @update-selected-drawing="updateSelectedDrawing"
      @remove-selected-drawing="removeSelectedDrawing"
    />

    <ChartCanvasArea
      v-if="!isLwcMode"
      :loading="loading"
      :loading-message="loadingMessage"
      :crosshair="crosshair"
      :visible-event-markers="visibleEventMarkers"
      :focused-event-key="focusedEventKey"
      :canvas-class="canvasClass"
      :chart-area-target="chartAreaTarget"
      :main-canvas-target="mainCanvasTarget"
      :on-mouse-down="onMouseDown"
      :on-mouse-move="onMouseMove"
      :on-mouse-leave="onMouseLeave"
      :on-mouse-up="onMouseUp"
      :on-wheel="onWheel"
      :on-chart-click="onChartClick"
      :on-double-click="onDoubleClick"
      :jump-to-event="jumpToEvent"
    />

    <LWCChartCanvas
      v-else
      :loading="loading"
      :loading-message="loadingMessage"
      :crosshair="crosshair"
      :visible-event-markers="visibleEventMarkers"
      :focused-event-key="focusedEventKey"
      :chart-container-target="chartContainerTarget"
      :jump-to-event="jumpToEvent"
    />

    <ChartSyncPaneGrid
      v-if="!isLwcMode && !isFullscreen"
      :layout-panes="layoutPanes"
      :current-ticker="currentTicker"
      :set-sync-pane-ref="setSyncPaneRef"
    />

    <ChartIndicatorPanel
      v-if="!isLwcMode && showComparePanel && !isFullscreen"
      :visible="true"
      :label="`COMPARE (${comparisonMode === 'percent' ? '%' : 'PRICE'})`"
      :canvas-target="compareCanvasTarget"
      panel-class="visible compare-panel"
    />

    <div v-if="!isLwcMode && showVolumePanel && !isFullscreen" class="volume-area"><canvas ref="volumeCanvas"></canvas></div>

    <ChartIndicatorPanel
      v-if="!isLwcMode && !isFullscreen"
      v-for="panel in indicatorPanels"
      :key="panel.key"
      :visible="panel.visible"
      :label="panel.label"
      :canvas-target="panel.canvasTarget"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { normalizeTicker } from "../composables/useDashboard";
import { useChartEngine } from "../composables/useChartEngine";
import { useLWCChart } from "../composables/useLWCChart";
import { useChartSyncPanes } from "../composables/useChartSyncPanes";
import { fmtPrice } from "../utils/formatters";
import ChartCanvasArea from "./chart/ChartCanvasArea.vue";
import DrawingManager from "./chart/DrawingManager.vue";
import ChartIndicatorPanel from "./chart/ChartIndicatorPanel.vue";
import ChartSyncPaneGrid from "./chart/ChartSyncPaneGrid.vue";
import LWCChartCanvas from "./chart/LWCChartCanvas.vue";
import ChartWorkspaceControls from "./chart/ChartWorkspaceControls.vue";
import ChartWorkspaceHeader from "./chart/ChartWorkspaceHeader.vue";
import ChartWorkspaceMetaBar from "./chart/ChartWorkspaceMetaBar.vue";
import ChartToolbar from "./chart/ChartToolbar.vue";

const props = defineProps({
  currentTicker: { type: String, required: true },
  currentName: { type: String, required: true },
  timeframeOptions: { type: Array, default: () => [] },
  currentPeriod: { type: String, default: "1y" },
  currentInterval: { type: String, default: "1d" },
  quote: { type: Object, required: true },
  activeTool: { type: String, required: true },
  activePanels: { type: Object, required: true },
  klineDisplayMode: { type: String, default: "day" },
  engineMode: { type: String, default: "legacy" },
  cleanChartMode: { type: Boolean, default: false },
  chartLayout: { type: String, default: "single" },
  loading: { type: Boolean, required: true },
  loadingMessage: { type: String, required: true },
  crosshair: { type: Object, required: true },
  ohlcData: { type: Array, required: true },
  activeInd: { type: Object, required: true },
  indicatorSettings: { type: Object, required: true },
  drawings: { type: Array, required: true },
  selectedDrawingId: { type: String, default: null },
  workspacePresets: { type: Array, default: () => [] },
  activeWorkspacePresetId: { type: [String, Number], default: null },
  syncingCurrent: { type: Boolean, required: true },
  compareSeries: { type: Array, default: () => [] },
  comparisonMode: { type: String, default: "percent" },
  institutionalOverlay: { type: Object, default: null },
  tickerEvents: { type: Array, default: () => [] },
  macroSummary: { type: Object, default: null },
  isFullscreen: { type: Boolean, default: false },
});

const emit = defineEmits([
  "set-tool",
  "add-signal",
  "clear-drawings",
  "remove-last-drawing",
  "sync-current",
  "add-horizontal-line",
  "add-drawing",
  "select-drawing",
  "remove-drawing",
  "update-drawing",
  "toggle-drawing-visibility",
  "toggle-drawing-lock",
  "save-workspace",
  "load-workspace",
  "delete-workspace",
  "set-timeframe",
  "update-crosshair",
  "hide-crosshair",
  "add-compare",
  "remove-compare",
  "clear-compare",
  "set-compare-mode",
  "set-kline-display-mode",
  "set-engine-mode",
  "set-chart-layout",
  "clear-indicators",
  "toggle-fullscreen",
  "open-journal-entry",
]);

const chartAreaRef = ref(null);
const chartContainerRef = ref(null);
const mainCanvas = ref(null);
const volumeCanvas = ref(null);
const compareCanvas = ref(null);
const rsiCanvas = ref(null);
const aroonCanvas = ref(null);
const trixCanvas = ref(null);
const williamsrCanvas = ref(null);
const mfiCanvas = ref(null);
const rocCanvas = ref(null);
const bbPercentCanvas = ref(null);
const bbWidthCanvas = ref(null);
const macdCanvas = ref(null);
const stochCanvas = ref(null);
const atrCanvas = ref(null);
const cciCanvas = ref(null);
const obvCanvas = ref(null);
const adxCanvas = ref(null);
const cmfCanvas = ref(null);
const compareInput = ref("");
const workspacePresetName = ref("");
const workspaceSelection = ref(props.activeWorkspacePresetId || "");
const focusedEventKey = ref("");
const chartAreaTarget = { target: chartAreaRef };
const chartContainerTarget = { target: chartContainerRef };
const mainCanvasTarget = { target: mainCanvas };
const compareCanvasTarget = { target: compareCanvas };
const rsiCanvasTarget = { target: rsiCanvas };
const aroonCanvasTarget = { target: aroonCanvas };
const trixCanvasTarget = { target: trixCanvas };
const williamsrCanvasTarget = { target: williamsrCanvas };
const mfiCanvasTarget = { target: mfiCanvas };
const rocCanvasTarget = { target: rocCanvas };
const bbPercentCanvasTarget = { target: bbPercentCanvas };
const bbWidthCanvasTarget = { target: bbWidthCanvas };
const macdCanvasTarget = { target: macdCanvas };
const stochCanvasTarget = { target: stochCanvas };
const atrCanvasTarget = { target: atrCanvas };
const cciCanvasTarget = { target: cciCanvas };
const obvCanvasTarget = { target: obvCanvas };
const adxCanvasTarget = { target: adxCanvas };
const cmfCanvasTarget = { target: cmfCanvas };

const legacyChart = useChartEngine({
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
});

const lwcChart = useLWCChart({
  chartContainer: chartContainerRef,
  props,
  emit,
});

const isLwcMode = computed(() => props.engineMode === "lwc");
const activeChartController = computed(() => (isLwcMode.value ? lwcChart : legacyChart));

const chartMode = computed(() => activeChartController.value.chartMode.value);
const priceScaleMode = computed(() => activeChartController.value.priceScaleMode.value);
const visibleData = computed(() => activeChartController.value.visibleData.value);
const viewportStartIndex = computed(() => activeChartController.value.viewportStartIndex.value);
const canvasClass = computed(() => activeChartController.value.canvasClass.value);
const visibleRangeLabel = computed(() => activeChartController.value.visibleRangeLabel.value);
const visibleBarsLabel = computed(() => activeChartController.value.visibleBarsLabel.value);
const visibleChangeLabel = computed(() => activeChartController.value.visibleChangeLabel.value);
const visibleChangeClass = computed(() => activeChartController.value.visibleChangeClass.value);
const zoomLabel = computed(() => activeChartController.value.zoomLabel.value);
const yScaleLabel = computed(() => activeChartController.value.yScaleLabel.value);
const priceScaleModeLabel = computed(() => activeChartController.value.priceScaleModeLabel.value);
const interactionHint = computed(() => activeChartController.value.interactionHint.value);
const canPanLeft = computed(() => activeChartController.value.canPanLeft.value);
const canPanRight = computed(() => activeChartController.value.canPanRight.value);
const canZoomIn = computed(() => activeChartController.value.canZoomIn.value);
const canZoomOut = computed(() => activeChartController.value.canZoomOut.value);
const canUseLogScale = computed(() => activeChartController.value.canUseLogScale.value);
const canGoBackHistory = computed(() => activeChartController.value.canGoBackHistory.value);
const canGoForwardHistory = computed(() => activeChartController.value.canGoForwardHistory.value);
const canResetYScale = computed(() => activeChartController.value.canResetYScale.value);

function setChartMode(mode) {
  activeChartController.value.setChartMode(mode);
}

function setPriceScaleMode(mode) {
  activeChartController.value.setPriceScaleMode(mode);
}

function zoomIn() {
  activeChartController.value.zoomIn();
}

function zoomOut() {
  activeChartController.value.zoomOut();
}

function zoomYIn() {
  activeChartController.value.zoomYIn();
}

function zoomYOut() {
  activeChartController.value.zoomYOut();
}

function panLeft() {
  activeChartController.value.panLeft();
}

function panRight() {
  activeChartController.value.panRight();
}

function goHistoryBack() {
  activeChartController.value.goHistoryBack();
}

function goHistoryForward() {
  activeChartController.value.goHistoryForward();
}

function jumpToLatest() {
  activeChartController.value.jumpToLatest();
}

function resetView() {
  activeChartController.value.resetView();
}

function resetYScale() {
  activeChartController.value.resetYScale();
}

function onMouseDown(event) {
  activeChartController.value.onMouseDown(event);
}

function onMouseMove(event) {
  activeChartController.value.onMouseMove(event);
}

function onMouseLeave(event) {
  activeChartController.value.onMouseLeave(event);
}

function onMouseUp(event) {
  activeChartController.value.onMouseUp(event);
}

function onWheel(event) {
  activeChartController.value.onWheel(event);
}

function onChartClick(event) {
  activeChartController.value.onChartClick(event);
}

function onDoubleClick(event) {
  activeChartController.value.onDoubleClick(event);
}

const displayPrice = computed(() =>
  props.quote.price == null ? "—" : `$${fmtPrice(props.quote.price)}`,
);

const displayChange = computed(() => {
  if (props.quote.price == null) return "—";
  const sign = props.quote.change_pct >= 0 ? "+" : "";
  return `${sign}${(props.quote.change || 0).toFixed(2)} (${sign}${(props.quote.change_pct || 0).toFixed(2)}%)`;
});

const quoteTimestampLabel = computed(() => {
  if (!props.quote.quote_timestamp && !props.quote.synced_at) return "資料時間：—";
  const value = props.quote.quote_timestamp || props.quote.synced_at;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return `資料時間：${value}`;
  return `資料時間：${date.toLocaleString("zh-TW", { hour12: false })}`;
});

const quoteSourceLabel = computed(() => `來源：${props.quote.source || "local_cache"}`);
const quoteDelayLabel = computed(() => (props.quote.is_delayed ? "延遲快照" : "最新快照"));
const quoteFreshnessState = computed(() => {
  const rawValue = props.quote.quote_timestamp || props.quote.synced_at;
  if (!rawValue) return "missing";
  const parsed = new Date(rawValue);
  if (Number.isNaN(parsed.getTime())) return "missing";
  const ageMs = Date.now() - parsed.getTime();
  if (ageMs > 24 * 60 * 60 * 1000) return "stale";
  return props.quote.is_delayed ? "delayed" : "live";
});
const quoteFreshnessLabel = computed(() => {
  if (quoteFreshnessState.value === "missing") return "無時間戳";
  if (quoteFreshnessState.value === "stale") return "資料較舊";
  return quoteFreshnessState.value === "live" ? "資料已更新" : "盤中延遲資料";
});
const quoteFreshnessHint = computed(() => {
  if (quoteFreshnessState.value === "missing") return "目前報價缺少時間戳，請先確認資料來源";
  if (quoteFreshnessState.value === "stale") return "目前顯示資料已超過 24 小時，建議先同步再下判斷";
  return "盤中請留意本畫面為延遲快照，不適合超短線下單判斷";
});
const quoteFreshnessChipClass = computed(() => ({
  up: quoteFreshnessState.value === "live",
  dn: quoteFreshnessState.value === "stale" || quoteFreshnessState.value === "missing",
  warn: quoteFreshnessState.value === "delayed",
}));
const showMacroRegimeBanner = computed(() => Boolean(
  props.macroSummary?.trade_posture
  || props.macroSummary?.overall_risk
  || props.macroSummary?.decision_hint,
));
const macroRegimeClass = computed(() => `is-${props.macroSummary?.trade_posture || "standby"}`);
const macroRiskLabel = computed(() => {
  if (props.macroSummary?.overall_risk === "high") return "高風險";
  if (props.macroSummary?.overall_risk === "medium") return "中風險";
  if (props.macroSummary?.overall_risk === "low") return "低風險";
  return "未同步";
});
const macroPostureLabel = computed(() => {
  if (props.macroSummary?.trade_posture === "defensive") return "防守控倉";
  if (props.macroSummary?.trade_posture === "selective") return "選擇性出手";
  if (props.macroSummary?.trade_posture === "offensive") return "偏進攻";
  if (props.macroSummary?.trade_posture === "balanced") return "平衡觀察";
  return "暫停判斷";
});
const macroDecisionHint = computed(
  () => props.macroSummary?.decision_hint || "尚未同步宏觀快照，先以個股與價格行為為主。",
);
const visibleEventMarkers = computed(() => {
  const rows = visibleData.value || [];
  if (!rows.length || !(props.tickerEvents || []).length) return [];
  const lastIndex = Math.max(rows.length - 1, 1);
  return (props.tickerEvents || [])
    .map((item) => {
      const absoluteIndex = findEventAbsoluteIndex(item.event_date);
      if (absoluteIndex < viewportStartIndex.value || absoluteIndex >= viewportStartIndex.value + rows.length) {
        return null;
      }
      const localIndex = absoluteIndex - viewportStartIndex.value;
      return {
        ...item,
        key: `${item.event_type}-${item.event_date}-${item.title}`,
        absoluteIndex,
        left: `${(localIndex / lastIndex) * 100}%`,
      };
    })
    .filter(Boolean);
});

const rsiLabel = computed(() => `RSI(${props.indicatorSettings.rsiPeriod})`);
const aroonLabel = computed(() => `Aroon(${props.indicatorSettings.aroonPeriod})`);
const trixLabel = computed(() => `TRIX(${props.indicatorSettings.trixPeriod},${props.indicatorSettings.trixSignal})`);
const williamsrLabel = computed(() => `Williams %R(${props.indicatorSettings.williamsrPeriod})`);
const mfiLabel = computed(() => `MFI(${props.indicatorSettings.mfiPeriod})`);
const rocLabel = computed(() => `ROC(${props.indicatorSettings.rocPeriod})`);
const bbPercentLabel = computed(() => `Bollinger %B(${props.indicatorSettings.bbPeriod})`);
const bbWidthLabel = computed(() => `Bollinger Width(${props.indicatorSettings.bbPeriod})`);
const macdLabel = computed(
  () => `MACD(${props.indicatorSettings.macdFast},${props.indicatorSettings.macdSlow},${props.indicatorSettings.macdSignal})`,
);
const stochLabel = computed(
  () => `KD Stoch(${props.indicatorSettings.stochK},${props.indicatorSettings.stochD})`,
);
const showVolumePanel = computed(() => !props.cleanChartMode);
const showMacdPanel = computed(() => (
  props.cleanChartMode ? false : (props.isFullscreen ? props.activePanels.macd : true)
));
const showStochPanel = computed(() => (
  props.cleanChartMode ? false : (props.isFullscreen ? props.activePanels.stoch : true)
));
const atrLabel = computed(() => `ATR(${props.indicatorSettings.atrPeriod})`);
const cciLabel = computed(() => `CCI(${props.indicatorSettings.cciPeriod})`);
const adxLabel = computed(() => `ADX(${props.indicatorSettings.adxPeriod})`);
const cmfLabel = computed(() => `CMF(${props.indicatorSettings.cmfPeriod})`);
const selectedDrawing = computed(
  () => props.drawings.find((drawing) => drawing.id === props.selectedDrawingId) || null,
);
const supportsLineWidth = computed(() =>
  ["hline", "vline", "trendline", "arrow", "fib", "rect", "measure"].includes(selectedDrawing.value?.type),
);
const supportsLineStyle = computed(() =>
  ["hline", "vline", "trendline", "arrow", "fib", "rect", "measure"].includes(selectedDrawing.value?.type),
);
const supportsFillOpacity = computed(() =>
  ["rect", "note"].includes(selectedDrawing.value?.type),
);
const supportsText = computed(() => selectedDrawing.value?.type === "note");
const showComparePanel = computed(() => !isLwcMode.value && props.compareSeries.length > 0 && !props.cleanChartMode);
const layoutPanes = computed(() => {
  if (props.chartLayout === "double") {
    return [{ key: "sync-line", title: "同步折線", mode: "line" }];
  }
  if (props.chartLayout === "quad") {
    return [
      { key: "sync-line", title: "同步折線", mode: "line" },
      { key: "sync-area", title: "同步面積", mode: "area" },
      { key: "sync-candle", title: "同步 K 線", mode: "candles" },
    ];
  }
  return [];
});
const indicatorPanels = computed(() => ([
  { key: "rsi", visible: props.activePanels.rsi, label: rsiLabel.value, canvasTarget: rsiCanvasTarget },
  { key: "aroon", visible: props.activePanels.aroon, label: aroonLabel.value, canvasTarget: aroonCanvasTarget },
  { key: "trix", visible: props.activePanels.trix, label: trixLabel.value, canvasTarget: trixCanvasTarget },
  { key: "williamsr", visible: props.activePanels.williamsr, label: williamsrLabel.value, canvasTarget: williamsrCanvasTarget },
  { key: "mfi", visible: props.activePanels.mfi, label: mfiLabel.value, canvasTarget: mfiCanvasTarget },
  { key: "roc", visible: props.activePanels.roc, label: rocLabel.value, canvasTarget: rocCanvasTarget },
  { key: "bbPercent", visible: props.activePanels.bbPercent, label: bbPercentLabel.value, canvasTarget: bbPercentCanvasTarget },
  { key: "bbWidth", visible: props.activePanels.bbWidth, label: bbWidthLabel.value, canvasTarget: bbWidthCanvasTarget },
  { key: "macd", visible: showMacdPanel.value, label: macdLabel.value, canvasTarget: macdCanvasTarget },
  { key: "stoch", visible: showStochPanel.value, label: stochLabel.value, canvasTarget: stochCanvasTarget },
  { key: "atr", visible: props.activePanels.atr, label: atrLabel.value, canvasTarget: atrCanvasTarget },
  { key: "cci", visible: props.activePanels.cci, label: cciLabel.value, canvasTarget: cciCanvasTarget },
  { key: "obv", visible: props.activePanels.obv, label: "OBV", canvasTarget: obvCanvasTarget },
  { key: "adx", visible: props.activePanels.adx, label: adxLabel.value, canvasTarget: adxCanvasTarget },
  { key: "cmf", visible: props.activePanels.cmf, label: cmfLabel.value, canvasTarget: cmfCanvasTarget },
]));

const { setSyncPaneRef } = useChartSyncPanes({
  layoutPanes,
  visibleData,
  viewportStartIndex,
  crosshair: computed(() => props.crosshair),
});

function drawingTypeLabel(type) {
  const labels = {
    buy: "買點",
    sell: "賣點",
    hline: "水平線",
    vline: "垂直線",
    trendline: "趨勢線",
    arrow: "箭頭線",
    fib: "費波",
    rect: "區間",
    measure: "測距",
    note: "註記",
  };
  return labels[type] || type;
}

function drawingLabel(drawing) {
  if (!drawing) return "未命名";
  if (drawing.type === "hline") return `@ ${fmtPrice(drawing.price)}`;
  if (drawing.type === "vline") return `第 ${drawing.index + 1} 根`;
  if (drawing.type === "buy" || drawing.type === "sell") return `第 ${drawing.index + 1} 根訊號`;
  if (drawing.type === "trendline") return `${fmtPrice(drawing.startPrice)} → ${fmtPrice(drawing.endPrice)}`;
  if (drawing.type === "arrow") return `${fmtPrice(drawing.startPrice)} ⇢ ${fmtPrice(drawing.endPrice)}`;
  if (drawing.type === "fib") return `${fmtPrice(drawing.startPrice)} ↔ ${fmtPrice(drawing.endPrice)}`;
  if (drawing.type === "rect") return `${fmtPrice(Math.max(drawing.startPrice, drawing.endPrice))} / ${fmtPrice(Math.min(drawing.startPrice, drawing.endPrice))}`;
  if (drawing.type === "measure") return `${Math.abs(drawing.endIndex - drawing.startIndex) + 1} 根`;
  if (drawing.type === "note") return drawing.text || drawing.label || "註記";
  return drawing.type;
}

function findEventAbsoluteIndex(eventDate) {
  if (!eventDate || !Array.isArray(props.ohlcData) || !props.ohlcData.length) return -1;
  const target = String(eventDate).slice(0, 10);
  const exactIndex = props.ohlcData.findIndex((row) => String(row?.date || "").slice(0, 10) === target);
  if (exactIndex >= 0) return exactIndex;
  const fallbackIndex = props.ohlcData.findLastIndex((row) => String(row?.date || "").slice(0, 10) <= target);
  return fallbackIndex >= 0 ? fallbackIndex : -1;
}

function jumpToEvent(eventItem) {
  const eventKey = `${eventItem.event_type}-${eventItem.event_date}-${eventItem.title}`;
  focusedEventKey.value = eventKey;
  const absoluteIndex = findEventAbsoluteIndex(eventItem.event_date);
  if (absoluteIndex < 0) return;
  emit("add-drawing", {
    type: "vline",
    index: absoluteIndex,
    label: eventItem.title || eventItem.event_type || "event",
  });
}

function updateSelectedDrawing(patch) {
  if (!selectedDrawing.value) return;
  emit("update-drawing", selectedDrawing.value.id, patch);
}

function handleClearIndicators() {
  setChartMode("candles");
  emit("clear-indicators");
}

function submitCompare() {
  const ticker = normalizeTicker(compareInput.value);
  if (!ticker) return;
  compareInput.value = "";
  emit("add-compare", ticker);
}

function saveWorkspace() {
  if (!workspacePresetName.value) return;
  emit("save-workspace", workspacePresetName.value);
  workspacePresetName.value = "";
}

function loadWorkspace() {
  if (!workspaceSelection.value) return;
  emit("load-workspace", workspaceSelection.value);
}

function deleteWorkspace() {
  if (!workspaceSelection.value) return;
  emit("delete-workspace", workspaceSelection.value);
  workspaceSelection.value = "";
}

function removeSelectedDrawing() {
  if (!props.selectedDrawingId) return;
  emit("remove-drawing", props.selectedDrawingId);
}

function handleKeydown(event) {
  const target = event.target;
  if (
    target instanceof HTMLInputElement
    || target instanceof HTMLTextAreaElement
    || target instanceof HTMLSelectElement
    || target?.isContentEditable
  ) {
    return;
  }

  const key = event.key.toLowerCase();
  const toolMap = {
    v: "cursor",
    h: "hline",
    l: "vline",
    t: "tline",
    a: "arrow",
    f: "fib",
    r: "rect",
    m: "measure",
    n: "note",
    b: "boxzoom",
  };

  if (toolMap[key]) {
    event.preventDefault();
    emit("set-tool", toolMap[key]);
    return;
  }

  if ((event.key === "Delete" || event.key === "Backspace") && props.selectedDrawingId) {
    event.preventDefault();
    emit("remove-drawing", props.selectedDrawingId);
    return;
  }

  if (event.key === "Escape") {
    event.preventDefault();
    emit("set-tool", "cursor");
    emit("select-drawing", null);
  }
}

watch(
  () => props.activeWorkspacePresetId,
  (value) => {
    workspaceSelection.value = value || "";
  },
);

watch(
  () => props.engineMode,
  (nextMode, previousMode) => {
    const previousController = previousMode === "lwc" ? lwcChart : legacyChart;
    const nextController = nextMode === "lwc" ? lwcChart : legacyChart;
    nextController.setChartMode(previousController.chartMode.value);
    nextController.setPriceScaleMode(previousController.priceScaleMode.value);
    emit("hide-crosshair");
  },
);

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped>
.center {
  height: 100%;
}

.center.is-chart-fullscreen {
  overflow: hidden;
}

.center.is-chart-fullscreen :deep(.chart-area) {
  flex: 1 1 auto;
  min-height: 0;
}
</style>
