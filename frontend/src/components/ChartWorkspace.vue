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
      <span style="font-size: 10px; color: var(--text3)">繪圖：</span>
      <button class="tool-btn" :class="{ active: activeTool === 'cursor' }" @click="$emit('set-tool', 'cursor')">⊹ 游標</button>
      <button class="tool-btn" :class="{ active: activeTool === 'hline' }" @click="$emit('set-tool', 'hline')">─ 水平線</button>
      <button class="tool-btn" :class="{ active: activeTool === 'tline' }" @click="$emit('set-tool', 'tline')">╱ 趨勢線</button>
      <button class="tool-btn" :class="{ active: activeTool === 'fib' }" @click="$emit('set-tool', 'fib')">⋋ 費波</button>
      <div class="tool-sep"></div>
      <span style="font-size: 10px; color: var(--text3)">標記：</span>
      <button class="tool-btn" @click="$emit('add-signal', 'buy')">▲ 買入</button>
      <button class="tool-btn" @click="$emit('add-signal', 'sell')">▼ 賣出</button>
      <div class="tool-sep"></div>
      <button class="tool-btn" @click="$emit('clear-drawings')">✕ 清除</button>
      <button class="tool-btn" :disabled="syncingCurrent" @click="$emit('sync-current')">
        {{ syncingCurrent ? "↻ 同步中..." : "↻ 同步" }}
      </button>
    </div>

    <div ref="chartAreaRef" class="chart-area">
      <canvas ref="mainCanvas" id="mainChart" @mousemove="onMouseMove" @mouseleave="onMouseLeave" @click="onChartClick"></canvas>
      <div v-show="loading" class="chart-loading">
        <div class="spinner"></div>
        <p>{{ loadingMessage }}</p>
      </div>
      <div v-show="crosshair.visible" class="crosshair-box">
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
  "sync-current",
  "add-horizontal-line",
  "update-crosshair",
  "hide-crosshair",
]);

const chartAreaRef = ref(null);
const mainCanvas = ref(null);
const volumeCanvas = ref(null);
const rsiCanvas = ref(null);
const macdCanvas = ref(null);
const stochCanvas = ref(null);

const { onMouseMove, onMouseLeave, onChartClick } = useChartEngine({
  mainCanvas,
  volumeCanvas,
  rsiCanvas,
  macdCanvas,
  stochCanvas,
  chartAreaRef,
  props,
  emit,
});

const displayPrice = computed(() => (props.quote.price == null ? "—" : `$${fmtPrice(props.quote.price)}`));
const displayChange = computed(() => {
  if (props.quote.price == null) return "—";
  const sign = props.quote.change_pct >= 0 ? "+" : "";
  return `${sign}${(props.quote.change || 0).toFixed(2)} (${sign}${(props.quote.change_pct || 0).toFixed(2)}%)`;
});
</script>
