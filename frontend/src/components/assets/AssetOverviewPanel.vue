<template>
  <div class="asset-overview">
    <div v-if="assetError" class="asset-error-state">
      <strong>資產資料載入異常</strong>
      <span>{{ assetError }}</span>
    </div>

    <AssetKpiGrid
      :asset-loading="assetLoading"
      :asset-performance-range="assetPerformanceRange"
      :asset-base-currency="assetBaseCurrency"
      :asset-summary="assetSummary"
      :asset-performance-summary="assetPerformanceSummary"
      :asset-performance-series="assetPerformanceSeries"
      :asset-holdings="assetHoldings"
    />

    <AssetPerformanceSection
      :asset-loading="assetLoading"
      :asset-performance-range="assetPerformanceRange"
      :asset-base-currency="assetBaseCurrency"
      :asset-summary="assetSummary"
      :asset-performance-summary="assetPerformanceSummary"
      :asset-performance-series="assetPerformanceSeries"
      @set-asset-performance-range="$emit('set-asset-performance-range', $event)"
    />

    <div v-if="hasWarnings" class="asset-warning-stack" aria-label="資產資料提醒">
      <button
        v-for="warning in assetWarnings"
        :key="warning"
        class="asset-warning-card asset-warning-action"
        type="button"
        @click="$emit('focus-maintenance', 'reconciliation')"
      >
        {{ warning }}
      </button>
      <button
        v-for="gap in assetQuoteGaps"
        :key="`${gap.account_id}-${gap.ticker}`"
        class="asset-warning-card asset-warning-action"
        type="button"
        @click="$emit('focus-maintenance', 'price-overrides')"
      >
        {{ gap.ticker }} 暫時抓不到最新報價，目前未納入估值；可到資料維護補手動價格覆蓋。
      </button>
      <button
        v-for="item in reconciliationGapItems"
        :key="`reco-${item.account_id}-${item.snapshot_id}`"
        class="asset-warning-card asset-warning-action"
        type="button"
        @click="$emit('focus-maintenance', 'reconciliation')"
      >
        {{ item.account_name }} 對帳差異 {{ formatSignedCurrency(item.total_difference, assetBaseCurrency) }}
      </button>
      <button
        v-for="alert in assetAlerts"
        :key="`${alert.code}-${alert.title}`"
        class="asset-warning-card asset-warning-action"
        :class="alert.level === 'info' ? 'info' : 'warning'"
        type="button"
        @click="$emit('focus-maintenance', 'reconciliation')"
      >
        <strong>{{ alert.title }}</strong>
        <span>{{ alert.message }}</span>
      </button>
    </div>

    <AssetHoldingsTable
      :asset-loading="assetLoading"
      :asset-base-currency="assetBaseCurrency"
      :asset-summary="assetSummary"
      :asset-holdings="assetHoldings"
      @focus-holding="focusHoldings({ ticker: $event })"
    />

    <div class="asset-overview-secondary-grid">
      <section class="asset-card">
        <div class="asset-card-head">
          <div>
            <div class="asset-card-title">本期資產怎麼變</div>
            <div class="bt-trade-sub">先用故事講清楚，再視需要切到進階瀑布圖</div>
          </div>
          <div class="asset-change-head">
            <div class="asset-list-metrics">
              <span>{{ formatCurrency(changeBreakdown.endValue) }}</span>
              <small>{{ selectedSnapshotLabel }} 焦點</small>
            </div>
            <div class="asset-chart-mode-row">
              <button
                class="asset-inline-btn"
                :class="{ active: changeBreakdownView === 'story' }"
                data-testid="asset-change-view-story"
                type="button"
                @click="setChangeBreakdownView('story')"
              >
                摘要
              </button>
              <button
                class="asset-inline-btn"
                :class="{ active: changeBreakdownView === 'waterfall' }"
                data-testid="asset-change-view-waterfall"
                type="button"
                @click="setChangeBreakdownView('waterfall')"
              >
                瀑布圖
              </button>
            </div>
          </div>
        </div>
        <div v-if="waterfallChartReady">
          <div v-show="changeBreakdownView === 'story'" class="asset-change-story" data-testid="asset-change-story">
            <div class="asset-change-hero">
              <span class="asset-change-eyebrow">{{ changeBreakdownEyebrow }}</span>
              <strong>{{ changeBreakdownLead }}</strong>
              <p>{{ changeBreakdownDetail }}</p>
            </div>

            <div class="asset-change-step-grid">
              <article
                v-for="step in changeBreakdownSteps"
                :key="step.key"
                class="asset-change-step"
                :class="step.tone"
              >
                <span class="asset-change-step-label">{{ step.label }}</span>
                <strong>{{ step.value }}</strong>
                <small>{{ step.helper }}</small>
              </article>
            </div>

            <div class="asset-change-equation" aria-label="asset-change-equation">
              <span>{{ formatCurrency(changeBreakdown.startValue) }}</span>
              <b>+</b>
              <span :class="trendClass(changeBreakdown.netFlow)">
                {{ formatSignedCurrency(changeBreakdown.netFlow, assetBaseCurrency) }}
              </span>
              <b>+</b>
              <span :class="trendClass(changeBreakdown.performance)">
                {{ formatSignedCurrency(changeBreakdown.performance, assetBaseCurrency) }}
              </span>
              <b>=</b>
              <strong>{{ formatCurrency(changeBreakdown.endValue) }}</strong>
            </div>

            <div class="asset-change-source-grid">
              <article class="asset-change-source-card">
                <header>
                  <div>
                    <span class="asset-change-source-kicker">資金流拆解</span>
                    <strong>{{ formatSignedCurrency(selectedFlowBreakdown.net_flow_base, assetBaseCurrency) }}</strong>
                  </div>
                  <small>加總後形成目前的淨流入</small>
                </header>
                <div class="asset-breakdown-list">
                  <div
                    v-for="row in fundingBreakdownRows"
                    :key="row.key"
                    class="asset-breakdown-row"
                  >
                    <div class="asset-breakdown-row-head">
                      <span>{{ row.label }}</span>
                      <strong :class="row.tone">{{ formatSignedCurrency(row.amount, assetBaseCurrency) }}</strong>
                    </div>
                    <div class="asset-breakdown-bar-track">
                      <div
                        class="asset-breakdown-bar-fill"
                        :class="row.tone"
                        :style="{ width: `${resolveBreakdownShare(row.amount, fundingBreakdownMax)}%` }"
                      ></div>
                    </div>
                    <small>{{ row.helper }}</small>
                  </div>
                </div>
              </article>

              <article class="asset-change-source-card">
                <header>
                  <div>
                    <span class="asset-change-source-kicker">損益來源</span>
                    <strong :class="trendClass(changeBreakdown.performance)">
                      {{ formatSignedCurrency(selectedPerformanceBreakdown.total_change_base, assetBaseCurrency) }}
                    </strong>
                  </div>
                  <small>扣除資金流後，資產自己變動的來源</small>
                </header>
                <div class="asset-breakdown-list">
                  <div
                    v-for="row in performanceBreakdownRows"
                    :key="row.key"
                    class="asset-breakdown-row"
                  >
                    <div class="asset-breakdown-row-head">
                      <span>{{ row.label }}</span>
                      <strong :class="row.tone">{{ formatSignedCurrency(row.amount, assetBaseCurrency) }}</strong>
                    </div>
                    <div class="asset-breakdown-bar-track">
                      <div
                        class="asset-breakdown-bar-fill"
                        :class="row.tone"
                        :style="{ width: `${resolveBreakdownShare(row.amount, performanceBreakdownMax)}%` }"
                      ></div>
                    </div>
                    <small>{{ row.helper }}</small>
                  </div>
                </div>
              </article>
            </div>

            <div class="asset-change-insight-grid">
              <article class="asset-change-insight-card">
                <header>
                  <span>資金流後基礎</span>
                  <strong>{{ formatCurrency(changeBreakdown.capitalBase) }}</strong>
                </header>
                <p>{{ changeFundingDescription }}</p>
                <div class="asset-change-pill-row">
                  <span class="asset-change-pill neutral">期初 {{ formatCurrency(changeBreakdown.startValue) }}</span>
                  <span class="asset-change-pill" :class="flowPillClass(changeBreakdown.netFlow)">
                    {{ changeBreakdown.netFlow >= 0 ? "新增投入" : "淨流出" }}
                    {{ formatSignedCurrency(changeBreakdown.netFlow, assetBaseCurrency) }}
                  </span>
                </div>
              </article>

              <article class="asset-change-insight-card">
                <header>
                  <span>投資結果</span>
                  <strong :class="trendClass(changeBreakdown.performance)">
                    {{ formatSignedCurrency(changeBreakdown.performance, assetBaseCurrency) }}
                  </strong>
                </header>
                <p>{{ changePerformanceDescription }}</p>
                <div class="asset-change-pill-row">
                  <span class="asset-change-pill accent">期末 {{ formatCurrency(changeBreakdown.endValue) }}</span>
                  <span class="asset-change-pill" :class="performancePillClass(changeBreakdown.performance)">
                    {{ changeBreakdown.performance >= 0 ? "報酬貢獻" : "損失影響" }}
                    {{ formatSignedCurrency(changeBreakdown.performance, assetBaseCurrency) }}
                  </span>
                </div>
              </article>
            </div>
          </div>

          <div v-show="changeBreakdownView === 'waterfall'" class="asset-chart-shell asset-chart-shell-waterfall">
            <DeferredVChart class="asset-chart asset-chart-waterfall" :option="waterfallChartOption" autoresize />
          </div>
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
          <DeferredVChart
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
      <AssetAllocationSection
        :asset-base-currency="assetBaseCurrency"
        :asset-account-allocation="assetAccountAllocation"
        :asset-market-allocation="assetMarketAllocation"
        :asset-currency-allocation="assetCurrencyAllocation"
        @focus-holdings="focusHoldings"
      />

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
          <DeferredVChart
            class="asset-chart asset-chart-contributors"
            :option="contributorChartOption"
            autoresize
            @click="handleContributorClick"
          />
        </div>
        <div v-else class="bt-history-empty">尚無損益貢獻資料。</div>
      </section>
    </div>

    <div class="asset-preview-grid asset-preview-grid-single">
      <AssetActivityTimeline
        :asset-loading="assetLoading"
        :asset-base-currency="assetBaseCurrency"
        :asset-cash-entries="assetCashEntries"
        :asset-trade-entries="assetTradeEntries"
        @focus-holdings="focusHoldings"
        @open-tab="$emit('open-tab', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, provide, ref, watch } from "vue";
import { use, graphic } from "echarts/core";
import { BarChart, HeatmapChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { THEME_KEY } from "vue-echarts";
import AssetActivityTimeline from "./AssetActivityTimeline.vue";
import AssetAllocationSection from "./AssetAllocationSection.vue";
import AssetHoldingsTable from "./AssetHoldingsTable.vue";
import AssetKpiGrid from "./AssetKpiGrid.vue";
import AssetPerformanceSection from "./AssetPerformanceSection.vue";
import DeferredVChart from "../DeferredVChart.vue";
import {
  formatCompactNumber as formatAssetCompactNumber,
  formatCurrency as formatAssetCurrency,
  formatDateLabel as formatAssetDateLabel,
  formatMonthLabel,
  formatPercent,
  formatSignedCurrency as formatAssetSignedCurrency,
  numberOrZero,
  parseFiniteNumber,
  percentAgainst,
  trendClass,
} from "./assetDashboardFormatters";

use([
  BarChart,
  HeatmapChart,
  CanvasRenderer,
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
]);

provide(THEME_KEY, "dark");

const props = defineProps({
  assetLoading: { type: Boolean, default: false },
  assetError: { type: String, default: "" },
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
  assetCurrencyAllocation: { type: Array, default: () => [] },
  assetContributors: { type: Object, default: () => ({ top_gainers: [], top_losers: [] }) },
  assetHoldings: { type: Array, default: () => [] },
  assetCashEntries: { type: Array, default: () => [] },
  assetTradeEntries: { type: Array, default: () => [] },
});

const emit = defineEmits([
  "set-asset-performance-range",
  "open-tab",
  "focus-holdings",
  "focus-maintenance",
]);

const emptyFlowBreakdown = Object.freeze({
  deposit_base: 0,
  withdraw_base: 0,
  dividend_interest_base: 0,
  fee_tax_base: 0,
  transfer_in_base: 0,
  transfer_out_base: 0,
  other_flow_base: 0,
  net_flow_base: 0,
});
const emptyPerformanceBreakdown = Object.freeze({
  realized_change_base: 0,
  unrealized_change_base: 0,
  other_change_base: 0,
  total_change_base: 0,
});

const changeBreakdownView = ref("story");
const selectedDate = ref("");
const selectedMonth = ref("");

const reconciliationItems = computed(() => props.assetReconciliation?.items || []);
const reconciliationGapItems = computed(() => reconciliationItems.value.filter((item) => item?.has_gap));
const hasWarnings = computed(() => (
  props.assetWarnings.length
  || props.assetQuoteGaps.length
  || props.assetAlerts.length
  || reconciliationGapItems.value.length
));

const performanceRows = computed(() => (
  (props.assetPerformanceSeries || [])
    .map((item) => ({
      date: String(item?.date || ""),
      cash_total_base: numberOrZero(item?.cash_total_base),
      market_value_total_base: numberOrZero(item?.market_value_total_base),
      total_asset_value_base: numberOrZero(item?.total_asset_value_base),
      true_performance_base: numberOrZero(item?.true_performance_base),
      net_flow_base: numberOrZero(item?.net_flow_base),
      realized_total_base: numberOrZero(item?.realized_total_base),
      unrealized_total_base: numberOrZero(item?.unrealized_total_base),
      drawdown_pct: numberOrZero(item?.drawdown_pct),
      quote_gap_count: numberOrZero(item?.quote_gap_count),
      flow_breakdown: normalizeFlowBreakdown(item?.flow_breakdown),
      performance_breakdown: normalizePerformanceBreakdown(item?.performance_breakdown),
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
    flow_breakdown: emptyFlowBreakdown,
    performance_breakdown: emptyPerformanceBreakdown,
  }
));

const selectedSnapshotLabel = computed(() => formatDateLabel(selectedPoint.value.date));
const selectedMonthLabel = computed(() => formatMonthLabel(selectedMonth.value));
const selectedFlowBreakdown = computed(() => normalizeFlowBreakdown(
  selectedPoint.value.flow_breakdown || props.assetPerformanceSummary.flow_breakdown,
));
const selectedPerformanceBreakdown = computed(() => normalizePerformanceBreakdown(
  selectedPoint.value.performance_breakdown || props.assetPerformanceSummary.performance_breakdown,
));
const changeBreakdown = computed(() => {
  const startValue = numberOrZero(props.assetPerformanceSummary.start_value_base);
  const netFlow = parseFiniteNumber(selectedFlowBreakdown.value.net_flow_base)
    ?? parseFiniteNumber(selectedPoint.value.net_flow_base)
    ?? 0;
  const breakdownPerformance = parseFiniteNumber(selectedPerformanceBreakdown.value.total_change_base);
  const pointPerformance = parseFiniteNumber(selectedPoint.value.true_performance_base);
  const performance = breakdownPerformance != null && Math.abs(breakdownPerformance) >= 0.01
    ? breakdownPerformance
    : pointPerformance ?? breakdownPerformance ?? 0;
  const endValue = numberOrZero(selectedPoint.value.total_asset_value_base);
  return {
    startValue,
    netFlow,
    performance,
    endValue,
    capitalBase: startValue + netFlow,
  };
});
const fundingBreakdownRows = computed(() => {
  const flow = selectedFlowBreakdown.value;
  const transferNet = numberOrZero(flow.transfer_in_base) - numberOrZero(flow.transfer_out_base);
  const rows = [
    {
      key: "deposit",
      label: "入金",
      amount: numberOrZero(flow.deposit_base),
      helper: "你主動補進來的資金",
      tone: "up",
    },
    {
      key: "withdraw",
      label: "出金",
      amount: -numberOrZero(flow.withdraw_base),
      helper: "提領或移出資產池的資金",
      tone: "dn",
    },
    {
      key: "dividend",
      label: "股利 / 利息",
      amount: numberOrZero(flow.dividend_interest_base),
      helper: "資產自己產生的現金流",
      tone: "up",
    },
    {
      key: "fees",
      label: "費用 / 稅 / 匯費",
      amount: -numberOrZero(flow.fee_tax_base),
      helper: "交易與匯兌成本",
      tone: "dn",
    },
  ];
  if (Math.abs(transferNet) >= 0.01 || numberOrZero(flow.transfer_in_base) || numberOrZero(flow.transfer_out_base)) {
    rows.push({
      key: "transfer",
      label: "帳戶轉撥",
      amount: transferNet,
      helper: `轉入 ${formatCurrency(flow.transfer_in_base)} / 轉出 ${formatCurrency(flow.transfer_out_base)}`,
      tone: transferNet >= 0 ? "neutral" : "dn",
    });
  }
  if (Math.abs(numberOrZero(flow.other_flow_base)) >= 0.01) {
    rows.push({
      key: "other",
      label: "其他現金事件",
      amount: numberOrZero(flow.other_flow_base),
      helper: "尚未歸類的現金流",
      tone: numberOrZero(flow.other_flow_base) >= 0 ? "neutral" : "dn",
    });
  }
  return rows;
});
const performanceBreakdownRows = computed(() => {
  const breakdown = selectedPerformanceBreakdown.value;
  const rows = [
    {
      key: "realized",
      label: "已實現損益",
      amount: numberOrZero(breakdown.realized_change_base),
      helper: "已賣出或結束部位累積的結果",
      tone: trendClass(breakdown.realized_change_base),
    },
    {
      key: "unrealized",
      label: "未實現損益",
      amount: numberOrZero(breakdown.unrealized_change_base),
      helper: "目前仍持有部位的估值變化",
      tone: trendClass(breakdown.unrealized_change_base),
    },
  ];
  if (Math.abs(numberOrZero(breakdown.other_change_base)) >= 0.01) {
    rows.push({
      key: "other",
      label: "其他差異",
      amount: numberOrZero(breakdown.other_change_base),
      helper: "尚未被已實現 / 未實現涵蓋的變化",
      tone: numberOrZero(breakdown.other_change_base) >= 0 ? "neutral" : "dn",
    });
  }
  return rows;
});
const fundingBreakdownMax = computed(() => resolveBreakdownMax(fundingBreakdownRows.value));
const performanceBreakdownMax = computed(() => resolveBreakdownMax(performanceBreakdownRows.value));
const changeBreakdownEyebrow = computed(() => dominantDriverLabel(
  changeBreakdown.value.netFlow,
  changeBreakdown.value.performance,
));
const changeBreakdownLead = computed(() => createChangeBreakdownLead(
  changeBreakdown.value,
  selectedSnapshotLabel.value,
));
const changeBreakdownDetail = computed(() => createChangeBreakdownDetail(
  changeBreakdown.value,
  selectedSnapshotLabel.value,
));
const changeBreakdownSteps = computed(() => [
  {
    key: "start",
    label: "區間起點",
    value: formatCurrency(changeBreakdown.value.startValue),
    helper: "本次比較的起始快照",
    tone: "neutral",
  },
  {
    key: "flow",
    label: changeBreakdown.value.netFlow >= 0 ? "期間淨投入" : "期間淨流出",
    value: formatSignedCurrency(changeBreakdown.value.netFlow, props.assetBaseCurrency),
    helper: changeBreakdown.value.netFlow >= 0
      ? "你實際補進來的資金"
      : "這段期間領回或轉出的資金",
    tone: trendClass(changeBreakdown.value.netFlow),
  },
  {
    key: "performance",
    label: "投資損益",
    value: formatSignedCurrency(changeBreakdown.value.performance, props.assetBaseCurrency),
    helper: changeBreakdown.value.performance >= 0
      ? "扣除資金流後，資產自己長出來的部分"
      : "扣除資金流後，資產自己縮水的部分",
    tone: trendClass(changeBreakdown.value.performance),
  },
  {
    key: "end",
    label: "目前資產",
    value: formatCurrency(changeBreakdown.value.endValue),
    helper: `${selectedSnapshotLabel.value} 焦點`,
    tone: "accent",
  },
]);
const changeFundingDescription = computed(() => {
  const { capitalBase, netFlow } = changeBreakdown.value;
  if (Math.abs(netFlow) < 0.01) {
    return `這段期間幾乎沒有明顯的現金流變化，資產基礎大致維持在 ${formatCurrency(capitalBase)}。`;
  }
  if (netFlow > 0) {
    return `把入金、股利、費用與帳戶轉撥一起算進來後，資金流為淨流入 ${formatCurrency(Math.abs(netFlow))}，讓資產基礎提高到 ${formatCurrency(capitalBase)}。`;
  }
  return `把所有現金事件一起算後，這段期間淨流出 ${formatCurrency(Math.abs(netFlow))}，所以資產基礎降到 ${formatCurrency(capitalBase)}。`;
});
const changePerformanceDescription = computed(() => {
  const { performance, capitalBase, endValue } = changeBreakdown.value;
  if (Math.abs(performance) < 0.01) {
    return `扣掉資金流之後，資產本身幾乎沒有明顯變化，期末大致落在 ${formatCurrency(endValue)}。`;
  }
  if (performance > 0) {
    return `資產在本金基礎 ${formatCurrency(capitalBase)} 之上，又靠投資表現多長出 ${formatCurrency(Math.abs(performance))}。`;
  }
  return `投資虧損吃掉了 ${formatCurrency(Math.abs(performance))}，所以期末資產低於本金基礎 ${formatCurrency(capitalBase)}。`;
});
const heatmapYears = computed(() => (
  Array.from(new Set((props.assetMonthlyHeatmap || []).map((item) => String(item.month || "").slice(0, 4))))
    .filter(Boolean)
    .sort((left, right) => Number(right) - Number(left))
));
const heatmapEntriesByMonth = computed(() => {
  const lookup = new Map();
  (props.assetMonthlyHeatmap || []).forEach((item) => {
    const month = String(item?.month || "");
    if (!month) return;
    lookup.set(month, {
      month,
      return_pct: numberOrZero(item?.return_pct),
      true_performance_base: numberOrZero(item?.true_performance_base),
    });
  });
  return lookup;
});
const monthlyHeatmapCells = computed(() => (
  heatmapYears.value.flatMap((year, yearIndex) => (
    Array.from({ length: 12 }, (_, monthIndex) => {
      const month = `${year}-${String(monthIndex + 1).padStart(2, "0")}`;
      const entry = heatmapEntriesByMonth.value.get(month);
      const hasData = Boolean(entry);
      const isSelected = month === selectedMonth.value;
      return {
        value: [monthIndex, yearIndex, hasData ? entry.return_pct : 0],
        month,
        return_pct: hasData ? entry.return_pct : null,
        performance: hasData ? entry.true_performance_base : null,
        hasData,
        itemStyle: hasData
          ? {
            borderColor: isSelected ? "#f5fbff" : "rgba(7, 17, 27, 0.92)",
            borderWidth: isSelected ? 3 : 2,
          }
          : {
            color: "rgba(40, 46, 60, 0.72)",
            borderColor: isSelected ? "#8792a8" : "rgba(24, 31, 44, 0.92)",
            borderWidth: isSelected ? 2 : 1,
          },
      };
    })
  ))
));

const waterfallChartReady = computed(() => performanceRows.value.length >= 1);
const monthlyHeatmapReady = computed(() => (props.assetMonthlyHeatmap || []).length > 0);

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
      value: numberOrZero(item.unrealized_pnl_base),
    }))
    .sort((left, right) => right.value - left.value);
});

const waterfallChartOption = computed(() => {
  const endValue = numberOrZero(selectedPoint.value.total_asset_value_base);
  const startValue = numberOrZero(props.assetPerformanceSummary.start_value_base);
  const netFlow = numberOrZero(selectedPoint.value.net_flow_base);
  const performance = numberOrZero(selectedPoint.value.true_performance_base);
  const steps = buildWaterfallSteps(startValue, netFlow, performance, endValue);
  const bounds = resolveWaterfallBounds(steps);
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
    grid: { top: 28, right: 24, bottom: 28, left: 42 },
    xAxis: {
      type: "category",
      data: steps.map((item) => item.label),
      axisLine: { lineStyle: { color: "rgba(255, 255, 255, 0.12)" } },
      axisLabel: { color: "rgba(219, 229, 240, 0.72)" },
    },
    yAxis: {
      type: "value",
      min: bounds.min,
      max: bounds.max,
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
  return {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      confine: true,
      position(point, _params, _dom, _rect, size) {
        const [x = 0, y = 0] = Array.isArray(point) ? point : [0, 0];
        const contentWidth = size?.contentSize?.[0] || 0;
        const contentHeight = size?.contentSize?.[1] || 0;
        const viewWidth = size?.viewSize?.[0] || 0;
        const viewHeight = size?.viewSize?.[1] || 0;
        const left = Math.max(12, Math.min(x - (contentWidth / 2), viewWidth - contentWidth - 12));
        const topCandidate = y - contentHeight - 14;
        const top = topCandidate >= 12
          ? topCandidate
          : Math.min(viewHeight - contentHeight - 12, y + 18);
        return [left, Math.max(12, top)];
      },
      backgroundColor: "rgba(8, 14, 22, 0.94)",
      borderColor: "rgba(123, 231, 255, 0.18)",
      textStyle: { color: "#e7f3ff" },
      formatter(params) {
        const month = params?.data?.month || "";
        if (!params?.data?.hasData) {
          return [
            `<div class="asset-tooltip-title">${formatMonthLabel(month)}</div>`,
            "<div>目前沒有該月份的績效資料</div>",
          ].join("");
        }
        return [
          `<div class="asset-tooltip-title">${formatMonthLabel(month)}</div>`,
          `<div>真實報酬：${formatPercent(params.data.return_pct)}</div>`,
          `<div>績效金額：${formatSignedCurrency(params.data.performance, props.assetBaseCurrency)}</div>`,
        ].join("");
      },
    },
    grid: { top: 18, right: 12, bottom: 82, left: 42 },
    xAxis: {
      type: "category",
      data: monthNames,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: "rgba(255, 255, 255, 0.12)" } },
      axisLabel: {
        color: "rgba(219, 229, 240, 0.68)",
        margin: 16,
      },
    },
    yAxis: {
      type: "category",
      data: heatmapYears.value,
      inverse: true,
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
      bottom: 16,
      textStyle: { color: "rgba(219, 229, 240, 0.66)" },
      inRange: {
        color: ["#22c55e", "#292f3f", "#ef4444"],
      },
    },
    series: [
      {
        type: "heatmap",
        data: monthlyHeatmapCells.value,
        label: {
          show: true,
          color: "#f5fbff",
          formatter: ({ data }) => (data?.hasData ? formatPercent(data.return_pct, 1) : ""),
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
  grid: { top: 14, right: 96, bottom: 20, left: 68 },
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
          color: item.value > 0 ? "#ef4444" : item.value < 0 ? "#22c55e" : "#94a3b8",
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

function normalizeFlowBreakdown(value) {
  return {
    deposit_base: numberOrZero(value?.deposit_base),
    withdraw_base: numberOrZero(value?.withdraw_base),
    dividend_interest_base: numberOrZero(value?.dividend_interest_base),
    fee_tax_base: numberOrZero(value?.fee_tax_base),
    transfer_in_base: numberOrZero(value?.transfer_in_base),
    transfer_out_base: numberOrZero(value?.transfer_out_base),
    other_flow_base: numberOrZero(value?.other_flow_base),
    net_flow_base: numberOrZero(value?.net_flow_base),
  };
}

function normalizePerformanceBreakdown(value) {
  return {
    realized_change_base: numberOrZero(value?.realized_change_base),
    unrealized_change_base: numberOrZero(value?.unrealized_change_base),
    other_change_base: numberOrZero(value?.other_change_base),
    total_change_base: numberOrZero(value?.total_change_base),
  };
}

function setChangeBreakdownView(view) {
  changeBreakdownView.value = view === "waterfall" ? "waterfall" : "story";
}

function focusHoldings(filter = {}) {
  emit("focus-holdings", {
    accountKey: filter.accountKey || "",
    marketKey: filter.marketKey || "",
    ticker: filter.ticker || "",
    month: filter.month || "",
  });
}

function handleHeatmapClick(params) {
  const month = params?.data?.month;
  if (!month) return;
  selectedMonth.value = month;
  if (params?.data?.hasData) {
    focusHoldings({ month });
  }
}

function handleContributorClick(params) {
  const ticker = params?.data?.ticker;
  if (!ticker) return;
  focusHoldings({ ticker });
}

function buildWaterfallSteps(startValue, netFlow, performance, endValue) {
  const steps = [];
  if (Math.abs(startValue) >= 0.01) {
    steps.push({
      label: "期初",
      base: 0,
      value: Math.abs(startValue),
      color: "#7be7ff",
      signedLabel: formatCurrency(startValue),
      shortLabel: formatCompactNumber(startValue),
    });
  }

  let running = startValue;
  [
    { label: "淨流入", value: netFlow, positiveColor: "#ef4444", negativeColor: "#22c55e" },
    { label: "真實績效", value: performance, positiveColor: "#ef4444", negativeColor: "#22c55e" },
  ].forEach((item) => {
    if (Math.abs(item.value) < 0.01) return;
    const next = running + item.value;
    steps.push({
      label: item.label,
      base: item.value > 0 ? running : next,
      value: Math.abs(item.value),
      color: item.value > 0 ? item.positiveColor : item.negativeColor,
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

function dominantDriverLabel(netFlow, performance) {
  const flowValue = numberOrZero(netFlow);
  const performanceValue = numberOrZero(performance);
  const flowAbs = Math.abs(flowValue);
  const performanceAbs = Math.abs(performanceValue);
  if (flowAbs < 0.01 && performanceAbs < 0.01) return "這段期間幾乎沒有明顯變化";
  if (flowAbs >= performanceAbs) {
    return flowValue >= 0 ? "主要是新增投入把資產撐大" : "主要是資金流出在拉低資產";
  }
  return performanceValue >= 0 ? "主要是投資報酬在推高資產" : "主要是投資虧損在拖累資產";
}

function createChangeBreakdownLead({ netFlow, performance, endValue }, snapshotLabel) {
  const label = snapshotLabel && snapshotLabel !== "—" ? `${snapshotLabel} 為止` : "目前為止";
  if (Math.abs(netFlow) < 0.01 && Math.abs(performance) < 0.01) {
    return `${label}，總資產大致維持在 ${formatCurrency(endValue)}，沒有特別明顯的變化來源。`;
  }
  if (Math.abs(netFlow) >= Math.abs(performance)) {
    if (netFlow >= 0) {
      return `${label}，資產成長主要來自新增投入 ${formatCurrency(Math.abs(netFlow))}。`;
    }
    return `${label}，雖然有 ${formatCurrency(Math.abs(netFlow))} 的淨流出，資產仍維持在 ${formatCurrency(endValue)}。`;
  }
  if (performance >= 0) {
    return `${label}，資產變化主要來自投資損益增加 ${formatCurrency(Math.abs(performance))}。`;
  }
  return `${label}，資產變化主要受投資損失 ${formatCurrency(Math.abs(performance))} 影響。`;
}

function createChangeBreakdownDetail({ startValue, netFlow, performance, endValue }, snapshotLabel) {
  const label = snapshotLabel && snapshotLabel !== "—" ? snapshotLabel : "目前焦點";
  return [
    `以 ${formatCurrency(startValue)} 起步，`,
    netFlow >= 0
      ? `期間新增投入 ${formatCurrency(Math.abs(netFlow))}`
      : `期間淨流出 ${formatCurrency(Math.abs(netFlow))}`,
    `，投資損益 ${formatSignedCurrency(performance, props.assetBaseCurrency)}，`,
    `最後來到 ${label} 的 ${formatCurrency(endValue)}。`,
  ].join("");
}

function resolveWaterfallBounds(steps) {
  if (!steps.length) return { min: 0, max: 100 };
  const tops = steps.map((item) => numberOrZero(item.base) + numberOrZero(item.value));
  const bottoms = steps.map((item) => numberOrZero(item.base));
  const minValue = Math.min(0, ...tops, ...bottoms);
  const maxValue = Math.max(0, ...tops, ...bottoms);
  const span = Math.max(maxValue - minValue, 1);
  return {
    min: Number((minValue - span * 0.06).toFixed(2)),
    max: Number((maxValue + span * 0.1).toFixed(2)),
  };
}

function resolveBreakdownMax(rows) {
  return Math.max(...(rows || []).map((item) => Math.abs(numberOrZero(item.amount))), 1);
}

function resolveBreakdownShare(value, maxAbs) {
  const current = Math.abs(numberOrZero(value));
  const denominator = Math.max(numberOrZero(maxAbs), 1);
  return Number(((current / denominator) * 100).toFixed(2));
}

function flowPillClass(value) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null || numeric === 0) return "neutral";
  return numeric > 0 ? "warm" : "risk";
}

function performancePillClass(value) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null || numeric === 0) return "neutral";
  return numeric > 0 ? "success" : "risk";
}

function percentAgainstAsset(value, total) {
  return percentAgainst(value, total);
}

function formatCurrency(value, currency = props.assetBaseCurrency) {
  return formatAssetCurrency(value, currency);
}

function formatSignedCurrency(value, currency = props.assetBaseCurrency, flowType = "") {
  return formatAssetSignedCurrency(value, currency, flowType);
}

function formatCompactNumber(value, includeSign = false) {
  return formatAssetCompactNumber(value, includeSign);
}

function formatDateLabel(value, includeTime = false) {
  return formatAssetDateLabel(value, includeTime);
}

function extractMonth(value) {
  return String(value || "").slice(0, 7);
}
</script>

<style scoped>
.asset-overview {
  padding: 18px;
}

.asset-card {
  padding: 18px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-card, 16px);
  background: var(--asset-card-bg, #111827);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.14);
}

.asset-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.asset-card-title {
  color: var(--asset-text-primary, #e5e7eb);
  font-size: 18px;
  font-weight: 800;
}

.asset-inline-btn {
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-control, 10px);
  background: rgba(15, 23, 42, 0.72);
  color: var(--asset-text-secondary, #94a3b8);
  font: inherit;
  cursor: pointer;
}

.asset-inline-btn:hover,
.asset-inline-btn.active {
  border-color: rgba(37, 99, 235, 0.4);
  background: rgba(37, 99, 235, 0.16);
  color: var(--asset-text-primary, #e5e7eb);
}

.asset-warning-action,
.asset-summary-action {
  appearance: none;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.asset-warning-action {
  width: 100%;
}

.asset-warning-stack {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 10px;
  margin: 0 0 18px;
}

.asset-warning-card {
  min-height: 48px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 158, 11, 0.26);
  border-radius: var(--asset-radius-inner, 12px);
  background: rgba(245, 158, 11, 0.08);
  color: var(--asset-text-secondary, #94a3b8);
  line-height: 1.5;
}

.asset-warning-card:hover {
  border-color: rgba(245, 158, 11, 0.42);
  background: rgba(245, 158, 11, 0.12);
}

.asset-warning-card.info {
  border-color: rgba(37, 99, 235, 0.28);
  background: rgba(37, 99, 235, 0.1);
}

.asset-warning-card strong {
  display: block;
  color: var(--asset-text-primary, #e5e7eb);
  font-size: 12px;
}

.asset-warning-card span {
  display: block;
  margin-top: 4px;
  color: var(--asset-text-secondary, #94a3b8);
}

.asset-error-state {
  display: grid;
  gap: 6px;
  margin-bottom: 18px;
  padding: 14px 16px;
  border: 1px solid rgba(245, 158, 11, 0.32);
  border-radius: var(--asset-radius-card, 16px);
  background: rgba(245, 158, 11, 0.1);
  color: var(--asset-text-secondary, rgba(219, 229, 240, 0.82));
}

.asset-error-state strong {
  color: var(--asset-warning, #f59e0b);
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

.asset-change-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px 14px;
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

.asset-change-story {
  display: grid;
  gap: 14px;
  margin-top: 12px;
}

.asset-change-hero {
  padding: 16px 18px;
  border: 1px solid rgba(123, 231, 255, 0.12);
  border-radius: var(--asset-radius-card, 16px);
  background:
    radial-gradient(circle at top left, rgba(123, 231, 255, 0.12), transparent 42%),
    linear-gradient(160deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02));
}

.asset-change-eyebrow {
  display: inline-flex;
  margin-bottom: 10px;
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.12);
  color: rgba(226, 244, 255, 0.88);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.asset-change-hero strong {
  display: block;
  margin-bottom: 8px;
  color: #f5fbff;
  font-size: 18px;
  line-height: 1.45;
}

.asset-change-hero p {
  margin: 0;
  color: rgba(219, 229, 240, 0.7);
  line-height: 1.6;
}

.asset-change-step-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  align-items: stretch;
  gap: 10px;
}

.asset-change-step {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 8px;
  padding: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--asset-radius-card, 16px);
  background: rgba(10, 16, 26, 0.82);
}

.asset-change-step.up {
  border-color: rgba(239, 68, 68, 0.22);
}

.asset-change-step.dn {
  border-color: rgba(34, 197, 94, 0.2);
}

.asset-change-step.accent {
  border-color: rgba(141, 146, 255, 0.28);
}

.asset-change-step-label {
  color: rgba(219, 229, 240, 0.66);
  font-size: 11px;
}

.asset-change-step strong {
  display: block;
  min-width: 0;
  max-width: 100%;
  color: #f5fbff;
  font-size: clamp(15px, 1.7vw, 18px);
  line-height: 1.3;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.asset-change-step.up strong {
  color: var(--asset-positive, #ef4444);
}

.asset-change-step.dn strong {
  color: var(--asset-negative, #22c55e);
}

.asset-change-step.accent strong {
  color: #b3b6ff;
}

.asset-change-step small {
  min-width: 0;
  color: rgba(219, 229, 240, 0.56);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.asset-change-equation {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--asset-radius-card, 16px);
  background: rgba(9, 15, 24, 0.78);
  color: rgba(219, 229, 240, 0.84);
}

.asset-change-equation b {
  color: rgba(219, 229, 240, 0.4);
  font-size: 14px;
}

.asset-change-equation strong {
  color: #f5fbff;
}

.asset-change-source-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.asset-change-source-card {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--asset-radius-card, 16px);
  background: rgba(8, 14, 22, 0.72);
}

.asset-change-source-card header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.asset-change-source-card header div {
  display: grid;
  gap: 6px;
}

.asset-change-source-card header strong {
  color: #f5fbff;
  font-size: 18px;
}

.asset-change-source-card header small {
  color: rgba(219, 229, 240, 0.56);
  line-height: 1.5;
  text-align: right;
}

.asset-change-source-kicker {
  color: rgba(219, 229, 240, 0.66);
  font-size: 11px;
}

.asset-breakdown-list {
  display: grid;
  gap: 10px;
}

.asset-breakdown-row {
  display: grid;
  gap: 6px;
}

.asset-breakdown-row-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.asset-breakdown-row-head span {
  color: rgba(219, 229, 240, 0.82);
  font-size: 12px;
}

.asset-breakdown-row-head strong {
  color: #f5fbff;
  font-size: 13px;
}

.asset-breakdown-bar-track {
  overflow: hidden;
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
}

.asset-breakdown-bar-fill {
  height: 100%;
  min-width: 4px;
  border-radius: inherit;
  background: rgba(123, 231, 255, 0.66);
}

.asset-breakdown-bar-fill.up {
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.54), rgba(239, 68, 68, 0.9));
}

.asset-breakdown-bar-fill.dn {
  background: linear-gradient(90deg, rgba(34, 197, 94, 0.5), rgba(34, 197, 94, 0.88));
}

.asset-breakdown-bar-fill.neutral {
  background: linear-gradient(90deg, rgba(123, 231, 255, 0.52), rgba(123, 231, 255, 0.88));
}

.asset-breakdown-row small {
  color: rgba(219, 229, 240, 0.54);
  line-height: 1.45;
}

.asset-change-insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.asset-change-insight-card {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--asset-radius-card, 16px);
  background: rgba(8, 14, 22, 0.7);
}

.asset-change-insight-card header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.asset-change-insight-card header span {
  color: rgba(219, 229, 240, 0.66);
  font-size: 11px;
}

.asset-change-insight-card header strong {
  color: #f5fbff;
  font-size: 18px;
}

.asset-change-insight-card p {
  margin: 0;
  color: rgba(219, 229, 240, 0.7);
  line-height: 1.6;
}

.asset-change-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.asset-change-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(230, 241, 250, 0.9);
  font-size: 11px;
  font-weight: 600;
}

.asset-change-pill.neutral {
  border-color: rgba(123, 231, 255, 0.16);
  background: rgba(123, 231, 255, 0.08);
}

.asset-change-pill.warm {
  border-color: rgba(255, 207, 120, 0.18);
  background: rgba(255, 207, 120, 0.1);
}

.asset-change-pill.success {
  border-color: rgba(239, 68, 68, 0.22);
  background: rgba(239, 68, 68, 0.1);
}

.asset-change-pill.risk {
  border-color: rgba(34, 197, 94, 0.22);
  background: rgba(34, 197, 94, 0.1);
}

.asset-change-pill.accent {
  border-color: rgba(141, 146, 255, 0.22);
  background: rgba(141, 146, 255, 0.1);
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

.asset-overview-secondary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.asset-preview-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.asset-preview-grid-single {
  grid-template-columns: 1fr;
}

:deep(.asset-tooltip-title) {
  margin-bottom: 8px;
  color: #f5fbff;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 1180px) {
  .asset-change-source-grid,
  .asset-change-step-grid,
  .asset-change-insight-grid,
  .asset-overview-secondary-grid,
  .asset-preview-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .asset-chart-performance,
  .asset-chart-waterfall,
  .asset-chart-contributors,
  .asset-chart-heatmap {
    min-height: 240px;
  }
}

@media (max-width: 768px) {
  .asset-overview {
    padding: 12px;
  }

  .asset-card-head,
  .asset-change-source-card header,
  .asset-change-insight-card header {
    display: grid;
  }

  .asset-change-head {
    justify-content: flex-start;
  }
}
</style>
