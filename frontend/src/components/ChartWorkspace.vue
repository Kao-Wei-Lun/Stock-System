<template>
  <div class="center">
    <div class="chart-header">
      <div>
        <div style="display: flex; align-items: baseline; gap: 8px">
          <div class="ch-ticker">{{ currentTicker || "—" }}</div>
          <div style="font-size: 11px; color: var(--text3)">{{ currentName || "載入中..." }}</div>
        </div>
        <div v-if="quoteFreshnessState !== 'live'" class="quote-risk-banner" :class="quoteFreshnessState">
          {{ quoteFreshnessHint }}
        </div>
        <div v-if="showMacroRegimeBanner" class="market-regime-banner" :class="macroRegimeClass">
          <span class="market-regime-pill">{{ macroRiskLabel }}</span>
          <strong>{{ macroPostureLabel }}</strong>
          <span>{{ macroDecisionHint }}</span>
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
      <button class="tool-btn" :class="{ active: activeTool === 'arrow' }" @click="$emit('set-tool', 'arrow')">↗ 箭頭</button>
      <button class="tool-btn" :class="{ active: activeTool === 'fib' }" @click="$emit('set-tool', 'fib')">⋮ 費波</button>
      <button class="tool-btn" :class="{ active: activeTool === 'rect' }" @click="$emit('set-tool', 'rect')">▭ 區間</button>
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

      <span class="tool-label">K別：</span>
      <button class="tool-btn" :class="{ active: klineDisplayMode === 'day' }" @click="$emit('set-kline-display-mode', 'day')">日K</button>
      <button class="tool-btn" :class="{ active: klineDisplayMode === 'week' }" @click="$emit('set-kline-display-mode', 'week')">週K</button>
      <button class="tool-btn" :class="{ active: klineDisplayMode === 'month' }" @click="$emit('set-kline-display-mode', 'month')">月K</button>
      <button class="tool-btn" :class="{ active: klineDisplayMode === 'quarter' }" @click="$emit('set-kline-display-mode', 'quarter')">季K</button>
      <button class="tool-btn" @click="handleClearIndicators">清指標</button>

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

    <div class="chart-meta">
      <div class="meta-chip">{{ visibleRangeLabel }}</div>
      <div class="meta-chip">{{ visibleBarsLabel }}</div>
      <div class="meta-chip" :class="visibleChangeClass">{{ visibleChangeLabel }}</div>
      <div class="meta-chip">{{ zoomLabel }}</div>
      <div class="meta-chip">{{ yScaleLabel }}</div>
      <div class="meta-chip">{{ priceScaleModeLabel }}</div>
      <div class="meta-chip">{{ quoteTimestampLabel }}</div>
      <div class="meta-chip">{{ quoteSourceLabel }}</div>
      <div class="meta-chip" :class="{ up: !quote.is_delayed, dn: quote.is_delayed }">{{ quoteDelayLabel }}</div>
      <div class="meta-chip" :class="quoteFreshnessChipClass">{{ quoteFreshnessLabel }}</div>
      <div v-if="institutionalOverlay" class="meta-chip">
        {{ institutionalOverlay.label }} / Basis
        {{ institutionalOverlay.basis == null ? "—" : `${institutionalOverlay.basis >= 0 ? "+" : ""}${fmtPrice(institutionalOverlay.basis)} (${institutionalOverlay.basisPct >= 0 ? "+" : ""}${Number(institutionalOverlay.basisPct || 0).toFixed(2)}%)` }}
      </div>
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

    <div v-if="showComparePanel" class="compare-legend">
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
          <span class="drawing-shortcuts">快捷鍵：V 游標 / H 水平 / L 垂直 / T 趨勢 / A 箭頭 / F 費波 / R 區間 / M 測距 / N 註記 / B 框選 / Del 刪除 / Esc 取消</span>
          <button class="tool-btn compact" :disabled="!selectedDrawingId" @click="removeSelectedDrawing">刪除所選</button>
        </div>
      </div>
      <div class="drawing-list">
        <div
          v-for="drawing in drawings"
          :key="drawing.id || drawingLabel(drawing)"
          class="drawing-chip"
          :class="{ active: drawing.id === selectedDrawingId, muted: drawing.hidden, locked: drawing.locked }"
          @click="$emit('select-drawing', drawing.id)"
        >
          <span class="drawing-chip-type">{{ drawingTypeLabel(drawing.type) }}</span>
          <span class="drawing-chip-label">{{ drawingLabel(drawing) }}</span>
          <button
            class="drawing-chip-action"
            :class="{ active: !drawing.hidden }"
            :title="drawing.hidden ? '顯示物件' : '隱藏物件'"
            @click.stop="$emit('toggle-drawing-visibility', drawing.id)"
          >
            {{ drawing.hidden ? "隱" : "顯" }}
          </button>
          <button
            class="drawing-chip-action"
            :class="{ active: drawing.locked }"
            :title="drawing.locked ? '解除鎖定' : '鎖定物件'"
            @click.stop="$emit('toggle-drawing-lock', drawing.id)"
          >
            {{ drawing.locked ? "鎖" : "編" }}
          </button>
          <span class="drawing-chip-close" @click.stop="$emit('remove-drawing', drawing.id)">✕</span>
        </div>
      </div>
    </div>

    <div v-if="selectedDrawing" class="drawing-props">
      <div class="drawing-manager-head">
        <div class="drawing-manager-title">屬性面板</div>
        <div class="drawing-manager-actions">
          <span class="drawing-shortcuts">{{ drawingTypeLabel(selectedDrawing.type) }} / {{ drawingLabel(selectedDrawing) }}</span>
        </div>
      </div>
      <div class="drawing-prop-grid">
        <label class="drawing-prop">
          <span>顏色</span>
          <input class="drawing-color" type="color" :value="selectedDrawing.color || '#00d4ff'" @input="updateSelectedDrawing({ color: $event.target.value })" />
        </label>
        <label v-if="supportsLineWidth" class="drawing-prop">
          <span>線寬</span>
          <input class="drawing-range" type="range" min="1" max="5" step="0.5" :value="selectedDrawing.lineWidth || 1.5" @input="updateSelectedDrawing({ lineWidth: Number($event.target.value) })" />
          <strong>{{ Number(selectedDrawing.lineWidth || 1.5).toFixed(1) }}</strong>
        </label>
        <label v-if="supportsLineStyle" class="drawing-prop">
          <span>線型</span>
          <select class="drawing-select" :value="selectedDrawing.lineStyle || 'solid'" @change="updateSelectedDrawing({ lineStyle: $event.target.value })">
            <option value="solid">實線</option>
            <option value="dash">虛線</option>
            <option value="dot">點線</option>
          </select>
        </label>
        <label class="drawing-prop wide">
          <span>標籤</span>
          <input class="drawing-text" type="text" :value="selectedDrawing.label || ''" placeholder="可選，顯示在圖上的說明" @input="updateSelectedDrawing({ label: $event.target.value })" />
        </label>
        <label v-if="supportsText" class="drawing-prop wide">
          <span>註記文字</span>
          <input class="drawing-text" type="text" :value="selectedDrawing.text || ''" placeholder="編輯註記內容" @input="updateSelectedDrawing({ text: $event.target.value })" />
        </label>
        <label v-if="supportsFillOpacity" class="drawing-prop">
          <span>填色透明</span>
          <input class="drawing-range" type="range" min="0.05" max="0.95" step="0.05" :value="selectedDrawing.fillOpacity || 0.12" @input="updateSelectedDrawing({ fillOpacity: Number($event.target.value) })" />
          <strong>{{ Math.round((selectedDrawing.fillOpacity || 0.12) * 100) }}%</strong>
        </label>
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
        <div class="ci-row"><span class="ci-label">游標價</span><span>{{ crosshair.hoverPrice }}</span></div>
        <div class="ci-row"><span class="ci-label">開盤</span><span>{{ crosshair.open }}</span></div>
        <div class="ci-row"><span class="ci-label">最高</span><span>{{ crosshair.high }}</span></div>
        <div class="ci-row"><span class="ci-label">最低</span><span>{{ crosshair.low }}</span></div>
        <div class="ci-row"><span class="ci-label">收盤</span><span>{{ crosshair.close }}</span></div>
        <div class="ci-row"><span class="ci-label">漲跌</span><span>{{ crosshair.change }} ({{ crosshair.changePct }})</span></div>
        <div class="ci-row"><span class="ci-label">成交量</span><span>{{ crosshair.volume }}</span></div>
      </div>

      <div v-if="visibleEventMarkers.length" class="chart-event-overlay">
        <button
          v-for="marker in visibleEventMarkers"
          :key="marker.key"
          type="button"
          class="chart-event-marker"
          :class="[marker.importance || 'medium', { active: focusedEventKey === marker.key }]"
          :style="{ left: marker.left }"
          :title="`${marker.title} / ${marker.event_date}`"
          @click="jumpToEvent(marker)"
        >
          <span class="chart-event-line"></span>
          <span class="chart-event-dot"></span>
        </button>
      </div>
    </div>

    <div v-if="showIntelStrip" class="intel-strip">
      <section class="intel-mini-card">
        <div class="intel-mini-head">
          <strong>事件焦點</strong>
          <span>{{ tickerEvents.length }} 筆</span>
        </div>
        <button
          v-for="item in tickerEvents.slice(0, 4)"
          :key="`${item.event_type}-${item.event_date}`"
          type="button"
          class="intel-mini-row"
          @click="jumpToEvent(item)"
        >
          <span>{{ item.title }}</span>
          <small>{{ item.event_date }}</small>
        </button>
      </section>

      <section v-if="fundamentalsSummary" class="intel-mini-card">
        <div class="intel-mini-head">
          <strong>基本面摘要</strong>
          <span>{{ fundamentalsSummary.updated_at ? "已同步" : "local" }}</span>
        </div>
        <div class="intel-mini-title">{{ fundamentalsSummary.headline }}</div>
        <div class="intel-badge-row">
          <span v-for="signal in fundamentalsSummary.signals || []" :key="`${signal.label}-${signal.value}`" class="intel-badge">
            {{ signal.label }} · {{ signal.value }}
          </span>
        </div>
      </section>

      <section v-if="taiwanChipSummary" class="intel-mini-card">
        <div class="intel-mini-head">
          <strong>台股籌碼</strong>
          <span :class="`bias-${taiwanChipSummary.bias || 'neutral'}`">{{ taiwanChipSummary.bias || "neutral" }}</span>
        </div>
        <div class="intel-badge-row">
          <span v-for="signal in taiwanChipSummary.signals || []" :key="`${signal.label}-${signal.value}`" class="intel-badge">
            {{ signal.label }} · {{ signal.value }}
          </span>
        </div>
      </section>

      <section class="intel-mini-card">
        <div class="intel-mini-head">
          <strong>新聞快照</strong>
          <span>{{ tickerNews.length }} 則</span>
        </div>
        <a
          v-for="article in tickerNews.slice(0, 3)"
          :key="`${article.title}-${article.published_at}`"
          class="intel-mini-row link"
          :href="article.url"
          target="_blank"
          rel="noreferrer"
        >
          <span>{{ article.title }}</span>
          <small>{{ formatTimestamp(article.published_at) }}</small>
        </a>
      </section>
    </div>

    <div v-if="layoutPanes.length" class="sync-layout-grid" :class="`is-${chartLayout}`">
      <div v-for="pane in layoutPanes" :key="pane.key" class="sync-pane-card">
        <div class="sync-pane-head">
          <span>{{ pane.title }}</span>
          <span>{{ currentTicker }}</span>
        </div>
        <canvas :ref="(el) => setSyncPaneRef(pane.key, el)"></canvas>
      </div>
    </div>

    <div v-if="showComparePanel" class="ind-panel visible compare-panel">
      <div class="ind-label-tag">COMPARE ({{ comparisonMode === "percent" ? "%" : "PRICE" }})</div>
      <canvas ref="compareCanvas"></canvas>
    </div>
    <div v-if="showVolumePanel" class="volume-area"><canvas ref="volumeCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.rsi }"><div class="ind-label-tag">{{ rsiLabel }}</div><canvas ref="rsiCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.aroon }"><div class="ind-label-tag">{{ aroonLabel }}</div><canvas ref="aroonCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.trix }"><div class="ind-label-tag">{{ trixLabel }}</div><canvas ref="trixCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.williamsr }"><div class="ind-label-tag">{{ williamsrLabel }}</div><canvas ref="williamsrCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.mfi }"><div class="ind-label-tag">{{ mfiLabel }}</div><canvas ref="mfiCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.roc }"><div class="ind-label-tag">{{ rocLabel }}</div><canvas ref="rocCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.bbPercent }"><div class="ind-label-tag">{{ bbPercentLabel }}</div><canvas ref="bbPercentCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.bbWidth }"><div class="ind-label-tag">{{ bbWidthLabel }}</div><canvas ref="bbWidthCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: showMacdPanel }"><div class="ind-label-tag">{{ macdLabel }}</div><canvas ref="macdCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: showStochPanel }"><div class="ind-label-tag">{{ stochLabel }}</div><canvas ref="stochCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.atr }"><div class="ind-label-tag">{{ atrLabel }}</div><canvas ref="atrCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.cci }"><div class="ind-label-tag">{{ cciLabel }}</div><canvas ref="cciCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.obv }"><div class="ind-label-tag">OBV</div><canvas ref="obvCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.adx }"><div class="ind-label-tag">{{ adxLabel }}</div><canvas ref="adxCanvas"></canvas></div>
    <div class="ind-panel" :class="{ visible: activePanels.cmf }"><div class="ind-label-tag">{{ cmfLabel }}</div><canvas ref="cmfCanvas"></canvas></div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import { normalizeTicker } from "../composables/useDashboard";
import { useChartEngine } from "../composables/useChartEngine";
import { fmtMktCap, fmtPrice, fmtVol } from "../utils/formatters";

const props = defineProps({
  currentTicker: { type: String, required: true },
  currentName: { type: String, required: true },
  quote: { type: Object, required: true },
  activeTool: { type: String, required: true },
  activePanels: { type: Object, required: true },
  klineDisplayMode: { type: String, default: "day" },
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
  tickerNews: { type: Array, default: () => [] },
  macroSummary: { type: Object, default: null },
  fundamentalsSummary: { type: Object, default: null },
  taiwanChipSummary: { type: Object, default: null },
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
  "update-crosshair",
  "hide-crosshair",
  "add-compare",
  "remove-compare",
  "clear-compare",
  "set-compare-mode",
  "set-kline-display-mode",
  "set-chart-layout",
  "clear-indicators",
  "toggle-fullscreen",
  "open-journal-entry",
]);

const chartAreaRef = ref(null);
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
const syncPaneRefs = reactive({});
let syncPaneFrame = 0;

const {
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
} = useChartEngine({
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
const showIntelStrip = computed(() => Boolean(
  (props.tickerEvents || []).length
  || (props.tickerNews || []).length
  || props.fundamentalsSummary
  || props.taiwanChipSummary,
));
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
const showComparePanel = computed(() => props.compareSeries.length > 0 && !props.cleanChartMode);
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

function formatTimestamp(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-TW", { hour12: false });
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

function setSyncPaneRef(key, element) {
  if (element) syncPaneRefs[key] = element;
  else delete syncPaneRefs[key];
  scheduleSyncPaneRender();
}

function formatPaneDateLabel(dateString, range = 0) {
  if (!dateString) return "";
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return dateString.slice(5);
  if (range > 540) {
    return `${String(date.getFullYear()).slice(2)}/${String(date.getMonth() + 1).padStart(2, "0")}`;
  }
  return `${String(date.getFullYear()).slice(2)}/${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")}`;
}

function getPaneTickIndices(data, count = 5) {
  if (!data.length) return [];
  const indices = new Set([0, data.length - 1]);
  const step = Math.max(1, Math.floor((data.length - 1) / Math.max(count - 1, 1)));
  for (let index = 0; index < data.length; index += step) {
    indices.add(index);
  }
  return [...indices].sort((left, right) => left - right);
}

function resizeSyncPaneCanvas(canvas) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const { clientWidth, clientHeight } = canvas;
  canvas.width = Math.max(1, clientWidth * dpr);
  canvas.height = Math.max(1, clientHeight * dpr);
  canvas.style.width = `${clientWidth}px`;
  canvas.style.height = `${clientHeight}px`;
}

function drawSyncPane(canvas, pane) {
  if (!canvas || !visibleData.value.length) {
    if (canvas) {
      const ctx = canvas.getContext("2d");
      const dpr = window.devicePixelRatio || 1;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, canvas.width / dpr, canvas.height / dpr);
    }
    return;
  }

  resizeSyncPaneCanvas(canvas);
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.width / dpr;
  const height = canvas.height / dpr;
  const pad = { top: 18, right: 12, bottom: 20, left: 10 };
  const data = visibleData.value;
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;
  const step = chartWidth / Math.max(data.length, 1);
  const barWidth = Math.max(1.5, step * 0.68);
  const xAt = (index) => pad.left + (index + 0.5) * step;
  const highs = data.map((row) => row.high);
  const lows = data.map((row) => row.low);
  const rawMin = Math.min(...lows);
  const rawMax = Math.max(...highs);
  const padValue = Math.max((rawMax - rawMin) * 0.12, Math.abs(rawMax) * 0.02, 0.05);
  const min = rawMin - padValue;
  const max = rawMax + padValue;
  const scaleY = (value) => pad.top + (1 - (value - min) / (max - min || 1)) * chartHeight;
  const rangeDays = data.length > 1
    ? Math.abs((new Date(data[data.length - 1].date) - new Date(data[0].date)) / 86400000)
    : 0;

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "rgba(8,12,18,0.96)";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(30,45,61,0.72)";
  ctx.lineWidth = 0.5;
  [0, 0.33, 0.66, 1].forEach((ratio) => {
    const y = pad.top + chartHeight * ratio;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
  });

  const closes = data.map((row) => row.close);
  if (pane.mode === "candles") {
    data.forEach((row, index) => {
      const x = xAt(index);
      const isUp = row.close >= row.open;
      const color = isUp ? "#00d9a3" : "#ff4d6a";
      ctx.strokeStyle = color;
      ctx.fillStyle = isUp ? "rgba(0,217,163,0.88)" : "rgba(255,77,106,0.88)";
      ctx.beginPath();
      ctx.moveTo(x, scaleY(row.high));
      ctx.lineTo(x, scaleY(row.low));
      ctx.stroke();
      const top = scaleY(Math.max(row.open, row.close));
      const bottom = scaleY(Math.min(row.open, row.close));
      ctx.fillRect(x - barWidth / 2, top, barWidth, Math.max(1, bottom - top));
    });
  } else {
    ctx.beginPath();
    closes.forEach((value, index) => {
      if (index === 0) ctx.moveTo(xAt(index), scaleY(value));
      else ctx.lineTo(xAt(index), scaleY(value));
    });
    if (pane.mode === "area") {
      ctx.lineTo(xAt(data.length - 1), height - pad.bottom);
      ctx.lineTo(xAt(0), height - pad.bottom);
      ctx.closePath();
      ctx.fillStyle = "rgba(0,212,255,0.12)";
      ctx.fill();
      ctx.beginPath();
      closes.forEach((value, index) => {
        if (index === 0) ctx.moveTo(xAt(index), scaleY(value));
        else ctx.lineTo(xAt(index), scaleY(value));
      });
    }
    ctx.strokeStyle = pane.mode === "area" ? "#00d4ff" : "#8dc1ff";
    ctx.lineWidth = 1.6;
    ctx.stroke();
  }

  const tickIndices = getPaneTickIndices(data, 4);
  ctx.fillStyle = "rgba(99,123,148,0.9)";
  ctx.font = "9px JetBrains Mono";
  tickIndices.forEach((index) => {
    const x = xAt(index);
    ctx.beginPath();
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, height - pad.bottom);
    ctx.strokeStyle = "rgba(30,45,61,0.5)";
    ctx.stroke();
    const label = formatPaneDateLabel(data[index].date, rangeDays);
    ctx.fillText(label, Math.max(pad.left, x - Math.max(16, label.length * 3.4)), height - 5);
  });

  if (
    props.crosshair.visible
    && Number.isInteger(props.crosshair.absoluteIndex)
    && props.crosshair.absoluteIndex >= viewportStartIndex.value
    && props.crosshair.absoluteIndex < viewportStartIndex.value + data.length
  ) {
    const localIndex = props.crosshair.absoluteIndex - viewportStartIndex.value;
    const x = xAt(localIndex);
    ctx.strokeStyle = "rgba(255,209,102,0.95)";
    ctx.setLineDash([5, 3]);
    ctx.beginPath();
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, height - pad.bottom);
    ctx.stroke();
    ctx.setLineDash([]);

    const label = formatPaneDateLabel(data[localIndex]?.date, rangeDays);
    const labelWidth = Math.max(44, label.length * 8 + 10);
    const left = Math.min(Math.max(pad.left, x - labelWidth / 2), width - pad.right - labelWidth);
    ctx.fillStyle = "rgba(255,209,102,0.16)";
    ctx.fillRect(left, 2, labelWidth, 14);
    ctx.strokeStyle = "rgba(255,209,102,0.88)";
    ctx.strokeRect(left, 2, labelWidth, 14);
    ctx.fillStyle = "#ffd166";
    ctx.fillText(label, left + 6, 12);
  }
}

function renderSyncPanes() {
  layoutPanes.value.forEach((pane) => {
    drawSyncPane(syncPaneRefs[pane.key], pane);
  });
}

function scheduleSyncPaneRender() {
  if (syncPaneFrame) cancelAnimationFrame(syncPaneFrame);
  syncPaneFrame = window.requestAnimationFrame(() => {
    syncPaneFrame = 0;
    renderSyncPanes();
  });
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
  () => [
    props.chartLayout,
    props.currentTicker,
    props.crosshair.visible,
    props.crosshair.absoluteIndex,
    chartMode.value,
    visibleData.value.length,
    viewportStartIndex.value,
  ],
  () => scheduleSyncPaneRender(),
  { deep: true },
);

watch(
  () => props.ohlcData,
  () => scheduleSyncPaneRender(),
  { deep: true },
);

onMounted(() => {
  window.addEventListener("keydown", handleKeydown);
  window.addEventListener("resize", scheduleSyncPaneRender);
  nextTick(() => scheduleSyncPaneRender());
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
  window.removeEventListener("resize", scheduleSyncPaneRender);
  if (syncPaneFrame) cancelAnimationFrame(syncPaneFrame);
});
</script>

<style scoped>
.quote-risk-banner {
  display: inline-flex;
  align-items: center;
  margin-top: 6px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  line-height: 1.4;
}

.quote-risk-banner.delayed {
  background: rgba(255, 209, 102, 0.14);
  color: #ffd166;
}

.quote-risk-banner.stale,
.quote-risk-banner.missing {
  background: rgba(255, 77, 106, 0.14);
  color: #ff8a9d;
}

.market-regime-banner {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 12px;
  font-size: 11px;
  line-height: 1.5;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text2);
}

.market-regime-banner strong {
  color: var(--text1);
}

.market-regime-pill {
  border-radius: 999px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.08);
}

.market-regime-banner.is-defensive {
  background: rgba(255, 107, 107, 0.12);
}

.market-regime-banner.is-defensive .market-regime-pill {
  background: rgba(255, 107, 107, 0.2);
  color: #ffd0d0;
}

.market-regime-banner.is-selective,
.market-regime-banner.is-balanced {
  background: rgba(255, 209, 102, 0.12);
}

.market-regime-banner.is-selective .market-regime-pill,
.market-regime-banner.is-balanced .market-regime-pill {
  background: rgba(255, 209, 102, 0.2);
  color: #ffe2a6;
}

.market-regime-banner.is-offensive {
  background: rgba(0, 217, 163, 0.12);
}

.market-regime-banner.is-offensive .market-regime-pill {
  background: rgba(0, 217, 163, 0.2);
  color: #bfffea;
}

.meta-chip.warn {
  color: #ffd166;
  border-color: rgba(255, 209, 102, 0.24);
}

.chart-event-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.chart-event-marker {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 18px;
  margin-left: -9px;
  border: 0;
  background: transparent;
  padding: 0;
  pointer-events: auto;
  cursor: pointer;
}

.chart-event-line {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
  background: rgba(255, 209, 102, 0.45);
}

.chart-event-dot {
  position: absolute;
  top: 18px;
  left: 50%;
  width: 8px;
  height: 8px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: #ffd166;
  box-shadow: 0 0 0 4px rgba(255, 209, 102, 0.12);
}

.chart-event-marker.high .chart-event-dot {
  background: #ff7b72;
  box-shadow: 0 0 0 4px rgba(255, 123, 114, 0.12);
}

.chart-event-marker.low .chart-event-dot {
  background: #86d98f;
  box-shadow: 0 0 0 4px rgba(134, 217, 143, 0.12);
}

.chart-event-marker.active .chart-event-line {
  background: rgba(0, 212, 255, 0.7);
}

.chart-event-marker.active .chart-event-dot {
  background: #00d4ff;
  box-shadow: 0 0 0 4px rgba(0, 212, 255, 0.14);
}

.intel-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.intel-mini-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(8, 12, 18, 0.82);
  border-radius: 14px;
  padding: 12px;
}

.intel-mini-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--text2);
  font-size: 11px;
  margin-bottom: 10px;
}

.intel-mini-title {
  color: var(--text1);
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 10px;
}

.intel-mini-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  border-radius: 10px;
  padding: 8px 10px;
  text-decoration: none;
  margin-bottom: 8px;
  cursor: pointer;
}

.intel-mini-row span {
  color: var(--text1);
  text-align: left;
}

.intel-mini-row small {
  color: var(--text3);
}

.intel-mini-row.link {
  cursor: pointer;
}

.intel-badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.intel-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  color: var(--text2);
  background: rgba(255, 255, 255, 0.05);
}

.bias-bullish {
  color: var(--green);
}

.bias-bearish {
  color: var(--red);
}
</style>
