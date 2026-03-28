<template>
  <div class="center">
    <div class="chart-header">
      <div>
        <div style="display: flex; align-items: baseline; gap: 8px">
          <div class="ch-ticker">{{ currentTicker || "—" }}</div>
          <div style="font-size: 11px; color: var(--text3)">{{ currentName || "載入中..." }}</div>
        </div>
      </div>
      <div class="ch-price" :class="quote.change_pct >= 0 ? 'up' : 'dn'">{{ displayPrice }}</div>
      <div class="ch-chg" :class="quote.change_pct >= 0 ? 'up' : 'dn'">{{ displayChange }}</div>
      <div class="ch-stats">
        <div class="ch-stat"><span>開盤</span><span>{{ fmtPrice(quote.open) }}</span></div>
        <div class="ch-stat"><span>最高</span><span style="color: var(--green)">{{ fmtPrice(quote.high) }}</span></div>
        <div class="ch-stat"><span>最低</span><span style="color: var(--red)">{{ fmtPrice(quote.low) }}</span></div>
        <div class="ch-stat"><span>成交量</span><span>{{ fmtVol(quote.volume) }}</span></div>
        <div class="ch-stat"><span>市值</span><span>{{ fmtMktCap(quote.market_cap) }}</span></div>
      </div>
    </div>

    <div class="chart-toolbar">
      <span class="tool-label">繪圖：</span>
      <button class="tool-btn" :class="{ active: activeTool === 'cursor' }" @click="$emit('set-tool', 'cursor')">⊹ 游標</button>
      <button class="tool-btn" :class="{ active: activeTool === 'hline' }" @click="$emit('set-tool', 'hline')">─ 水平線</button>
      <button class="tool-btn" :class="{ active: activeTool === 'vline' }" @click="$emit('set-tool', 'vline')">│ 垂直線</button>
      <button class="tool-btn" :class="{ active: activeTool === 'tline' }" @click="$emit('set-tool', 'tline')">╱ 趨勢線</button>
      <button class="tool-btn" :class="{ active: activeTool === 'fib' }" @click="$emit('set-tool', 'fib')">⋮ 費波</button>
      <button class="tool-btn" :class="{ active: activeTool === 'rect' }" @click="$emit('set-tool', 'rect')">▭ 區間</button>
      <button class="tool-btn" :class="{ active: activeTool === 'measure' }" @click="$emit('set-tool', 'measure')">⊕ 測距</button>
      <button class="tool-btn" :class="{ active: activeTool === 'boxzoom' }" @click="$emit('set-tool', 'boxzoom')">□ 框選</button>

      <div class="tool-sep"></div>

      <span class="tool-label">標記：</span>
      <button class="tool-btn" @click="$emit('add-signal', 'buy')">▲ 買入</button>
      <button class="tool-btn" @click="$emit('add-signal', 'sell')">▼ 賣出</button>
      <button class="tool-btn" @click="$emit('remove-last-drawing')">↶ 復原</button>
      <button class="tool-btn" @click="$emit('clear-drawings')">✕ 清除</button>

      <div class="tool-sep"></div>

      <span class="tool-label">檢視：</span>
      <button class="tool-btn" :disabled="!canGoBackHistory" @click="goHistoryBack">↶ 返回</button>
      <button class="tool-btn" :disabled="!canGoForwardHistory" @click="goHistoryForward">↷ 前進</button>
      <button class="tool-btn" :disabled="!canPanLeft" @click="panLeft">← 左移</button>
      <button class="tool-btn" :disabled="!canPanRight" @click="panRight">→ 右移</button>
      <button class="tool-btn" :disabled="!canZoomIn" @click="zoomIn">＋ 放大</button>
      <button class="tool-btn" :disabled="!canZoomOut" @click="zoomOut">－ 縮小</button>
      <button class="tool-btn" @click="jumpToLatest">最新</button>
      <button class="tool-btn" @click="resetView">重置</button>

      <div class="tool-sep"></div>

      <span class="tool-label">Y 軸：</span>
      <button class="tool-btn" @click="zoomYIn">Y＋</button>
      <button class="tool-btn" @click="zoomYOut">Y－</button>
      <button class="tool-btn" :disabled="!canResetYScale" @click="resetYScale">Y 自動</button>
      <button class="tool-btn" :class="{ active: priceScaleMode === 'linear' }" @click="setPriceScaleMode('linear')">線性</button>
      <button class="tool-btn" :class="{ active: priceScaleMode === 'log' }" :disabled="!canUseLogScale" @click="setPriceScaleMode('log')">對數</button>

      <div class="tool-sep"></div>

      <span class="tool-label">圖型：</span>
      <button class="tool-btn" :class="{ active: chartMode === 'candles' }" @click="setChartMode('candles')">K 線</button>
      <button class="tool-btn" :class="{ active: chartMode === 'line' }" @click="setChartMode('line')">折線</button>
      <button class="tool-btn" :class="{ active: chartMode === 'area' }" @click="setChartMode('area')">面積</button>

      <div class="tool-sep"></div>

      <button class="tool-btn" :disabled="syncingCurrent" @click="$emit('sync-current')">
        {{ syncingCurrent ? "↻ 同步中..." : "↻ 同步" }}
      </button>
    </div>

    <div class="chart-meta">
      <div class="meta-chip">{{ visibleRangeLabel }}</div>
      <div class="meta-chip">{{ visibleBarsLabel }}</div>
      <div class="meta-chip" :class="visibleChangeClass">{{ visibleChangeLabel }}</div>
      <div class="meta-chip">{{ zoomLabel }}</div>
      <div class="meta-chip">{{ yScaleLabel }}</div>
      <div class="meta-chip">{{ priceScaleModeLabel }}</div>
      <div class="meta-chip is-hint">{{ interactionHint }}</div>
    </div>

    <div class="workspace-toolbar">
      <span class="tool-label">工作區：</span>
      <input
        v-model.trim="workspacePresetName"
        class="compare-input workspace-input"
        type="text"
        placeholder="輸入名稱後儲存目前分析版面"
        @keydown.enter.prevent="saveWorkspace"
      />
      <button class="tool-btn" @click="saveWorkspace">儲存</button>
      <select v-model="workspaceSelection" class="workspace-select">
        <option value="">選擇已儲存工作區</option>
        <option
          v-for="preset in workspacePresets"
          :key="preset.id"
          :value="preset.id"
        >
          {{ preset.name }}
        </option>
      </select>
      <button class="tool-btn" :disabled="!workspaceSelection" @click="loadWorkspace">載入</button>
      <button class="tool-btn" :disabled="!workspaceSelection" @click="deleteWorkspace">刪除</button>
    </div>

    <div class="compare-toolbar">
      <span class="tool-label">比較：</span>
      <input
        v-model.trim="compareInput"
        class="compare-input"
        type="text"
        placeholder="輸入代號加入比較，例如 MSFT / 0050"
        @keydown.enter.prevent="submitCompare"
      />
      <button class="tool-btn" @click="submitCompare">加入比較</button>
      <button class="tool-btn" :class="{ active: comparisonMode === 'percent' }" @click="$emit('set-compare-mode', 'percent')">相對報酬</button>
      <button class="tool-btn" :class="{ active: comparisonMode === 'price' }" @click="$emit('set-compare-mode', 'price')">絕對價格</button>
      <button class="tool-btn" :disabled="!compareSeries.length" @click="$emit('clear-compare')">清空比較</button>
    </div>

    <div v-if="compareSeries.length" class="compare-legend">
      <button
        v-for="series in compareSeries"
        :key="series.ticker"
        class="compare-chip"
        :style="{ '--compare-color': series.color }"
        @click="$emit('remove-compare', series.ticker)"
      >
        <span class="compare-chip-line"></span>
        <span>{{ series.ticker }}</span>
        <span :class="series.changePct >= 0 ? 'up' : 'dn'">
          {{ series.changePct >= 0 ? "+" : "" }}{{ Number(series.changePct || 0).toFixed(2) }}%
        </span>
        <span class="compare-chip-close">✕</span>
      </button>
    </div>

    <div v-if="drawings.length" class="drawing-manager">
      <div class="drawing-manager-head">
        <div class="drawing-manager-title">物件樹</div>
        <div class="drawing-manager-actions">
          <span class="drawing-shortcuts">快捷鍵：V 游標 / H 水平 / L 垂直 / T 趨勢 / F 費波 / R 區間 / M 測距 / B 框選 / Del 刪除 / Esc 取消</span>
          <button class="tool-btn compact" :disabled="!selectedDrawingId" @click="removeSelectedDrawing">刪除所選</button>
        </div>
      </div>
      <div class="drawing-list">
        <button
          v-for="drawing in drawings"
          :key="drawing.id || drawingLabel(drawing)"
          class="drawing-chip"
          :class="{ active: drawing.id === selectedDrawingId }"
          @click="$emit('select-drawing', drawing.id)"
        >
          <span class="drawing-chip-type">{{ drawingTypeLabel(drawing.type) }}</span>
          <span class="drawing-chip-label">{{ drawingLabel(drawing) }}</span>
          <span class="drawing-chip-close" @click.stop="$emit('remove-drawing', drawing.id)">✕</span>
        </button>
      </div>
    </div>

    <div ref="chartAreaRef" class="chart-area">
      <canvas
        ref="mainCanvas"
        id="mainChart"
        :class="canvasClass"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseleave="onMouseLeave"
        @mouseup="onMouseUp"
        @wheel.prevent="onWheel"
        @click="onChartClick"
        @dblclick="onDoubleClick"
      ></canvas>

      <div v-show="loading" class="chart-loading">
        <div class="spinner"></div>
        <p>{{ loadingMessage }}</p>
      </div>

      <div v-show="crosshair.visible" class="crosshair-box is-open">
        <div class="ci-row"><span class="ci-label">日期</span><span>{{ crosshair.date }}</span></div>
        <div class="ci-row"><span class="ci-label">開盤</span><span>{{ crosshair.open }}</span></div>
        <div class="ci-row"><span class="ci-label">最高</span><span>{{ crosshair.high }}</span></div>
        <div class="ci-row"><span class="ci-label">最低</span><span>{{ crosshair.low }}</span></div>
        <div class="ci-row"><span class="ci-label">收盤</span><span>{{ crosshair.close }}</span></div>
        <div class="ci-row"><span class="ci-label">成交量</span><span>{{ crosshair.volume }}</span></div>
      </div>
    </div>

    <div v-if="compareSeries.length" class="ind-panel visible compare-panel">
      <div class="ind-label-tag">COMPARE ({{ comparisonMode === "percent" ? "%" : "PRICE" }})</div>
      <canvas ref="compareCanvas"></canvas>
    </div>
    <div class="volume-area"><canvas ref="volumeCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.rsi }"><div class="ind-label-tag">RSI(14)</div><canvas ref="rsiCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.macd }"><div class="ind-label-tag">MACD(12,26,9)</div><canvas ref="macdCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.stoch }"><div class="ind-label-tag">KD Stoch(14,3)</div><canvas ref="stochCanvas"></canvas></div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { normalizeTicker } from "../composables/useDashboard";
import { useChartEngine } from "../composables/useChartEngine";
import { fmtMktCap, fmtPrice, fmtVol } from "../utils/formatters";

const props = defineProps({
  currentTicker: { type: String, required: true },
  currentName: { type: String, required: true },
  quote: { type: Object, required: true },
  activeTool: { type: String, required: true },
  activePanels: { type: Object, required: true },
  loading: { type: Boolean, required: true },
  loadingMessage: { type: String, required: true },
  crosshair: { type: Object, required: true },
  ohlcData: { type: Array, required: true },
  activeInd: { type: Object, required: true },
  drawings: { type: Array, required: true },
  selectedDrawingId: { type: String, default: null },
  workspacePresets: { type: Array, default: () => [] },
  activeWorkspacePresetId: { type: String, default: null },
  syncingCurrent: { type: Boolean, required: true },
  compareSeries: { type: Array, default: () => [] },
  comparisonMode: { type: String, default: "percent" },
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
  "save-workspace",
  "load-workspace",
  "delete-workspace",
  "update-crosshair",
  "hide-crosshair",
  "add-compare",
  "remove-compare",
  "clear-compare",
  "set-compare-mode",
]);

const chartAreaRef = ref(null);
const mainCanvas = ref(null);
const volumeCanvas = ref(null);
const compareCanvas = ref(null);
const rsiCanvas = ref(null);
const macdCanvas = ref(null);
const stochCanvas = ref(null);
const compareInput = ref("");
const workspacePresetName = ref("");
const workspaceSelection = ref(props.activeWorkspacePresetId || "");

const {
  chartMode,
  priceScaleMode,
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
} = useChartEngine({
  mainCanvas,
  volumeCanvas,
  compareCanvas,
  rsiCanvas,
  macdCanvas,
  stochCanvas,
  chartAreaRef,
  props,
  emit,
});

const displayPrice = computed(() =>
  props.quote.price == null ? "—" : `$${fmtPrice(props.quote.price)}`,
);

const displayChange = computed(() => {
  if (props.quote.price == null) return "—";
  const sign = props.quote.change_pct >= 0 ? "+" : "";
  return `${sign}${(props.quote.change || 0).toFixed(2)} (${sign}${(props.quote.change_pct || 0).toFixed(2)}%)`;
});

function drawingTypeLabel(type) {
  const labels = {
    buy: "買點",
    sell: "賣點",
    hline: "水平線",
    vline: "垂直線",
    trendline: "趨勢線",
    fib: "費波",
    rect: "區間",
    measure: "測距",
  };
  return labels[type] || type;
}

function drawingLabel(drawing) {
  if (!drawing) return "未命名";
  if (drawing.type === "hline") return `@ ${fmtPrice(drawing.price)}`;
  if (drawing.type === "vline") return `第 ${drawing.index + 1} 根`;
  if (drawing.type === "buy" || drawing.type === "sell") return `第 ${drawing.index + 1} 根訊號`;
  if (drawing.type === "trendline") return `${fmtPrice(drawing.startPrice)} → ${fmtPrice(drawing.endPrice)}`;
  if (drawing.type === "fib") return `${fmtPrice(drawing.startPrice)} ↔ ${fmtPrice(drawing.endPrice)}`;
  if (drawing.type === "rect") return `${fmtPrice(Math.max(drawing.startPrice, drawing.endPrice))} / ${fmtPrice(Math.min(drawing.startPrice, drawing.endPrice))}`;
  if (drawing.type === "measure") return `${Math.abs(drawing.endIndex - drawing.startIndex) + 1} 根`;
  return drawing.type;
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
    f: "fib",
    r: "rect",
    m: "measure",
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

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
});
</script>
