<template>
  <div class="chart-toolbar compact-toolbar">
    <button class="tool-btn" :class="{ active: activeTool === 'cursor' }" @click="$emit('set-tool', 'cursor')">⊹ 游標</button>

    <div class="toolbar-menu">
      <button class="tool-btn menu-trigger" :class="{ active: drawingGroupActive }" type="button">
        {{ drawingTriggerLabel }} ▾
      </button>
      <div class="toolbar-menu-panel">
        <button
          v-for="tool in drawingTools"
          :key="tool.key"
          class="tool-btn"
          :class="{ active: activeTool === tool.key }"
          type="button"
          @click="$emit('set-tool', tool.key)"
        >
          {{ tool.label }}
        </button>
      </div>
    </div>

    <button class="tool-btn" @click="$emit('add-signal', 'buy')">▲ 買入</button>
    <button class="tool-btn" @click="$emit('add-signal', 'sell')">▼ 賣出</button>

    <div class="tool-sep"></div>

    <div v-if="timeframeOptions.length" class="toolbar-menu">
      <button class="tool-btn menu-trigger" type="button">
        {{ currentTimeframeLabel }} ▾
      </button>
      <div class="toolbar-menu-panel period-panel">
        <span class="panel-label">時間週期</span>
        <button
          v-for="timeframe in timeframeOptions"
          :key="`${timeframe.tf}-${timeframe.iv}`"
          class="tool-btn"
          :class="{ active: currentPeriod === timeframe.tf && currentInterval === timeframe.iv }"
          type="button"
          @click="$emit('set-timeframe', timeframe)"
        >
          {{ timeframe.label }}
        </button>
        <span class="panel-label">K 別聚合</span>
        <button
          v-for="option in klineOptions"
          :key="option.key"
          class="tool-btn"
          :class="{ active: klineDisplayMode === option.key }"
          type="button"
          @click="$emit('set-kline-display-mode', option.key)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <div class="toolbar-menu">
      <button class="tool-btn menu-trigger" type="button">
        {{ chartModeLabel }} ▾
      </button>
      <div class="toolbar-menu-panel">
        <button
          v-for="mode in chartModes"
          :key="mode.key"
          class="tool-btn"
          :class="{ active: chartMode === mode.key }"
          type="button"
          @click="$emit('set-chart-mode', mode.key)"
        >
          {{ mode.label }}
        </button>
      </div>
    </div>

    <div class="tool-sep"></div>

    <button class="tool-btn" :class="{ active: indicatorDeckOpen }" @click="$emit('toggle-indicator-deck')">
      {{ indicatorDeckOpen ? "收合指標" : "指標面板" }}
    </button>

    <div class="toolbar-menu">
      <button class="tool-btn menu-trigger" type="button">
        更多 ▾
      </button>
      <div class="toolbar-menu-panel more-panel">
        <span class="panel-label">檢視</span>
        <button class="tool-btn" :disabled="!canGoBackHistory" @click="$emit('go-history-back')">↶ 返回</button>
        <button class="tool-btn" :disabled="!canGoForwardHistory" @click="$emit('go-history-forward')">↷ 前進</button>
        <button class="tool-btn" :disabled="!canPanLeft" @click="$emit('pan-left')">← 左移</button>
        <button class="tool-btn" :disabled="!canPanRight" @click="$emit('pan-right')">→ 右移</button>
        <button class="tool-btn" :disabled="!canZoomIn" @click="$emit('zoom-in')">＋ 放大</button>
        <button class="tool-btn" :disabled="!canZoomOut" @click="$emit('zoom-out')">－ 縮小</button>
        <button class="tool-btn" @click="$emit('jump-to-latest')">最新</button>
        <button class="tool-btn" @click="$emit('reset-view')">重設</button>

        <span class="panel-label">Y 軸</span>
        <button class="tool-btn" @click="$emit('zoom-y-in')">Y＋</button>
        <button class="tool-btn" @click="$emit('zoom-y-out')">Y－</button>
        <button class="tool-btn" :disabled="!canResetYScale" @click="$emit('reset-y-scale')">Y 自動</button>
        <button class="tool-btn" :class="{ active: priceScaleMode === 'linear' }" @click="$emit('set-price-scale-mode', 'linear')">線性</button>
        <button class="tool-btn" :class="{ active: priceScaleMode === 'log' }" :disabled="!canUseLogScale" @click="$emit('set-price-scale-mode', 'log')">對數</button>

        <span class="panel-label">引擎</span>
        <button class="tool-btn" :class="{ active: engineMode === 'legacy' }" @click="$emit('set-engine-mode', 'legacy')">Legacy</button>
        <button class="tool-btn" :class="{ active: engineMode === 'lwc' }" @click="$emit('set-engine-mode', 'lwc')">LWC Beta</button>

        <span class="panel-label">版面</span>
        <button
          v-for="layout in layoutOptions"
          :key="layout.key"
          class="tool-btn"
          :class="{ active: chartLayout === layout.key }"
          type="button"
          @click="$emit('set-chart-layout', layout.key)"
        >
          {{ layout.label }}
        </button>

        <span class="panel-label">整理</span>
        <button class="tool-btn" @click="$emit('remove-last-drawing')">↶ 復原</button>
        <button class="tool-btn" @click="$emit('clear-drawings')">✕ 清除</button>
        <button class="tool-btn" @click="$emit('clear-indicators')">清指標</button>
        <button class="tool-btn" :class="{ active: isFullscreen }" @click="$emit('toggle-fullscreen')">
          {{ isFullscreen ? "退出全螢幕" : "K線全螢幕" }}
        </button>
      </div>
    </div>

    <div class="tool-sep"></div>

    <button class="tool-btn" :disabled="syncingCurrent" @click="$emit('sync-current')">
      {{ syncingCurrent ? "↻ 同步中..." : "↻ 同步" }}
    </button>
    <button class="tool-btn" @click="$emit('open-journal-entry', { ticker: currentTicker, entry_price: quote.price })">✎ 寫日誌</button>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  activeTool: { type: String, required: true },
  canGoBackHistory: { type: Boolean, default: false },
  canGoForwardHistory: { type: Boolean, default: false },
  canPanLeft: { type: Boolean, default: false },
  canPanRight: { type: Boolean, default: false },
  canZoomIn: { type: Boolean, default: false },
  canZoomOut: { type: Boolean, default: false },
  canResetYScale: { type: Boolean, default: false },
  priceScaleMode: { type: String, required: true },
  canUseLogScale: { type: Boolean, default: false },
  timeframeOptions: { type: Array, default: () => [] },
  currentPeriod: { type: String, default: "1y" },
  currentInterval: { type: String, default: "1d" },
  chartMode: { type: String, required: true },
  engineMode: { type: String, default: "legacy" },
  klineDisplayMode: { type: String, required: true },
  indicatorDeckOpen: { type: Boolean, default: false },
  isFullscreen: { type: Boolean, default: false },
  chartLayout: { type: String, required: true },
  syncingCurrent: { type: Boolean, default: false },
  currentTicker: { type: String, required: true },
  quote: { type: Object, required: true },
});

defineEmits([
  "set-tool",
  "add-signal",
  "remove-last-drawing",
  "clear-drawings",
  "go-history-back",
  "go-history-forward",
  "pan-left",
  "pan-right",
  "zoom-in",
  "zoom-out",
  "jump-to-latest",
  "reset-view",
  "set-timeframe",
  "zoom-y-in",
  "zoom-y-out",
  "reset-y-scale",
  "set-price-scale-mode",
  "set-chart-mode",
  "set-engine-mode",
  "set-kline-display-mode",
  "clear-indicators",
  "toggle-indicator-deck",
  "toggle-fullscreen",
  "set-chart-layout",
  "sync-current",
  "open-journal-entry",
]);

const drawingTools = [
  { key: "hline", label: "─ 水平線" },
  { key: "vline", label: "│ 垂直線" },
  { key: "tline", label: "╱ 趨勢線" },
  { key: "arrow", label: "↗ 箭頭" },
  { key: "fib", label: "⋮ 費波" },
  { key: "rect", label: "▬ 區間" },
  { key: "measure", label: "⊕ 測距" },
  { key: "note", label: "✎ 註記" },
  { key: "boxzoom", label: "□ 框選" },
];

const chartModes = [
  { key: "candles", label: "K 線" },
  { key: "line", label: "折線" },
  { key: "area", label: "面積" },
];

const klineOptions = [
  { key: "day", label: "日K" },
  { key: "week", label: "週K" },
  { key: "month", label: "月K" },
  { key: "quarter", label: "季K" },
];

const layoutOptions = [
  { key: "single", label: "1 圖" },
  { key: "double", label: "2 圖" },
  { key: "quad", label: "4 圖" },
];

const drawingGroupActive = computed(() => drawingTools.some((tool) => tool.key === props.activeTool));
const drawingTriggerLabel = computed(() => drawingTools.find((tool) => tool.key === props.activeTool)?.label || "繪圖");
const currentTimeframeLabel = computed(() => {
  const match = props.timeframeOptions.find(
    (timeframe) => timeframe.tf === props.currentPeriod && timeframe.iv === props.currentInterval,
  );
  return match?.label || "週期";
});
const chartModeLabel = computed(() => chartModes.find((mode) => mode.key === props.chartMode)?.label || "圖型");
</script>

<style scoped>
.compact-toolbar {
  overflow: visible;
}

.toolbar-menu {
  position: relative;
  display: inline-flex;
}

.toolbar-menu-panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 40;
  display: none;
  min-width: 168px;
  max-width: min(360px, calc(100vw - 28px));
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(7, 12, 19, 0.98);
  box-shadow: 0 18px 36px rgba(0, 0, 0, 0.32);
  gap: 6px;
  flex-wrap: wrap;
}

.toolbar-menu:focus-within .toolbar-menu-panel,
.toolbar-menu:hover .toolbar-menu-panel {
  display: flex;
}

.period-panel,
.more-panel {
  min-width: 300px;
}

.panel-label {
  width: 100%;
  margin: 2px 0 0;
  color: var(--text3);
  font-size: 10px;
}

.menu-trigger {
  min-width: 78px;
  justify-content: center;
}
</style>
