<template>
  <div class="chart-toolbar">
    <span class="tool-label">繪圖：</span>
    <button class="tool-btn" :class="{ active: activeTool === 'cursor' }" @click="$emit('set-tool', 'cursor')">⊹ 游標</button>
    <button class="tool-btn" :class="{ active: activeTool === 'hline' }" @click="$emit('set-tool', 'hline')">─ 水平線</button>
    <button class="tool-btn" :class="{ active: activeTool === 'vline' }" @click="$emit('set-tool', 'vline')">│ 垂直線</button>
    <button class="tool-btn" :class="{ active: activeTool === 'tline' }" @click="$emit('set-tool', 'tline')">╱ 趨勢線</button>
    <button class="tool-btn" :class="{ active: activeTool === 'arrow' }" @click="$emit('set-tool', 'arrow')">↗ 箭頭</button>
    <button class="tool-btn" :class="{ active: activeTool === 'fib' }" @click="$emit('set-tool', 'fib')">⋮ 費波</button>
    <button class="tool-btn" :class="{ active: activeTool === 'rect' }" @click="$emit('set-tool', 'rect')">▬ 區間</button>
    <button class="tool-btn" :class="{ active: activeTool === 'measure' }" @click="$emit('set-tool', 'measure')">⊕ 測距</button>
    <button class="tool-btn" :class="{ active: activeTool === 'note' }" @click="$emit('set-tool', 'note')">✎ 註記</button>
    <button class="tool-btn" :class="{ active: activeTool === 'boxzoom' }" @click="$emit('set-tool', 'boxzoom')">□ 框選</button>

    <div class="tool-sep"></div>

    <span class="tool-label">標記：</span>
    <button class="tool-btn" @click="$emit('add-signal', 'buy')">▲ 買入</button>
    <button class="tool-btn" @click="$emit('add-signal', 'sell')">▼ 賣出</button>
    <button class="tool-btn" @click="$emit('remove-last-drawing')">↶ 復原</button>
    <button class="tool-btn" @click="$emit('clear-drawings')">✕ 清除</button>

    <div class="tool-sep"></div>

    <span class="tool-label">檢視：</span>
    <button class="tool-btn" :disabled="!canGoBackHistory" @click="$emit('go-history-back')">↶ 返回</button>
    <button class="tool-btn" :disabled="!canGoForwardHistory" @click="$emit('go-history-forward')">↷ 前進</button>
    <button class="tool-btn" :disabled="!canPanLeft" @click="$emit('pan-left')">← 左移</button>
    <button class="tool-btn" :disabled="!canPanRight" @click="$emit('pan-right')">→ 右移</button>
    <button class="tool-btn" :disabled="!canZoomIn" @click="$emit('zoom-in')">＋ 放大</button>
    <button class="tool-btn" :disabled="!canZoomOut" @click="$emit('zoom-out')">－ 縮小</button>
    <button class="tool-btn" @click="$emit('jump-to-latest')">最新</button>
    <button class="tool-btn" @click="$emit('reset-view')">重置</button>

    <div class="tool-sep"></div>

    <template v-if="timeframeOptions.length">
      <span class="tool-label">週期：</span>
      <button
        v-for="timeframe in timeframeOptions"
        :key="`${timeframe.tf}-${timeframe.iv}`"
        class="tool-btn"
        :class="{ active: currentPeriod === timeframe.tf && currentInterval === timeframe.iv }"
        @click="$emit('set-timeframe', timeframe)"
      >
        {{ timeframe.label }}
      </button>

      <div class="tool-sep"></div>
    </template>

    <span class="tool-label">Y 軸：</span>
    <button class="tool-btn" @click="$emit('zoom-y-in')">Y＋</button>
    <button class="tool-btn" @click="$emit('zoom-y-out')">Y－</button>
    <button class="tool-btn" :disabled="!canResetYScale" @click="$emit('reset-y-scale')">Y 自動</button>
    <button class="tool-btn" :class="{ active: priceScaleMode === 'linear' }" @click="$emit('set-price-scale-mode', 'linear')">線性</button>
    <button class="tool-btn" :class="{ active: priceScaleMode === 'log' }" :disabled="!canUseLogScale" @click="$emit('set-price-scale-mode', 'log')">對數</button>

    <div class="tool-sep"></div>

    <span class="tool-label">圖型：</span>
    <button class="tool-btn" :class="{ active: chartMode === 'candles' }" @click="$emit('set-chart-mode', 'candles')">K 線</button>
    <button class="tool-btn" :class="{ active: chartMode === 'line' }" @click="$emit('set-chart-mode', 'line')">折線</button>
    <button class="tool-btn" :class="{ active: chartMode === 'area' }" @click="$emit('set-chart-mode', 'area')">面積</button>

    <div class="tool-sep"></div>

    <span class="tool-label">引擎：</span>
    <button class="tool-btn" :class="{ active: engineMode === 'legacy' }" @click="$emit('set-engine-mode', 'legacy')">Legacy</button>
    <button class="tool-btn" :class="{ active: engineMode === 'lwc' }" @click="$emit('set-engine-mode', 'lwc')">LWC Beta</button>

    <div class="tool-sep"></div>

    <span class="tool-label">K別：</span>
    <button class="tool-btn" :class="{ active: klineDisplayMode === 'day' }" @click="$emit('set-kline-display-mode', 'day')">日K</button>
    <button class="tool-btn" :class="{ active: klineDisplayMode === 'week' }" @click="$emit('set-kline-display-mode', 'week')">週K</button>
    <button class="tool-btn" :class="{ active: klineDisplayMode === 'month' }" @click="$emit('set-kline-display-mode', 'month')">月K</button>
    <button class="tool-btn" :class="{ active: klineDisplayMode === 'quarter' }" @click="$emit('set-kline-display-mode', 'quarter')">季K</button>
    <button class="tool-btn" @click="$emit('clear-indicators')">清指標</button>

    <button class="tool-btn" :class="{ active: isFullscreen }" @click="$emit('toggle-fullscreen')">
      {{ isFullscreen ? "退出全螢幕" : "K線全螢幕" }}
    </button>

    <div class="tool-sep"></div>

    <span class="tool-label">版面：</span>
    <button class="tool-btn" :class="{ active: chartLayout === 'single' }" @click="$emit('set-chart-layout', 'single')">1 圖</button>
    <button class="tool-btn" :class="{ active: chartLayout === 'double' }" @click="$emit('set-chart-layout', 'double')">2 圖</button>
    <button class="tool-btn" :class="{ active: chartLayout === 'quad' }" @click="$emit('set-chart-layout', 'quad')">4 圖</button>

    <div class="tool-sep"></div>

    <button class="tool-btn" :disabled="syncingCurrent" @click="$emit('sync-current')">
      {{ syncingCurrent ? "↻ 同步中..." : "↻ 同步" }}
    </button>
    <button class="tool-btn" @click="$emit('open-journal-entry', { ticker: currentTicker, entry_price: quote.price })">✎ 寫日誌</button>
  </div>
</template>

<script setup>
defineProps({
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
  "toggle-fullscreen",
  "set-chart-layout",
  "sync-current",
  "open-journal-entry",
]);
</script>
