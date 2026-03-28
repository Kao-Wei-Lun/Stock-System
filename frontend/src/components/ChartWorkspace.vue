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
      <button class="tool-btn" :class="{ active: activeTool === 'tline' }" @click="$emit('set-tool', 'tline')">╱ 趨勢線</button>
      <button class="tool-btn" :class="{ active: activeTool === 'fib' }" @click="$emit('set-tool', 'fib')">⋮ 費波</button>
      <button class="tool-btn" :class="{ active: activeTool === 'boxzoom' }" @click="$emit('set-tool', 'boxzoom')">□ 框選</button>

      <div class="tool-sep"></div>

      <span class="tool-label">標記：</span>
      <button class="tool-btn" @click="$emit('add-signal', 'buy')">▲ 買入</button>
      <button class="tool-btn" @click="$emit('add-signal', 'sell')">▼ 賣出</button>
      <button class="tool-btn" @click="$emit('remove-last-drawing')">↶ 復原</button>
      <button class="tool-btn" @click="$emit('clear-drawings')">✕ 清除</button>

      <div class="tool-sep"></div>

      <span class="tool-label">檢視：</span>
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
      <div class="meta-chip is-hint">{{ interactionHint }}</div>
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

    <div class="volume-area"><canvas ref="volumeCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.rsi }"><div class="ind-label-tag">RSI(14)</div><canvas ref="rsiCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.macd }"><div class="ind-label-tag">MACD(12,26,9)</div><canvas ref="macdCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.stoch }"><div class="ind-label-tag">KD Stoch(14,3)</div><canvas ref="stochCanvas"></canvas></div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

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
  syncingCurrent: { type: Boolean, required: true },
});

const emit = defineEmits([
  "set-tool",
  "add-signal",
  "clear-drawings",
  "remove-last-drawing",
  "sync-current",
  "add-horizontal-line",
  "add-drawing",
  "update-crosshair",
  "hide-crosshair",
]);

const chartAreaRef = ref(null);
const mainCanvas = ref(null);
const volumeCanvas = ref(null);
const rsiCanvas = ref(null);
const macdCanvas = ref(null);
const stochCanvas = ref(null);

const {
  chartMode,
  canvasClass,
  visibleRangeLabel,
  visibleBarsLabel,
  visibleChangeLabel,
  visibleChangeClass,
  zoomLabel,
  yScaleLabel,
  interactionHint,
  canPanLeft,
  canPanRight,
  canZoomIn,
  canZoomOut,
  canResetYScale,
  setChartMode,
  zoomIn,
  zoomOut,
  zoomYIn,
  zoomYOut,
  panLeft,
  panRight,
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
</script>
