<template>
  <div class="asset-overview">
    <div v-if="hasWarnings" class="asset-warning-stack">
      <button
        v-for="warning in assetWarnings"
        :key="warning"
        class="asset-warning-card asset-warning-action"
        type="button"
        @click="$emit('open-tab', 'maintenance')"
      >
        {{ warning }}
      </button>
      <button
        v-for="gap in assetQuoteGaps"
        :key="`${gap.account_id}-${gap.ticker}`"
        class="asset-warning-card asset-warning-action"
        type="button"
        @click="$emit('open-tab', 'maintenance')"
      >
        {{ gap.ticker }} 暫時抓不到最新報價，目前未納入估值；可到資料維護補手動價格覆蓋。
      </button>
      <button
        v-for="item in reconciliationGapItems"
        :key="`reco-${item.account_id}-${item.snapshot_id}`"
        class="asset-warning-card asset-warning-action"
        type="button"
        @click="$emit('open-tab', 'maintenance')"
      >
        {{ item.account_name }} 對帳差異 {{ formatSignedCurrency(item.total_difference, assetBaseCurrency) }}
      </button>
      <button
        v-for="alert in assetAlerts"
        :key="`${alert.code}-${alert.title}`"
        class="asset-warning-card asset-warning-action"
        :class="alert.level === 'info' ? 'info' : 'warning'"
        type="button"
        @click="$emit('open-tab', 'maintenance')"
      >
        <strong>{{ alert.title }}</strong>
        <span>{{ alert.message }}</span>
      </button>
    </div>

    <div class="asset-range-row">
      <button
        v-for="item in performanceRangeOptions"
        :key="item.value"
        class="asset-range-btn"
        :class="{ active: assetPerformanceRange === item.value }"
        type="button"
        @click="$emit('set-asset-performance-range', item.value)"
      >
        {{ item.label }}
      </button>
    </div>

    <div class="asset-summary-grid">
      <button
        v-for="card in summaryCards"
        :key="card.key"
        class="asset-summary-card asset-summary-action"
        :class="{ active: activeChartMode === card.chartMode }"
        type="button"
        @click="setActiveChartMode(card.chartMode)"
      >
        <span>{{ card.label }}</span>
        <strong :class="card.tone">{{ card.value }}</strong>
        <small>{{ card.helper }}</small>
      </button>
    </div>

    <section class="asset-card asset-card-wide">
      <div class="asset-card-head">
        <div>
          <div class="asset-card-title">資產曲線</div>
          <div class="bt-trade-sub">
            {{ assetPerformanceSeries.length }} 個觀察點 · 目前聚焦 {{ selectedSnapshotLabel }}
          </div>
        </div>
        <div class="asset-chart-mode-row">
          <button
            v-for="mode in performanceModeOptions"
            :key="mode.value"
            class="asset-inline-btn"
            :class="{ active: activeChartMode === mode.value }"
            type="button"
            @click="setActiveChartMode(mode.value)"
          >
            {{ mode.label }}
          </button>
        </div>
      </div>

      <div v-if="performanceChartReady" class="asset-performance-grid asset-performance-grid-chart">
        <div class="asset-curve-card asset-curve-card-chart">
          <div class="asset-curve-metrics">
            <div class="asset-mini-block">
              <span>區間起點</span>
              <strong>{{ formatCurrency(assetPerformanceSummary.start_value_base) }}</strong>
            </div>
            <div class="asset-mini-block">
              <span>期間淨流入</span>
              <strong>{{ formatSignedCurrency(selectedPoint.net_flow_base, assetBaseCurrency) }}</strong>
            </div>
            <div class="asset-mini-block">
              <span>聚焦日期</span>
              <strong>{{ selectedSnapshotLabel }}</strong>
            </div>
          </div>
          <v-chart
            class="asset-chart asset-chart-performance"
            :option="performanceChartOption"
            autoresize
            @click="handlePerformanceChartClick"
          />
        </div>

        <div class="asset-side-analytics asset-side-analytics-chart">
          <div class="asset-mini-block">
            <span>選定資產值</span>
            <strong>{{ formatCurrency(selectedPoint.total_asset_value_base) }}</strong>
          </div>
          <div class="asset-mini-block">
            <span>選定現金</span>
            <strong>{{ formatCurrency(selectedPoint.cash_total_base) }}</strong>
          </div>
          <div class="asset-mini-block">
            <span>選定持倉市值</span>
            <strong>{{ formatCurrency(selectedPoint.market_value_total_base) }}</strong>
          </div>
          <div class="asset-mini-block">
            <span>選定真實績效</span>
            <strong :class="Number(selectedPoint.true_performance_base || 0) >= 0 ? 'up' : 'dn'">
              {{ formatSignedCurrency(selectedPoint.true_performance_base, assetBaseCurrency) }}
            </strong>
          </div>
          <div class="asset-mini-block">
            <span>高水位</span>
            <strong>{{ formatCurrency(assetPerformanceSummary.high_water_mark_base) }}</strong>
          </div>
          <div class="asset-mini-block">
            <span>最大回撤</span>
            <strong :class="Number(assetPerformanceSummary.max_drawdown_pct || 0) >= 0 ? 'neutral' : 'dn'">
              {{ formatPercent(assetPerformanceSummary.max_drawdown_pct) }}
            </strong>
          </div>
        </div>
      </div>
      <div v-else class="bt-history-empty">目前沒有足夠的歷史快照可繪製資產曲線。</div>
    </section>

    <div class="asset-overview-secondary-grid">
      <section class="asset-card">
        <div class="asset-card-head">
          <div>
            <div class="asset-card-title">變化拆解</div>
            <div class="bt-trade-sub">以區間起點、淨流入與真實績效拆開資產變化</div>
          </div>
          <div class="asset-list-metrics">
            <span>{{ formatCurrency(selectedPoint.total_asset_value_base) }}</span>
            <small>期末資產</small>
          </div>
        </div>
        <div v-if="waterfallChartReady" class="asset-chart-shell">
          <v-chart class="asset-chart asset-chart-waterfall" :option="waterfallChartOption" autoresize />
        </div>
        <div v-else class="bt-history-empty">缺少起訖點資料，暫時無法拆解資產變化。</div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div>
            <div class="asset-card-title">月度熱力圖</div>
            <div class="bt-trade-sub">點擊月份可直接帶著篩選進入持倉與流水</div>
          </div>
          <div class="asset-list-metrics">
            <span>{{ selectedMonthLabel }}</span>
            <small>目前月份焦點</small>
          </div>
        </div>
        <div v-if="monthlyHeatmapReady" class="asset-chart-shell">
          <v-chart
            class="asset-chart asset-chart-heatmap"
            :option="monthlyHeatmapOption"
            autoresize
            @click="handleHeatmapClick"
          />
        </div>
        <div v-else class="bt-history-empty">目前沒有足夠的月度績效資料。</div>
      </section>
    </div>

    <div class="asset-analytics-grid">
      <section class="asset-card">
        <div class="asset-card-head">
          <div>
            <div class="asset-card-title">帳戶配置</div>
            <div class="bt-trade-sub">點擊任一帳戶可直接查看該帳戶持倉與流水</div>
          </div>
          <div class="asset-list-metrics">
            <span>{{ assetAccountAllocation.length }}</span>
            <small>帳戶</small>
          </div>
        </div>
        <div v-if="assetAccountAllocation.length" class="asset-donut-card">
          <v-chart
            class="asset-chart asset-chart-donut"
            :option="accountAllocationChartOption"
            autoresize
            @click="handleAccountAllocationClick"
          />
          <div class="asset-donut-legend">
            <button
              v-for="item in assetAccountAllocation.slice(0, 5)"
              :key="item.key"
              class="asset-donut-legend-item"
              type="button"
              @click="focusHoldings({ accountKey: item.key })"
            >
              <span class="asset-dot" :style="{ backgroundColor: paletteColorFor(assetAccountAllocation, item.key) }"></span>
              <strong>{{ item.key }}</strong>
              <small>{{ formatPercent(item.weight_pct) }}</small>
            </button>
          </div>
        </div>
        <div v-else class="bt-history-empty">尚無配置資料。</div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div>
            <div class="asset-card-title">市場配置</div>
            <div class="bt-trade-sub">點擊市場分布後，持倉頁只看對應市場</div>
          </div>
          <div class="asset-list-metrics">
            <span>{{ assetMarketAllocation.length }}</span>
            <small>市場</small>
          </div>
        </div>
        <div v-if="assetMarketAllocation.length" class="asset-donut-card">
          <v-chart
            class="asset-chart asset-chart-donut"
            :option="marketAllocationChartOption"
            autoresize
            @click="handleMarketAllocationClick"
          />
          <div class="asset-donut-legend">
            <button
              v-for="item in assetMarketAllocation"
              :key="item.key"
              class="asset-donut-legend-item"
              type="button"
              @click="focusHoldings({ marketKey: item.key })"
            >
              <span class="asset-dot" :style="{ backgroundColor: paletteColorFor(assetMarketAllocation, item.key) }"></span>
              <strong>{{ item.key }}</strong>
              <small>{{ formatPercent(item.weight_pct) }}</small>
            </button>
          </div>
        </div>
        <div v-else class="bt-history-empty">目前沒有持股市值。</div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div>
            <div class="asset-card-title">損益貢獻</div>
            <div class="bt-trade-sub">點擊標的可直接切到該標的的持倉與流水</div>
          </div>
          <div class="asset-list-metrics">
            <span>{{ contributorRows.length }}</span>
            <small>標的</small>
          </div>
        </div>
        <div v-if="contributorRows.length" class="asset-chart-shell">
          <v-chart
            class="asset-chart asset-chart-contributors"
            :option="contributorChartOption"
            autoresize
            @click="handleContributorClick"
          />
        </div>
        <div v-else class="bt-history-empty">尚無損益貢獻資料。</div>
      </section>
    </div>

    <div class="asset-preview-grid">
      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">持倉預覽</div>
          <button class="asset-inline-btn" type="button" @click="$emit('open-tab', 'holdings')">查看全部</button>
        </div>
        <div v-if="assetHoldings.length" class="asset-list">
          <button
            v-for="holding in assetHoldings.slice(0, 5)"
            :key="`${holding.account_id}-${holding.ticker}`"
            class="asset-list-item"
            type="button"
            @click="focusHoldings({ ticker: holding.ticker })"
          >
            <div>
              <strong>{{ holding.ticker }}</strong>
              <div class="bt-trade-sub">{{ holding.account_name }}</div>
            </div>
            <div class="asset-list-metrics">
              <span>{{ formatCurrency(holding.market_value_base) }}</span>
              <small :class="Number(holding.unrealized_pnl_base || 0) >= 0 ? 'up' : 'dn'">
                {{ formatSignedCurrency(holding.unrealized_pnl_base, assetBaseCurrency) }}
              </small>
            </div>
          </button>
        </div>
        <div v-else class="bt-history-empty">尚無持倉。</div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">最近流水</div>
          <button class="asset-inline-btn" type="button" @click="$emit('open-tab', 'holdings')">查看明細</button>
        </div>
        <div v-if="recentFlowItems.length" class="asset-list">
          <button
            v-for="item in recentFlowItems"
            :key="item.key"
            class="asset-list-item"
            type="button"
            @click="focusHoldings(item.filter)"
          >
            <div>
              <strong>{{ item.title }}</strong>
              <div class="bt-trade-sub">{{ item.meta }}</div>
            </div>
            <div class="asset-list-metrics">
              <span>{{ item.value }}</span>
              <small>{{ item.kind }}</small>
            </div>
          </button>
        </div>
        <div v-else class="bt-history-empty">目前沒有最近流水。</div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, provide, ref, watch } from "vue";
import { use, graphic } from "echarts/core";
import { BarChart, HeatmapChart, LineChart, PieChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart, { THEME_KEY } from "vue-echarts";

use([
  BarChart,
  HeatmapChart,
  LineChart,
  PieChart,
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
]);

provide(THEME_KEY, "dark");

const props = defineProps({
  assetPerformanceRange: { type: String, default: "1y" },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetWarnings: { type: Array, default: () => [] },
  assetQuoteGaps: { type: Array, default: () => [] },
  assetReconciliation: { type: Object, default: () => ({ items: [], summary: {} }) },
  assetPerformanceSummary: { type: Object, default: () => ({}) },
  assetPerformanceSeries: { type: Array, default: () => [] },
  assetMonthlyHeatmap: { type: Array, default: () => [] },
  assetAlerts: { type: Array, default: () => [] },
  assetAccountAllocation: { type: Array, default: () => [] },
  assetMarketAllocation: { type: Array, default: () => [] },
  assetContributors: { type: Object, default: () => ({ top_gainers: [], top_losers: [] }) },
  assetHoldings: { type: Array, default: () => [] },
  assetCashEntries: { type: Array, default: () => [] },
  assetTradeEntries: { type: Array, default: () => [] },
});

const emit = defineEmits([
  "set-asset-performance-range",
  "open-tab",
  "focus-holdings",
]);

const performanceRangeOptions = [
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "180d", label: "180D" },
  { value: "1y", label: "1Y" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "All" },
];

const performanceModeOptions = [
  { value: "total_asset_value_base", label: "總資產", color: "#7be7ff" },
  { value: "true_performance_base", label: "純績效", color: "#6ef0a7" },
  { value: "cash_total_base", label: "現金", color: "#ffcf78" },
  { value: "market_value_total_base", label: "持倉市值", color: "#ff7f9d" },
];

const palette = ["#7be7ff", "#6ef0a7", "#ffcf78", "#ff7f9d", "#8d92ff", "#73b8ff", "#9ef7d6"];

const activeChartMode = ref("total_asset_value_base");
const selectedDate = ref("");
const selectedMonth = ref("");

const hasWarnings = computed(() => (
  props.assetWarnings.length
  || props.assetQuoteGaps.length
  || props.assetAlerts.length
  || reconciliationGapItems.value.length
));

const reconciliationItems = computed(() => props.assetReconciliation?.items || []);
const reconciliationGapItems = computed(() => reconciliationItems.value.filter((item) => item?.has_gap));

const performanceRows = computed(() => (
  (props.assetPerformanceSeries || [])
    .map((item) => ({
      date: String(item?.date || ""),
      cash_total_base: Number(item?.cash_total_base || 0),
      market_value_total_base: Number(item?.market_value_total_base || 0),
      total_asset_value_base: Number(item?.total_asset_value_base || 0),
      true_performance_base: Number(item?.true_performance_base || 0),
      net_flow_base: Number(item?.net_flow_base || 0),
      realized_total_base: Number(item?.realized_total_base || 0),
      unrealized_total_base: Number(item?.unrealized_total_base || 0),
      drawdown_pct: Number(item?.drawdown_pct || 0),
      quote_gap_count: Number(item?.quote_gap_count || 0),
    }))
    .filter((item) => item.date)
));

watch(
  performanceRows,
  (rows) => {
    const lastRow = rows.at(-1);
    if (!rows.length) {
      selectedDate.value = "";
      return;
    }
    if (!rows.some((item) => item.date === selectedDate.value)) {
      selectedDate.value = lastRow?.date || "";
    }
  },
  { immediate: true },
);

watch(
  () => props.assetMonthlyHeatmap,
  (rows) => {
    const lastMonth = Array.isArray(rows) ? rows.at(-1)?.month : "";
    if (lastMonth && !rows.some((item) => item.month === selectedMonth.value)) {
      selectedMonth.value = lastMonth;
    }
  },
  { immediate: true },
);

const selectedPoint = computed(() => (
  performanceRows.value.find((item) => item.date === selectedDate.value)
  || performanceRows.value.at(-1)
  || {
    date: "",
    cash_total_base: 0,
    market_value_total_base: 0,
    total_asset_value_base: 0,
    true_performance_base: 0,
    net_flow_base: 0,
    realized_total_base: 0,
    unrealized_total_base: 0,
    drawdown_pct: 0,
    quote_gap_count: 0,
  }
));

const selectedSnapshotLabel = computed(() => formatDateLabel(selectedPoint.value.date));
const selectedMonthLabel = computed(() => formatMonthLabel(selectedMonth.value));

const performanceChartReady = computed(() => performanceRows.value.length >= 2);
const waterfallChartReady = computed(() => performanceRows.value.length >= 1);
const monthlyHeatmapReady = computed(() => (props.assetMonthlyHeatmap || []).length > 0);

const summaryCards = computed(() => [
  {
    key: "total",
    label: "總資產現值",
    value: formatCurrency(selectedPoint.value.total_asset_value_base),
    helper: `${selectedSnapshotLabel.value} 快照`,
    tone: "neutral",
    chartMode: "total_asset_value_base",
  },
  {
    key: "true",
    label: "區間真實績效",
    value: formatSignedCurrency(props.assetPerformanceSummary.true_performance_base, props.assetBaseCurrency),
    helper: formatPercent(props.assetPerformanceSummary.true_return_pct),
    tone: Number(props.assetPerformanceSummary.true_performance_base || 0) >= 0 ? "up" : "dn",
    chartMode: "true_performance_base",
  },
  {
    key: "cash",
    label: "現金總額",
    value: formatCurrency(selectedPoint.value.cash_total_base),
    helper: "點我改看現金曲線",
    tone: "neutral",
    chartMode: "cash_total_base",
  },
  {
    key: "market",
    label: "持倉市值",
    value: formatCurrency(selectedPoint.value.market_value_total_base),
    helper: "點我改看持倉曲線",
    tone: "neutral",
    chartMode: "market_value_total_base",
  },
  {
    key: "unrealized",
    label: "未實現損益",
    value: formatSignedCurrency(props.assetSummary.unrealized_total_base, props.assetBaseCurrency),
    helper: formatPercent(percentAgainstAsset(props.assetSummary.unrealized_total_base, props.assetSummary.total_asset_value_base)),
    tone: Number(props.assetSummary.unrealized_total_base || 0) >= 0 ? "up" : "dn",
    chartMode: "market_value_total_base",
  },
  {
    key: "realized",
    label: "已實現損益",
    value: formatSignedCurrency(props.assetSummary.realized_total_base, props.assetBaseCurrency),
    helper: formatSignedCurrency(props.assetPerformanceSummary.realized_end_base, props.assetBaseCurrency),
    tone: Number(props.assetSummary.realized_total_base || 0) >= 0 ? "up" : "dn",
    chartMode: "true_performance_base",
  },
  {
    key: "drawdown",
    label: "最大回撤",
    value: formatPercent(props.assetPerformanceSummary.max_drawdown_pct),
    helper: `${selectedPoint.value.quote_gap_count || 0} 個估值缺口`,
    tone: Number(props.assetPerformanceSummary.max_drawdown_pct || 0) >= 0 ? "neutral" : "dn",
    chartMode: "total_asset_value_base",
  },
  {
    key: "net-flow",
    label: "期間淨流入",
    value: formatSignedCurrency(selectedPoint.value.net_flow_base, props.assetBaseCurrency),
    helper: `${props.assetPerformanceSummary.point_count || performanceRows.value.length || 0} 個觀察點`,
    tone: Number(selectedPoint.value.net_flow_base || 0) >= 0 ? "up" : "dn",
    chartMode: "total_asset_value_base",
  },
]);

const contributorRows = computed(() => {
  const source = [
    ...(props.assetContributors?.top_gainers || []),
    ...(props.assetContributors?.top_losers || []),
  ];
  const deduped = [];
  const seen = new Set();
  source.forEach((item) => {
    if (!item?.ticker || seen.has(item.ticker)) return;
    seen.add(item.ticker);
    deduped.push(item);
  });
  return deduped
    .map((item) => ({
      ticker: item.ticker,
      account_name: item.account_name || "",
      value: Number(item.unrealized_pnl_base || 0),
    }))
    .sort((left, right) => right.value - left.value);
});

const recentFlowItems = computed(() => {
  const trades = (props.assetTradeEntries || []).map((entry) => ({
    key: `trade-${entry.id}`,
    title: `${entry.ticker} · ${tradeSideLabel(entry.side)}`,
    meta: `${entry.account_name || entry.account_id || "帳戶"} · ${formatDateLabel(entry.trade_date, true)}`,
    value: `${formatNumber(entry.quantity, 4)} @ ${formatNumber(entry.price, 2)}`,
    kind: "交易",
    timestamp: new Date(entry.trade_date || 0).getTime(),
    filter: {
      accountKey: entry.account_name || "",
      marketKey: entry.market || "",
      ticker: entry.ticker || "",
      month: extractMonth(entry.trade_date),
    },
  }));
  const cash = (props.assetCashEntries || []).map((entry) => ({
    key: `cash-${entry.id}`,
    title: flowTypeLabel(entry.flow_type),
    meta: `${entry.account_name || entry.account_id || "帳戶"} · ${formatDateLabel(entry.flow_date, true)}`,
    value: formatSignedCurrency(entry.amount, entry.currency, entry.flow_type),
    kind: "現金",
    timestamp: new Date(entry.flow_date || 0).getTime(),
    filter: {
      accountKey: entry.account_name || "",
      month: extractMonth(entry.flow_date),
    },
  }));
  return [...trades, ...cash]
    .sort((left, right) => right.timestamp - left.timestamp)
    .slice(0, 5);
});

const performanceChartOption = computed(() => {
  const metric = performanceModeOptions.find((item) => item.value === activeChartMode.value) || performanceModeOptions[0];
  const selectedIndex = performanceRows.value.findIndex((item) => item.date === selectedPoint.value.date);
  return {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", snap: true },
      backgroundColor: "rgba(8, 14, 22, 0.94)",
      borderColor: "rgba(123, 231, 255, 0.18)",
      textStyle: { color: "#e7f3ff" },
      formatter(params) {
        const raw = params?.[0]?.data?.raw;
        if (!raw) return "";
        return [
          `<div class="asset-tooltip-title">${formatDateLabel(raw.date, true)}</div>`,
          `<div>總資產：${formatCurrency(raw.total_asset_value_base)}</div>`,
          `<div>現金：${formatCurrency(raw.cash_total_base)}</div>`,
          `<div>持倉市值：${formatCurrency(raw.market_value_total_base)}</div>`,
          `<div>純績效：${formatSignedCurrency(raw.true_performance_base, props.assetBaseCurrency)}</div>`,
          `<div>淨流入：${formatSignedCurrency(raw.net_flow_base, props.assetBaseCurrency)}</div>`,
        ].join("");
      },
    },
    grid: { top: 28, right: 20, bottom: 44, left: 54 },
    dataZoom: [
      {
        type: "inside",
        filterMode: "none",
      },
    ],
    xAxis: {
      type: "category",
      data: performanceRows.value.map((item) => formatShortDate(item.date)),
      boundaryGap: false,
      axisLine: { lineStyle: { color: "rgba(255, 255, 255, 0.12)" } },
      axisLabel: { color: "rgba(219, 229, 240, 0.66)" },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisLabel: {
        color: "rgba(219, 229, 240, 0.66)",
        formatter: (value) => formatCompactNumber(value),
      },
      splitLine: { lineStyle: { color: "rgba(255, 255, 255, 0.07)" } },
    },
    series: [
      {
        type: "line",
        name: metric.label,
        smooth: 0.2,
        symbol: "circle",
        symbolSize: 7,
        lineStyle: {
          width: 3,
          color: metric.color,
        },
        itemStyle: {
          color: metric.color,
          borderColor: "#07111b",
          borderWidth: 2,
        },
        areaStyle: {
          color: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: `${metric.color}88` },
            { offset: 1, color: "rgba(7, 17, 27, 0.02)" },
          ]),
        },
        markPoint: selectedIndex >= 0
          ? {
            symbol: "circle",
            symbolSize: 14,
            label: { show: false },
            itemStyle: {
              color: metric.color,
              borderColor: "#f5fbff",
              borderWidth: 2,
            },
            data: [
              {
                coord: [
                  selectedIndex,
                  Number(selectedPoint.value[activeChartMode.value] || 0),
                ],
              },
            ],
          }
          : undefined,
        data: performanceRows.value.map((item) => ({
          value: Number(item[activeChartMode.value] || 0),
          raw: item,
        })),
      },
    ],
  };
});

const waterfallChartOption = computed(() => {
  const endValue = Number(selectedPoint.value.total_asset_value_base || 0);
  const startValue = Number(props.assetPerformanceSummary.start_value_base || 0);
  const netFlow = Number(selectedPoint.value.net_flow_base || 0);
  const performance = Number(selectedPoint.value.true_performance_base || 0);
  const steps = buildWaterfallSteps(startValue, netFlow, performance, endValue);
  return {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "rgba(8, 14, 22, 0.94)",
      borderColor: "rgba(123, 231, 255, 0.18)",
      textStyle: { color: "#e7f3ff" },
      formatter(params) {
        const point = params?.[1]?.data;
        if (!point) return "";
        return `<div class="asset-tooltip-title">${point.label}</div><div>${point.signedLabel}</div>`;
      },
    },
    grid: { top: 18, right: 12, bottom: 22, left: 16, containLabel: true },
    xAxis: {
      type: "category",
      data: steps.map((item) => item.label),
      axisLine: { lineStyle: { color: "rgba(255, 255, 255, 0.12)" } },
      axisLabel: { color: "rgba(219, 229, 240, 0.72)" },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      axisLabel: {
        color: "rgba(219, 229, 240, 0.66)",
        formatter: (value) => formatCompactNumber(value),
      },
      splitLine: { lineStyle: { color: "rgba(255, 255, 255, 0.07)" } },
    },
    series: [
      {
        type: "bar",
        stack: "asset-waterfall",
        itemStyle: { color: "transparent" },
        emphasis: { disabled: true },
        data: steps.map((item) => item.base),
      },
      {
        type: "bar",
        stack: "asset-waterfall",
        barWidth: 34,
        label: {
          show: true,
          position: "top",
          color: "#dfeaf4",
          formatter: ({ data }) => data.shortLabel,
        },
        data: steps.map((item) => ({
          value: item.value,
          label: item.label,
          signedLabel: item.signedLabel,
          shortLabel: item.shortLabel,
          itemStyle: { color: item.color },
        })),
      },
    ],
  };
});

const monthlyHeatmapOption = computed(() => {
  const monthNames = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];
  const years = Array.from(new Set((props.assetMonthlyHeatmap || []).map((item) => String(item.month || "").slice(0, 4))))
    .filter(Boolean)
    .sort();
  return {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      position: "top",
      backgroundColor: "rgba(8, 14, 22, 0.94)",
      borderColor: "rgba(123, 231, 255, 0.18)",
      textStyle: { color: "#e7f3ff" },
      formatter(params) {
        const [, , pct, month, performance] = params?.data || [];
        return [
          `<div class="asset-tooltip-title">${formatMonthLabel(month)}</div>`,
          `<div>真實報酬：${formatPercent(pct)}</div>`,
          `<div>績效金額：${formatSignedCurrency(performance, props.assetBaseCurrency)}</div>`,
        ].join("");
      },
    },
    grid: { top: 12, right: 12, bottom: 52, left: 42 },
    xAxis: {
      type: "category",
      data: monthNames,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: "rgba(255, 255, 255, 0.12)" } },
      axisLabel: { color: "rgba(219, 229, 240, 0.68)" },
    },
    yAxis: {
      type: "category",
      data: years,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: "rgba(255, 255, 255, 0.12)" } },
      axisLabel: { color: "rgba(219, 229, 240, 0.68)" },
    },
    visualMap: {
      min: -20,
      max: 20,
      calculable: false,
      orient: "horizontal",
      left: "center",
      bottom: 6,
      textStyle: { color: "rgba(219, 229, 240, 0.66)" },
      inRange: {
        color: ["#ff5f7e", "#292f3f", "#6ef0a7"],
      },
    },
    series: [
      {
        type: "heatmap",
        data: (props.assetMonthlyHeatmap || []).map((item) => {
          const monthLabel = String(item.month || "");
          const monthIndex = Number(monthLabel.slice(5, 7)) - 1;
          const yearIndex = years.indexOf(monthLabel.slice(0, 4));
          return [
            monthIndex,
            yearIndex,
            Number(item.return_pct || 0),
            monthLabel,
            Number(item.true_performance_base || 0),
          ];
        }),
        label: {
          show: true,
          color: "#f5fbff",
          formatter: ({ data }) => `${Number(data?.[2] || 0).toFixed(1)}%`,
        },
        itemStyle: {
          borderColor: "rgba(7, 17, 27, 0.92)",
          borderWidth: 2,
        },
        emphasis: {
          itemStyle: {
            borderColor: "#f5fbff",
            borderWidth: 2,
          },
        },
      },
    ],
  };
});

const accountAllocationChartOption = computed(() => buildDonutChartOption(
  props.assetAccountAllocation,
  "帳戶",
  "點擊扇區查看帳戶明細",
));

const marketAllocationChartOption = computed(() => buildDonutChartOption(
  props.assetMarketAllocation,
  "市場",
  "點擊扇區查看市場明細",
));

const contributorChartOption = computed(() => ({
  animation: false,
  backgroundColor: "transparent",
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "shadow" },
    backgroundColor: "rgba(8, 14, 22, 0.94)",
    borderColor: "rgba(123, 231, 255, 0.18)",
    textStyle: { color: "#e7f3ff" },
    formatter(params) {
      const point = params?.[0]?.data || {};
      return `<div class="asset-tooltip-title">${point.ticker || ""}</div><div>${formatSignedCurrency(point.value, props.assetBaseCurrency)}</div>`;
    },
  },
  grid: { top: 10, right: 12, bottom: 12, left: 54, containLabel: true },
  xAxis: {
    type: "value",
    axisLabel: {
      color: "rgba(219, 229, 240, 0.66)",
      formatter: (value) => formatCompactNumber(value),
    },
    splitLine: { lineStyle: { color: "rgba(255, 255, 255, 0.07)" } },
  },
  yAxis: {
    type: "category",
    inverse: true,
    axisLine: { show: false },
    axisLabel: { color: "rgba(219, 229, 240, 0.72)" },
    data: contributorRows.value.map((item) => item.ticker),
  },
  series: [
    {
      type: "bar",
      barWidth: 18,
      data: contributorRows.value.map((item) => ({
        value: item.value,
        ticker: item.ticker,
        itemStyle: {
          color: item.value >= 0 ? "#6ef0a7" : "#ff7f9d",
        },
      })),
      label: {
        show: true,
        position: "right",
        color: "#dfeaf4",
        formatter: ({ data }) => formatSignedCurrency(data?.value, props.assetBaseCurrency),
      },
    },
  ],
}));

function setActiveChartMode(mode) {
  activeChartMode.value = mode;
}

function focusHoldings(filter = {}) {
  emit("focus-holdings", {
    accountKey: filter.accountKey || "",
    marketKey: filter.marketKey || "",
    ticker: filter.ticker || "",
    month: filter.month || "",
  });
}

function handlePerformanceChartClick(params) {
  const raw = params?.data?.raw;
  if (!raw?.date) return;
  selectedDate.value = raw.date;
  selectedMonth.value = extractMonth(raw.date);
}

function handleHeatmapClick(params) {
  const month = params?.data?.[3];
  if (!month) return;
  selectedMonth.value = month;
  focusHoldings({ month });
}

function handleAccountAllocationClick(params) {
  const accountKey = params?.data?.name;
  if (!accountKey) return;
  focusHoldings({ accountKey });
}

function handleMarketAllocationClick(params) {
  const marketKey = params?.data?.name;
  if (!marketKey) return;
  focusHoldings({ marketKey });
}

function handleContributorClick(params) {
  const ticker = params?.data?.ticker;
  if (!ticker) return;
  focusHoldings({ ticker });
}

function buildDonutChartOption(items, title, subtitle) {
  return {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(8, 14, 22, 0.94)",
      borderColor: "rgba(123, 231, 255, 0.18)",
      textStyle: { color: "#e7f3ff" },
      formatter(params) {
        const pct = Number(params?.data?.weight_pct || 0);
        return [
          `<div class="asset-tooltip-title">${params?.data?.name || ""}</div>`,
          `<div>資產：${formatCurrency(params?.data?.value)}</div>`,
          `<div>占比：${pct.toFixed(2)}%</div>`,
        ].join("");
      },
    },
    series: [
      {
        type: "pie",
        radius: ["56%", "80%"],
        center: ["50%", "48%"],
        avoidLabelOverlap: true,
        itemStyle: {
          borderColor: "#07111b",
          borderWidth: 3,
        },
        label: { show: false },
        emphasis: { scale: true, scaleSize: 10 },
        data: items.map((item, index) => ({
          name: item.key,
          value: Number(item.value_base || 0),
          weight_pct: Number(item.weight_pct || 0),
          itemStyle: { color: palette[index % palette.length] },
        })),
      },
    ],
    graphic: [
      {
        type: "text",
        left: "center",
        top: "36%",
        style: {
          text: title,
          fill: "rgba(219, 229, 240, 0.72)",
          fontSize: 12,
          fontWeight: 600,
        },
      },
      {
        type: "text",
        left: "center",
        top: "46%",
        style: {
          text: subtitle,
          fill: "rgba(219, 229, 240, 0.46)",
          fontSize: 10,
        },
      },
    ],
  };
}

function buildWaterfallSteps(startValue, netFlow, performance, endValue) {
  const steps = [];
  steps.push({
    label: "期初",
    base: 0,
    value: Math.max(startValue, 0),
    color: "#7be7ff",
    signedLabel: formatCurrency(startValue),
    shortLabel: formatCompactNumber(startValue),
  });

  let running = startValue;
  [
    { label: "淨流入", value: netFlow, positiveColor: "#ffcf78", negativeColor: "#ff7f9d" },
    { label: "真實績效", value: performance, positiveColor: "#6ef0a7", negativeColor: "#ff5f7e" },
  ].forEach((item) => {
    const next = running + item.value;
    steps.push({
      label: item.label,
      base: item.value >= 0 ? running : next,
      value: Math.abs(item.value),
      color: item.value >= 0 ? item.positiveColor : item.negativeColor,
      signedLabel: formatSignedCurrency(item.value, props.assetBaseCurrency),
      shortLabel: formatCompactNumber(item.value, true),
    });
    running = next;
  });

  steps.push({
    label: "期末",
    base: 0,
    value: Math.max(endValue, 0),
    color: "#8d92ff",
    signedLabel: formatCurrency(endValue),
    shortLabel: formatCompactNumber(endValue),
  });
  return steps;
}

function paletteColorFor(items, key) {
  const index = (items || []).findIndex((item) => item.key === key);
  return palette[index >= 0 ? index % palette.length : 0];
}

function percentAgainstAsset(value, total) {
  const numerator = Number(value || 0);
  const denominator = Number(total || 0);
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || !denominator) return 0;
  return (numerator / denominator) * 100;
}

function formatNumber(value, digits = 2) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return numeric.toLocaleString("zh-TW", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function formatCurrency(value, currency = props.assetBaseCurrency) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${currency} ${numeric.toLocaleString("zh-TW", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function formatSignedCurrency(value, currency = props.assetBaseCurrency, flowType = "") {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  const sign = flowType
    ? (["withdraw", "fee", "tax", "fx_fee", "transfer_out"].includes(String(flowType)) ? "-" : "+")
    : (numeric >= 0 ? "+" : "-");
  return `${sign}${currency} ${Math.abs(numeric).toLocaleString("zh-TW", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function formatPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${numeric.toFixed(2)}%`;
}

function formatCompactNumber(value, includeSign = false) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  const sign = includeSign && numeric > 0 ? "+" : includeSign && numeric < 0 ? "-" : "";
  const absolute = Math.abs(numeric);
  if (absolute >= 1000000) return `${sign}${(absolute / 1000000).toFixed(1)}M`;
  if (absolute >= 1000) return `${sign}${(absolute / 1000).toFixed(1)}K`;
  return `${sign}${absolute.toFixed(0)}`;
}

function formatDateLabel(value, includeTime = false) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("zh-TW", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

function formatShortDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleDateString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
  });
}

function formatMonthLabel(value) {
  if (!value) return "—";
  const year = value.slice(0, 4);
  const month = value.slice(5, 7);
  if (!year || !month) return value;
  return `${year}/${month}`;
}

function extractMonth(value) {
  return String(value || "").slice(0, 7);
}

function flowTypeLabel(value) {
  return ({
    deposit: "入金",
    withdraw: "出金",
    transfer_in: "轉入",
    transfer_out: "轉出",
    dividend: "股利",
    fee: "手續費",
    tax: "稅費",
    fx_fee: "匯費",
    interest: "利息",
  }[String(value || "")] || String(value || "事件"));
}

function tradeSideLabel(value) {
  return String(value || "").toLowerCase() === "sell" ? "賣出" : "買進";
}
</script>

<style scoped>
.asset-overview {
  padding: 18px;
}

.asset-warning-action,
.asset-summary-action,
.asset-donut-legend-item {
  border: 0;
  text-align: left;
  cursor: pointer;
}

.asset-warning-action {
  width: 100%;
}

.asset-summary-action {
  width: 100%;
  padding: 14px;
}

.asset-summary-action.active {
  border-color: rgba(123, 231, 255, 0.34);
  background:
    linear-gradient(180deg, rgba(123, 231, 255, 0.12), rgba(255, 255, 255, 0.03)),
    rgba(255, 255, 255, 0.03);
}

.asset-summary-card small {
  display: block;
  margin-top: 8px;
  color: rgba(219, 229, 240, 0.58);
  font-size: 10px;
}

.asset-chart-mode-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.asset-inline-btn.active {
  background: rgba(123, 231, 255, 0.14);
  color: #f5fbff;
}

.asset-performance-grid-chart {
  align-items: stretch;
}

.asset-curve-card-chart {
  display: flex;
  flex-direction: column;
}

.asset-chart-shell {
  margin-top: 12px;
}

.asset-chart {
  width: 100%;
}

.asset-chart-performance {
  min-height: 340px;
}

.asset-chart-waterfall,
.asset-chart-contributors {
  min-height: 280px;
}

.asset-chart-heatmap {
  min-height: 300px;
}

.asset-chart-donut {
  min-height: 260px;
}

.asset-side-analytics-chart {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.asset-overview-secondary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.asset-donut-card {
  display: grid;
  gap: 12px;
}

.asset-donut-legend {
  display: grid;
  gap: 8px;
}

.asset-donut-legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(8, 14, 24, 0.66);
  color: var(--text1);
}

.asset-donut-legend-item strong {
  flex: 1;
}

.asset-donut-legend-item small {
  color: rgba(219, 229, 240, 0.64);
}

.asset-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  flex: 0 0 10px;
}

.asset-preview-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

:deep(.asset-tooltip-title) {
  margin-bottom: 8px;
  color: #f5fbff;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 1180px) {
  .asset-overview-secondary-grid,
  .asset-preview-grid,
  .asset-side-analytics-chart {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .asset-chart-performance,
  .asset-chart-waterfall,
  .asset-chart-contributors,
  .asset-chart-heatmap,
  .asset-chart-donut {
    min-height: 240px;
  }
}
</style>
