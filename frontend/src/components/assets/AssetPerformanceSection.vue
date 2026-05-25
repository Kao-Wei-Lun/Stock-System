<template>
  <section class="asset-performance-section">
    <header class="asset-section-head">
      <div>
        <span>Performance</span>
        <strong>資產走勢</strong>
      </div>
      <div class="asset-range-control" aria-label="績效期間">
        <button
          v-for="item in rangeOptions"
          :key="item.value"
          type="button"
          :class="{ active: assetPerformanceRange === item.value }"
          @click="$emit('set-asset-performance-range', item.value)"
        >
          {{ item.label }}
        </button>
      </div>
    </header>

    <div v-if="assetLoading" class="asset-performance-loading">
      <div class="asset-chart-skeleton"></div>
      <div class="asset-summary-skeleton">
        <span v-for="index in 7" :key="index"></span>
      </div>
    </div>

    <div v-else-if="chartReady" class="asset-performance-layout">
      <div class="asset-chart-panel">
        <DeferredVChart class="asset-performance-chart" :option="chartOption" autoresize />
      </div>
      <aside class="asset-performance-summary">
        <div
          v-for="item in summaryRows"
          :key="item.key"
          class="asset-summary-row"
          :data-testid="`asset-performance-summary-${item.key}`"
        >
          <span>{{ item.label }}</span>
          <strong :class="item.tone" :title="item.title || ''">{{ item.value }}</strong>
        </div>
      </aside>
    </div>

    <div v-else class="asset-empty-state">
      目前沒有足夠的歷史快照可繪製資產走勢。
    </div>
  </section>
</template>

<script setup>
import { computed, provide } from "vue";
import { use, graphic } from "echarts/core";
import { LineChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { THEME_KEY } from "vue-echarts";

import DeferredVChart from "../DeferredVChart.vue";
import {
  EMPTY_MARK,
  formatCalculationMethodLabel,
  formatCompactNumber,
  formatCurrency as formatAssetCurrency,
  formatDateLabel,
  formatPercent,
  formatShortDate,
  formatSignedCurrency as formatAssetSignedCurrency,
  parseFiniteNumber,
  toneForValue,
} from "./assetDashboardFormatters";

use([LineChart, CanvasRenderer, DataZoomComponent, GridComponent, TooltipComponent]);
provide(THEME_KEY, "dark");

const INFO_COLOR = "#60a5fa";

const props = defineProps({
  assetLoading: { type: Boolean, default: false },
  assetPerformanceRange: { type: String, default: "1y" },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetPerformanceSummary: { type: Object, default: () => ({}) },
  portfolioCalculationMetadata: { type: Object, default: () => ({}) },
  performanceCalculationMetadata: { type: Object, default: () => ({}) },
  assetPerformanceSeries: { type: Array, default: () => [] },
});

defineEmits(["set-asset-performance-range"]);

const rangeOptions = [
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "180d", label: "180D" },
  { value: "1y", label: "1Y" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "All" },
];

const rows = computed(() => (
  (props.assetPerformanceSeries || [])
    .map((item) => ({
      date: String(item?.date || ""),
      cash_total_base: parseFiniteNumber(item?.cash_total_base),
      market_value_total_base: parseFiniteNumber(item?.market_value_total_base),
      total_asset_value_base: parseFiniteNumber(item?.total_asset_value_base),
      true_performance_base: parseFiniteNumber(item?.true_performance_base),
      net_flow_base: parseFiniteNumber(item?.net_flow_base),
    }))
    .filter((item) => item.date && item.total_asset_value_base != null)
));

const chartReady = computed(() => rows.value.length >= 2);

const totalPnl = computed(() => {
  const direct = parseFiniteNumber(props.assetSummary?.total_pnl_base);
  if (direct != null) return direct;
  const realized = parseFiniteNumber(props.assetSummary?.realized_total_base);
  const unrealized = parseFiniteNumber(props.assetSummary?.unrealized_total_base);
  if (realized == null && unrealized == null) return null;
  return Number(realized || 0) + Number(unrealized || 0);
});

const currentPositionCostTitle = computed(() => {
  const metadata = props.portfolioCalculationMetadata?.current_position_cost;
  if (!metadata || !Object.keys(metadata).length) {
    return "目前持倉成本為現有持倉的成本基礎加總，不代表歷史累積投入本金。";
  }
  return [
    formatCalculationMethodLabel(metadata.method),
    "來源為 holdings.cost_basis_base",
    "此數值不是歷史累積投入本金",
  ].join("。");
});

const summaryRows = computed(() => [
  {
    key: "current-position-cost",
    label: "目前持倉成本",
    value: formatCurrency(props.assetSummary?.current_position_cost_base),
    tone: "neutral",
    title: currentPositionCostTitle.value,
  },
  {
    key: "total-pnl",
    label: "累積損益",
    value: formatSignedCurrency(totalPnl.value),
    tone: toneForValue(totalPnl.value),
  },
  {
    key: "realized",
    label: "已實現損益",
    value: formatSignedCurrency(props.assetSummary?.realized_total_base),
    tone: toneForValue(props.assetSummary?.realized_total_base),
  },
  {
    key: "unrealized",
    label: "未實現損益",
    value: formatSignedCurrency(props.assetSummary?.unrealized_total_base),
    tone: toneForValue(props.assetSummary?.unrealized_total_base),
  },
  {
    key: "return",
    label: "總報酬率",
    value: formatPercent(props.assetPerformanceSummary?.true_return_pct),
    tone: toneForValue(props.assetPerformanceSummary?.true_return_pct),
  },
  {
    key: "annualized",
    label: "年化報酬率",
    value: EMPTY_MARK,
    tone: "neutral",
    title: "目前 API 尚未提供可靠年化報酬率欄位。",
  },
  {
    key: "drawdown",
    label: "最大回撤",
    value: formatPercent(props.assetPerformanceSummary?.max_drawdown_pct),
    tone: toneForValue(props.assetPerformanceSummary?.max_drawdown_pct),
  },
]);

const chartOption = computed(() => ({
  animation: false,
  backgroundColor: "transparent",
  tooltip: {
    trigger: "axis",
    axisPointer: { type: "line", snap: true },
    backgroundColor: "rgba(15, 23, 42, 0.96)",
    borderColor: "rgba(148, 163, 184, 0.22)",
    textStyle: { color: "#e5e7eb" },
    formatter(params) {
      const raw = params?.[0]?.data?.raw;
      if (!raw) return "";
      return [
        `<div class="asset-tooltip-title">${formatDateLabel(raw.date)}</div>`,
        `<div>總資產：${formatCurrency(raw.total_asset_value_base)}</div>`,
        `<div>現金：${formatCurrency(raw.cash_total_base)}</div>`,
        `<div>持倉市值：${formatCurrency(raw.market_value_total_base)}</div>`,
        `<div>區間績效：${formatSignedCurrency(raw.true_performance_base)}</div>`,
      ].join("");
    },
  },
  grid: { top: 24, right: 24, bottom: 42, left: 56 },
  dataZoom: [{ type: "inside", filterMode: "none" }],
  xAxis: {
    type: "category",
    data: rows.value.map((item) => formatShortDate(item.date)),
    boundaryGap: false,
    axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.18)" } },
    axisLabel: { color: "#94a3b8", hideOverlap: true },
  },
  yAxis: {
    type: "value",
    axisLine: { show: false },
    axisLabel: {
      color: "#94a3b8",
      formatter: (value) => formatCompactNumber(value),
    },
    splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.12)" } },
  },
  series: [
    {
      type: "line",
      name: "總資產",
      smooth: 0.22,
      symbol: "circle",
      symbolSize: 5,
      lineStyle: { width: 3, color: INFO_COLOR },
      itemStyle: {
        color: INFO_COLOR,
        borderColor: "#0b111a",
        borderWidth: 2,
      },
      areaStyle: {
        color: new graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: "rgba(37, 99, 235, 0.24)" },
          { offset: 1, color: "rgba(37, 99, 235, 0.02)" },
        ]),
      },
      data: rows.value.map((item) => ({
        value: item.total_asset_value_base,
        raw: item,
      })),
    },
  ],
}));

function formatCurrency(value, currency = props.assetBaseCurrency) {
  return formatAssetCurrency(value, currency);
}

function formatSignedCurrency(value, currency = props.assetBaseCurrency) {
  return formatAssetSignedCurrency(value, currency);
}
</script>

<style scoped>
.asset-performance-section {
  margin-bottom: 18px;
  padding: 18px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-card, 16px);
  background: var(--asset-card-bg, #111827);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.14);
}

.asset-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.asset-section-head div:first-child {
  display: grid;
  gap: 5px;
}

.asset-section-head span {
  color: var(--asset-text-muted, #64748b);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.asset-section-head strong {
  color: var(--asset-text-primary, #e5e7eb);
  font-size: 20px;
}

.asset-range-control {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.asset-range-control button {
  padding: 7px 10px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-control, 10px);
  background: rgba(15, 23, 42, 0.72);
  color: var(--asset-text-secondary, #94a3b8);
  cursor: pointer;
}

.asset-range-control button.active {
  border-color: rgba(37, 99, 235, 0.48);
  background: rgba(37, 99, 235, 0.18);
  color: var(--asset-text-primary, #e5e7eb);
}

.asset-performance-layout,
.asset-performance-loading {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(260px, 0.8fr);
  gap: 16px;
  align-items: stretch;
}

.asset-chart-panel {
  min-width: 0;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-inner, 12px);
  background: rgba(15, 23, 42, 0.52);
}

.asset-performance-chart {
  min-height: 360px;
  width: 100%;
}

.asset-performance-summary {
  display: grid;
  align-content: start;
  gap: 8px;
}

.asset-summary-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-inner, 12px);
  background: rgba(15, 23, 42, 0.56);
}

.asset-summary-row span {
  color: var(--asset-text-secondary, #94a3b8);
}

.asset-summary-row strong {
  color: var(--asset-text-primary, #e5e7eb);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.asset-summary-row strong.positive {
  color: var(--asset-positive, #ef4444);
}

.asset-summary-row strong.negative {
  color: var(--asset-negative, #22c55e);
}

.asset-empty-state {
  display: grid;
  place-items: center;
  min-height: 260px;
  border: 1px dashed var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-card, 16px);
  color: var(--asset-text-secondary, #94a3b8);
  text-align: center;
}

.asset-chart-skeleton,
.asset-summary-skeleton span {
  border-radius: var(--asset-radius-inner, 12px);
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.08), rgba(148, 163, 184, 0.2), rgba(148, 163, 184, 0.08));
  background-size: 180% 100%;
  animation: asset-skeleton 1.2s ease-in-out infinite;
}

.asset-chart-skeleton {
  min-height: 360px;
}

.asset-summary-skeleton {
  display: grid;
  gap: 8px;
}

.asset-summary-skeleton span {
  height: 46px;
}

:deep(.asset-tooltip-title) {
  margin-bottom: 8px;
  color: #f8fafc;
  font-weight: 700;
}

@keyframes asset-skeleton {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@media (max-width: 1080px) {
  .asset-performance-layout,
  .asset-performance-loading {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .asset-section-head {
    display: grid;
  }

  .asset-performance-chart,
  .asset-chart-skeleton {
    min-height: 300px;
  }
}
</style>
