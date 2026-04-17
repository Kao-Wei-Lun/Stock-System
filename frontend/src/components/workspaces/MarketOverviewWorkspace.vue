<template>
  <section class="workspace-page overview-page">
    <div class="workspace-hero">
      <div>
        <div class="workspace-kicker">Market Overview</div>
        <h1>盤前先看風險，再挑今天值得追蹤的標的。</h1>
      </div>
      <div class="workspace-hero-meta">
        <div class="hero-stat">
          <span>目前焦點</span>
          <strong>{{ currentTicker }}</strong>
        </div>
        <button class="hero-action" type="button" @click="$emit('open-terminal', currentTicker)">
          前往終端
        </button>
      </div>
    </div>

    <div class="overview-macro">
      <MacroDashboard
        :macro-dashboard="macroDashboard"
        @refresh="$emit('refresh-macro')"
        @create-alert="$emit('create-alert', $event)"
      />
    </div>

    <div class="overview-grid snapshot-grid">
      <div class="overview-card snapshot-summary-card">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">Market Pulse</div>
            <div class="overview-card-title">台股快照</div>
          </div>
          <button class="hero-action ghost" type="button" @click="$emit('refresh-market-snapshot')">
            {{ marketSnapshotLoading ? "更新中..." : "更新快照" }}
          </button>
        </div>
        <div v-if="marketSnapshotError" class="snapshot-empty">{{ marketSnapshotError }}</div>
        <div v-else class="snapshot-summary-grid">
          <div v-for="card in marketBreadthCards" :key="card.key" class="snapshot-stat">
            <div class="snapshot-stat-label">{{ card.label }}</div>
            <strong>{{ formatCount(card.total) }}</strong>
            <div class="snapshot-stat-rows">
              <span class="up">上漲 {{ formatCount(card.advancers) }}</span>
              <span class="dn">下跌 {{ formatCount(card.decliners) }}</span>
              <span>平盤 {{ formatCount(card.unchanged) }}</span>
            </div>
          </div>
        </div>
        <div class="snapshot-active-head">成交額前段</div>
        <div class="snapshot-active-list">
          <button
            v-for="item in marketActiveLeaders.slice(0, 5)"
            :key="item.ticker"
            class="snapshot-active-row"
            type="button"
            @click="$emit('select-ticker', { ticker: item.ticker, name: item.name })"
          >
            <span>{{ item.name || item.ticker }}</span>
            <strong>{{ formatTradeValue(item.trade_value) }}</strong>
          </button>
        </div>
      </div>

      <div class="overview-card movers-card">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">Momentum</div>
            <div class="overview-card-title">盤中強勢股</div>
          </div>
        </div>
        <div class="mover-list">
          <button
            v-for="item in marketStrongMovers"
            :key="item.ticker"
            class="mover-row"
            type="button"
            @click="$emit('select-ticker', { ticker: item.ticker, name: item.name })"
          >
            <span class="mover-main">
              <strong>{{ item.ticker }}</strong>
              <span>{{ item.name }}</span>
            </span>
            <span class="mover-meta up">
              {{ formatPrice(item.price) }} / {{ formatChange(item) }}
            </span>
          </button>
        </div>
      </div>

      <div class="overview-card movers-card">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">Mean Reversion</div>
            <div class="overview-card-title">盤中弱勢股</div>
          </div>
        </div>
        <div class="mover-list">
          <button
            v-for="item in marketWeakMovers"
            :key="item.ticker"
            class="mover-row"
            type="button"
            @click="$emit('select-ticker', { ticker: item.ticker, name: item.name })"
          >
            <span class="mover-main">
              <strong>{{ item.ticker }}</strong>
              <span>{{ item.name }}</span>
            </span>
            <span class="mover-meta dn">
              {{ formatPrice(item.price) }} / {{ formatChange(item) }}
            </span>
          </button>
        </div>
      </div>
    </div>

    <div ref="heatmapSectionRef" class="overview-grid widgets-grid">
      <div class="overview-card widget-card" :class="{ 'is-fullscreen': fullscreenWidget === 'usHeatmap' }">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">TradingView</div>
            <div class="overview-card-title">美股板塊熱力圖</div>
          </div>
          <button class="hero-action ghost" type="button" @click="toggleFullscreen('usHeatmap')">
            {{ fullscreenWidget === 'usHeatmap' ? '還原' : '放大全螢幕' }}
          </button>
        </div>
        <div class="widget-shell heatmap-shell">
          <TradingViewWidgetEmbed
            script-src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js"
            :config="usHeatmapConfig"
            fallback-url="https://www.tradingview.com/heatmap/stock/"
          />
        </div>
      </div>

      <div class="overview-card widget-card" :class="{ 'is-fullscreen': fullscreenWidget === 'twEchartsHeatmap' }">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">Local Data</div>
            <div class="overview-card-title">台股資金熱力圖 (ECharts)</div>
          </div>
          <button class="hero-action ghost" type="button" @click="toggleFullscreen('twEchartsHeatmap')">
            {{ fullscreenWidget === 'twEchartsHeatmap' ? '還原' : '放大全螢幕' }}
          </button>
        </div>
        <div class="widget-shell heatmap-shell">
          <TaiwanHeatmap mode="stocks" @select-ticker="$emit('select-ticker', $event)" />
        </div>
      </div>

      <div class="overview-card widget-card" :class="{ 'is-fullscreen': fullscreenWidget === 'twIndicesHeatmap' }">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">Local Data</div>
            <div class="overview-card-title">大盤指數與 ETF (ECharts)</div>
          </div>
          <button class="hero-action ghost" type="button" @click="toggleFullscreen('twIndicesHeatmap')">
            {{ fullscreenWidget === 'twIndicesHeatmap' ? '還原' : '放大全螢幕' }}
          </button>
        </div>
        <div class="widget-shell heatmap-shell">
          <TaiwanHeatmap mode="indices" @select-ticker="$emit('select-ticker', $event)" />
        </div>
      </div>

      <div class="overview-card widget-card" :class="{ 'is-fullscreen': fullscreenWidget === 'twScreener' }">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">TradingView</div>
            <div class="overview-card-title">台股強勢股篩選</div>
          </div>
          <button class="hero-action ghost" type="button" @click="toggleFullscreen('twScreener')">
            {{ fullscreenWidget === 'twScreener' ? '還原' : '放大全螢幕' }}
          </button>
        </div>
        <div class="widget-shell heatmap-shell">
          <TradingViewWidgetEmbed
            script-src="https://s3.tradingview.com/external-embedding/embed-widget-screener.js"
            :config="twScreenerConfig"
            fallback-url="https://www.tradingview.com/screener/"
          />
        </div>
      </div>

      <div class="overview-card widget-card" :class="{ 'is-fullscreen': fullscreenWidget === 'overview' }">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">TradingView</div>
            <div class="overview-card-title">全球大盤快照</div>
          </div>
          <button class="hero-action ghost" type="button" @click="toggleFullscreen('overview')">
            {{ fullscreenWidget === 'overview' ? '還原' : '放大全螢幕' }}
          </button>
        </div>
        <div class="widget-shell market-overview-shell">
          <TradingViewWidgetEmbed
            script-src="https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js"
            :config="marketOverviewConfig"
            fallback-url="https://www.tradingview.com/markets/"
          />
        </div>
      </div>
    </div>

    <div class="overview-grid">
      <div class="overview-card overview-watch">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">Watchlist</div>
            <div class="overview-card-title">自選觀察池</div>
          </div>
        </div>
        <WatchlistPanel
          :groups="groups"
          :market-items="marketItems"
          :active-group-id="activeGroupId"
          :items="watchlist"
          :left-tab="leftTab"
          :active-ticker="currentTicker"
          :loading="watchlistLoading"
          :error="watchlistError"
          @set-left-tab="$emit('set-left-tab', $event)"
          @select-group="$emit('select-group', $event)"
          @create-group="$emit('create-group', $event)"
          @rename-group="$emit('rename-group', $event)"
          @delete-group="$emit('delete-group', $event)"
          @add-to-watchlist="$emit('add-to-watchlist', $event)"
          @remove-from-watchlist="$emit('remove-from-watchlist', $event)"
          @reorder-items="$emit('reorder-items', $event)"
          @select-ticker="$emit('select-ticker', $event)"
          @open-journal-entry="$emit('open-journal-entry', $event)"
          @open-alert-modal="$emit('open-alert-modal', $event)"
          @create-alerts-batch="$emit('create-alerts-batch', $event)"
        />
      </div>

      <div class="overview-card overview-events">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">Event Center</div>
            <div class="overview-card-title">事件與催化因子</div>
          </div>
          <button class="hero-action ghost" type="button" @click="$emit('refresh-events')">
            重新整理
          </button>
        </div>
        <EventCenter
          :current-ticker="currentTicker"
          :current-name="currentName"
          :calendar-events="calendarEvents"
          :ticker-events="tickerEvents"
          :ticker-news="tickerNews"
          @refresh-events="$emit('refresh-events')"
          @refresh-news="$emit('refresh-news')"
          @open-ticker="$emit('select-ticker', { ticker: $event, name: $event })"
          @create-alert="$emit('create-alert', $event)"
        />
      </div>
    </div>

    <div class="overview-card overview-screener">
      <div class="overview-card-head">
        <div>
          <div class="overview-card-kicker">Screener Workspace</div>
          <div class="overview-card-title">策略掃描結果</div>
        </div>
      </div>
      <ScreenerWorkspace
        :filters="screenerFilters"
        :results="screenerResults"
        :presets="screenerPresets"
        :loading="screenerLoading"
        :current-ticker="currentTicker"
        @update-filter="$emit('update-screener-filter', $event)"
        @run-screen="$emit('run-screener')"
        @save-preset="$emit('save-screener-preset', $event)"
        @load-preset="$emit('load-screener-preset', $event)"
        @delete-preset="$emit('delete-screener-preset', $event)"
        @open-ticker="$emit('select-ticker', { ticker: $event, name: $event })"
        @add-watchlist="$emit('add-to-watchlist', $event)"
        @open-journal-entry="$emit('open-journal-entry', $event)"
        @add-alert="$emit('open-alert-modal', $event)"
      />
    </div>
  </section>
</template>

<script setup>
import { ref } from "vue";

import EventCenter from "../EventCenter.vue";
import MacroDashboard from "../MacroDashboard.vue";
import ScreenerWorkspace from "../ScreenerWorkspace.vue";
import TradingViewWidgetEmbed from "../TradingViewWidgetEmbed.vue";
import WatchlistPanel from "../WatchlistPanel.vue";
import TaiwanHeatmap from "./TaiwanHeatmap.vue";

const heatmapSectionRef = ref(null);
const fullscreenWidget = ref(null);

const baseHeatmapConfig = {
  blockSize: "market_cap_basic",
  blockColor: "change",
  grouping: "sector",
  locale: "zh_TW",
  symbolUrl: "",
  colorTheme: "dark",
  hasTopBar: false,
  isDataSetEnabled: false,
  isZoomEnabled: true,
  hasSymbolTooltip: true,
  isMonoSize: false,
  width: "100%",
  height: "100%",
};

const usHeatmapConfig = {
  ...baseHeatmapConfig,
  dataSource: "SPX500",
};

const twScreenerConfig = {
  width: "100%",
  height: "100%",
  defaultColumn: "overview",
  defaultScreen: "top_gainers",
  market: "taiwan",
  showToolbar: true,
  colorTheme: "dark",
  locale: "zh_TW"
};

const marketOverviewConfig = {
  colorTheme: "dark",
  dateRange: "12M",
  showChart: true,
  locale: "zh_TW",
  largeChartUrl: "",
  isTransparent: true,
  showSymbolLogo: true,
  showFloatingTooltip: false,
  plotLineColorGrowing: "rgba(0, 217, 163, 1)",
  plotLineColorFalling: "rgba(255, 77, 106, 1)",
  gridLineColor: "rgba(255, 255, 255, 0.06)",
  scaleFontColor: "rgba(152, 167, 183, 1)",
  belowLineFillColorGrowing: "rgba(0, 217, 163, 0.16)",
  belowLineFillColorFalling: "rgba(255, 77, 106, 0.16)",
  belowLineFillColorGrowingBottom: "rgba(0, 217, 163, 0)",
  belowLineFillColorFallingBottom: "rgba(255, 77, 106, 0)",
  symbolActiveColor: "rgba(123, 231, 255, 0.16)",
  tabs: [
    {
      title: "美股指數",
      symbols: [
        { s: "FOREXCOM:SPXUSD", d: "S&P 500" },
        { s: "NASDAQ:NDX", d: "NASDAQ 100" },
        { s: "INDEX:DJI", d: "Dow Jones" },
      ],
      originalTitle: "US",
    },
    {
      title: "台灣/亞洲",
      symbols: [
        { s: "TVC:TWII", d: "TWSE" },
        { s: "INDEX:HSI", d: "Hang Seng" },
        { s: "INDEX:NKY", d: "Nikkei 225" },
      ],
      originalTitle: "Asia",
    },
    {
      title: "商品/匯率",
      symbols: [
        { s: "COMEX:GC1!", d: "Gold" },
        { s: "NYMEX:CL1!", d: "WTI Oil" },
        { s: "FX:USDJPY", d: "USD/JPY" },
      ],
      originalTitle: "Macro",
    },
  ],
  width: "100%",
  height: "100%",
};

function focusHeatmap() {
  heatmapSectionRef.value?.scrollIntoView?.({ behavior: "smooth", block: "start" });
}

function toggleFullscreen(widgetId) {
  if (fullscreenWidget.value === widgetId) {
    fullscreenWidget.value = null;
  } else {
    fullscreenWidget.value = widgetId;
  }
}

function formatCount(value) {
  return Number(value || 0).toLocaleString();
}

function formatPrice(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: Number(value) >= 1000 ? 0 : 2,
    maximumFractionDigits: Number(value) >= 1000 ? 0 : 2,
  });
}

function formatChange(item) {
  const changePct = Number(item?.change_pct ?? 0);
  return `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`;
}

function formatTradeValue(value) {
  const numeric = Number(value || 0);
  if (numeric >= 1e8) return `${(numeric / 1e8).toFixed(1)} 億`;
  if (numeric >= 1e4) return `${(numeric / 1e4).toFixed(0)} 萬`;
  return numeric.toLocaleString();
}

defineExpose({
  focusHeatmap,
});

defineProps({
  groups: { type: Array, required: true },
  marketItems: { type: Array, required: true },
  activeGroupId: { type: Number, default: null },
  watchlist: { type: Array, required: true },
  watchlistLoading: { type: Boolean, required: true },
  watchlistError: { type: Boolean, required: true },
  leftTab: { type: String, required: true },
  currentTicker: { type: String, required: true },
  currentName: { type: String, required: true },
  macroDashboard: { type: Object, required: true },
  marketBreadthCards: { type: Array, default: () => [] },
  marketStrongMovers: { type: Array, default: () => [] },
  marketWeakMovers: { type: Array, default: () => [] },
  marketActiveLeaders: { type: Array, default: () => [] },
  marketSnapshotLoading: { type: Boolean, default: false },
  marketSnapshotError: { type: String, default: "" },
  calendarEvents: { type: Array, default: () => [] },
  tickerEvents: { type: Array, default: () => [] },
  tickerNews: { type: Array, default: () => [] },
  screenerFilters: { type: Object, required: true },
  screenerResults: { type: Object, required: true },
  screenerPresets: { type: Array, default: () => [] },
  screenerLoading: { type: Boolean, required: true },
});

defineEmits([
  "open-terminal",
  "refresh-macro",
  "refresh-market-snapshot",
  "refresh-events",
  "refresh-news",
  "create-alert",
  "set-left-tab",
  "select-group",
  "create-group",
  "rename-group",
  "delete-group",
  "add-to-watchlist",
  "remove-from-watchlist",
  "reorder-items",
  "select-ticker",
  "open-journal-entry",
  "open-alert-modal",
  "create-alerts-batch",
  "update-screener-filter",
  "run-screener",
  "save-screener-preset",
  "load-screener-preset",
  "delete-screener-preset",
]);
</script>

<style scoped>
.workspace-page {
  height: 100%;
  overflow: auto;
  padding: 18px;
}

.overview-page {
  background:
    radial-gradient(circle at top left, rgba(123, 231, 255, 0.08), transparent 24%),
    linear-gradient(180deg, rgba(7, 12, 19, 0.98), rgba(8, 13, 21, 0.98));
}

.workspace-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 22px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(6, 20, 30, 0.94), rgba(10, 16, 26, 0.96));
}

.workspace-kicker,
.overview-card-kicker {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text3);
}

.workspace-hero h1 {
  margin-top: 8px;
  font-family: "Syne", sans-serif;
  font-size: 28px;
  line-height: 1.1;
}

.workspace-hero-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hero-stat {
  min-width: 120px;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
}

.hero-stat span {
  display: block;
  font-size: 10px;
  color: var(--text3);
}

.hero-stat strong {
  display: block;
  margin-top: 4px;
  font-size: 16px;
  color: var(--text1);
}

.hero-action {
  padding: 10px 14px;
  border: 1px solid rgba(123, 231, 255, 0.22);
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.12);
  color: #d7fbff;
  cursor: pointer;
  font-size: 11px;
}

.hero-action.ghost {
  border-color: rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
}

.overview-macro {
  margin-top: 18px;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.92fr) minmax(0, 1.08fr);
  gap: 18px;
  margin-top: 18px;
  align-items: start;
}

.snapshot-grid {
  grid-template-columns: minmax(340px, 1.2fr) minmax(280px, 0.9fr) minmax(280px, 0.9fr);
}

.overview-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  background: rgba(6, 10, 18, 0.68);
  overflow: hidden;
}

.widgets-grid {
  margin-top: 18px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.widgets-grid > .widget-card:nth-child(5) {
  grid-column: span 2;
}

.widget-card {
  min-height: 480px;
}

.widget-card.is-fullscreen {
  position: fixed;
  inset: 18px;
  z-index: 9999;
  min-height: unset;
  display: flex;
  flex-direction: column;
  background: rgba(8, 12, 18, 0.98);
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.6);
}

.widget-card.is-fullscreen .widget-shell {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.snapshot-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  padding: 0 18px 12px;
}

.snapshot-stat {
  padding: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
}

.snapshot-stat-label {
  font-size: 11px;
  color: var(--text3);
}

.snapshot-stat strong {
  display: block;
  margin-top: 8px;
  font-size: 22px;
  line-height: 1;
}

.snapshot-stat-rows {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
  font-size: 11px;
  color: var(--text2);
}

.snapshot-stat-rows .up,
.mover-meta.up {
  color: var(--green);
}

.snapshot-stat-rows .dn,
.mover-meta.dn {
  color: var(--red);
}

.snapshot-active-head {
  padding: 0 18px;
  font-size: 11px;
  color: var(--text3);
}

.snapshot-active-list,
.mover-list {
  display: grid;
  gap: 8px;
  padding: 12px 18px 18px;
}

.snapshot-active-row,
.mover-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text1);
  cursor: pointer;
  text-align: left;
}

.snapshot-active-row strong {
  color: var(--text2);
}

.mover-main {
  display: grid;
  gap: 4px;
}

.mover-main strong {
  font-size: 12px;
}

.mover-main span {
  color: var(--text3);
  font-size: 11px;
}

.mover-meta {
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.snapshot-empty {
  padding: 0 18px 18px;
  color: #ff8a9d;
  font-size: 12px;
}

.widget-shell {
  min-height: 360px;
  padding: 0 18px 18px;
}

.heatmap-shell :deep(.tv-widget-shell),
.market-overview-shell :deep(.tv-widget-shell),
.heatmap-shell :deep(.tv-widget-frame),
.market-overview-shell :deep(.tv-widget-frame) {
  min-height: 100%;
  height: 100%;
}

.overview-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px 10px;
}

.overview-card-title {
  margin-top: 4px;
  font-family: "Syne", sans-serif;
  font-size: 17px;
  font-weight: 700;
}

.overview-watch,
.overview-events {
  min-height: 640px;
}

.overview-watch :deep(.left-panel) {
  width: 100%;
  min-width: 0;
  height: 100%;
  border-right: 0;
  background: transparent;
}

.overview-events :deep(.intel-shell) {
  height: 100%;
  min-height: 0;
  border-radius: 0;
  border: 0;
  background: transparent;
}

.overview-screener {
  margin-top: 18px;
}

.overview-screener :deep(.screen-shell) {
  border: 0;
  border-radius: 0;
  background: transparent;
}

@media (max-width: 1280px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .widgets-grid {
    grid-template-columns: 1fr;
  }

  .widgets-grid > .widget-card:nth-child(3) {
    grid-column: span 1;
  }

  .overview-watch,
  .overview-events {
    min-height: 0;
  }
}

@media (max-width: 720px) {
  .workspace-page {
    padding: 12px;
  }

  .workspace-hero {
    flex-direction: column;
    align-items: stretch;
  }

  .workspace-hero h1 {
    font-size: 24px;
  }

  .workspace-hero-meta {
    flex-wrap: wrap;
  }
}
</style>
