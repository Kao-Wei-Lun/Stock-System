<template>
  <section class="workspace-page review-page">
    <div class="workspace-hero">
      <div>
        <div class="workspace-kicker">Journal, Backtest & Assets</div>
        <h1>把盤中的決策痕跡，轉成可回顧、可比較，也可量化的資產紀律。</h1>
      </div>
      <div class="workspace-hero-meta">
        <div class="hero-stat">
          <span>目前標的</span>
          <strong>{{ currentTicker }}</strong>
        </div>
        <button class="hero-action" type="button" @click="$emit('open-terminal')">
          回到終端
        </button>
      </div>
    </div>

    <div class="review-tabs">
      <button
        class="review-tab"
        :class="{ active: normalizedTab === 'journal' }"
        type="button"
        @click="$emit('set-right-tab', 'journal')"
      >
        交易日誌
      </button>
      <button
        class="review-tab"
        :class="{ active: normalizedTab === 'backtest' }"
        type="button"
        @click="$emit('set-right-tab', 'backtest')"
      >
        系統回測
      </button>
      <button
        class="review-tab"
        :class="{ active: normalizedTab === 'assets' }"
        type="button"
        @click="$emit('set-right-tab', 'assets')"
      >
        資產追蹤
      </button>
    </div>

    <div class="review-stage">
      <div class="review-main-card">
        <JournalPanel
          v-if="normalizedTab === 'journal'"
          :journal-form="journalForm"
          :journal-entries="journalEntries"
          :journal-stats="journalStats"
          :journal-loading="journalLoading"
          :journal-filter-presets="journalFilterPresets"
          :journal-filter-scope="journalFilterScope"
          :journal-filters="journalFilters"
          v-model:showAllJournalEntries="showAllJournalEntries"
          v-model:editingJournalPresetId="editingJournalPresetId"
          v-model:journalPresetName="journalPresetName"
          v-model:journalPresetDescription="journalPresetDescription"
          :formatDateTime="formatDateTime"
          @update-journal-field="$emit('update-journal-field', $event)"
          @update-journal-filter="$emit('update-journal-filter', $event)"
          @apply-journal-filter-preset="$emit('apply-journal-filter-preset', $event)"
          @save-journal-filter-preset="$emit('save-journal-filter-preset', $event)"
          @load-journal-filter-preset="$emit('load-journal-filter-preset', $event)"
          @delete-journal-filter-preset="$emit('delete-journal-filter-preset', $event)"
          @save-journal-entry="$emit('save-journal-entry')"
          @delete-journal-entry="$emit('delete-journal-entry', $event)"
          @select-journal-entry="$emit('select-journal-entry', $event)"
          @reset-journal-form="$emit('reset-journal-form')"
          @add-journal-attachment="$emit('add-journal-attachment')"
          @remove-journal-attachment="$emit('remove-journal-attachment', $event)"
          @create-watch-group="$emit('create-watch-group', $event)"
          @add-watchlist="$emit('add-watchlist', $event)"
          @open-alert-modal="$emit('open-alert-modal', $event)"
        />

        <BacktestPanel
          v-else-if="normalizedTab === 'backtest'"
          :backtest-form="backtestForm"
          :backtest-result="backtestResult"
          :backtest-loading="backtestLoading"
          :backtest-history="backtestHistory"
          :formatPct="formatPct"
          :formatPositionSizing="formatPositionSizing"
          :backtestEquityPath="backtestEquityPath"
          :backtestTradeRows="backtestTradeRows"
          :backtestHistoryRows="backtestHistoryRows"
          :backtestCompareRows="backtestCompareRows"
          :isBacktestRunCompared="isBacktestRunCompared"
          @update-backtest-field="$emit('update-backtest-field', $event)"
          @run-backtest="$emit('run-backtest')"
          @load-backtest="$emit('load-backtest', $event)"
          @toggle-backtest-compare="$emit('toggle-backtest-compare', $event)"
          @clear-backtest-compare="$emit('clear-backtest-compare')"
        />

        <AssetTrackingPanel
          v-else
          :current-ticker="currentTicker"
          :asset-loading="assetLoading"
          :asset-performance-range="assetPerformanceRange"
          :asset-base-currency="assetBaseCurrency"
          :asset-summary="assetSummary"
          :asset-accounts="assetAccounts"
          :asset-accounts-summary="assetAccountsSummary"
          :asset-holdings="assetHoldings"
          :asset-warnings="assetWarnings"
          :asset-quote-gaps="assetQuoteGaps"
          :asset-reconciliation="assetReconciliation"
          :asset-price-overrides="assetPriceOverrides"
          :asset-fx-rates="assetFxRates"
          :asset-adjustments="assetAdjustments"
          :asset-performance-summary="assetPerformanceSummary"
          :asset-performance-series="assetPerformanceSeries"
          :asset-monthly-heatmap="assetMonthlyHeatmap"
          :asset-realized-vs-unrealized="assetRealizedVsUnrealized"
          :asset-alerts="assetAlerts"
          :asset-trade-import-result="assetTradeImportResult"
          :asset-cash-import-result="assetCashImportResult"
          :asset-journal-import-preview="assetJournalImportPreview"
          :asset-last-recompute="assetLastRecompute"
          :asset-account-allocation="assetAccountAllocation"
          :asset-market-allocation="assetMarketAllocation"
          :asset-contributors="assetContributors"
          :asset-cash-entries="assetCashEntries"
          :asset-trade-entries="assetTradeEntries"
          :asset-reconciliation-entries="assetReconciliationEntries"
          :asset-account-form="assetAccountForm"
          :asset-cash-form="assetCashForm"
          :asset-trade-form="assetTradeForm"
          :asset-reconciliation-form="assetReconciliationForm"
          :asset-price-override-form="assetPriceOverrideForm"
          :asset-fx-rate-form="assetFxRateForm"
          :asset-adjustment-form="assetAdjustmentForm"
          :asset-trade-import-form="assetTradeImportForm"
          :asset-cash-import-form="assetCashImportForm"
          :asset-journal-import-form="assetJournalImportForm"
          @reload-asset-data="$emit('reload-asset-data')"
          @set-asset-performance-range="$emit('set-asset-performance-range', $event)"
          @edit-asset-account="$emit('edit-asset-account', $event)"
          @update-asset-account-field="$emit('update-asset-account-field', $event)"
          @update-asset-cash-field="$emit('update-asset-cash-field', $event)"
          @update-asset-trade-field="$emit('update-asset-trade-field', $event)"
          @update-asset-reconciliation-field="$emit('update-asset-reconciliation-field', $event)"
          @update-asset-price-override-field="$emit('update-asset-price-override-field', $event)"
          @update-asset-fx-rate-field="$emit('update-asset-fx-rate-field', $event)"
          @update-asset-adjustment-field="$emit('update-asset-adjustment-field', $event)"
          @update-asset-trade-import-field="$emit('update-asset-trade-import-field', $event)"
          @update-asset-cash-import-field="$emit('update-asset-cash-import-field', $event)"
          @update-asset-journal-import-field="$emit('update-asset-journal-import-field', $event)"
          @save-asset-account="$emit('save-asset-account')"
          @save-asset-cash-entry="$emit('save-asset-cash-entry')"
          @save-asset-trade-entry="$emit('save-asset-trade-entry')"
          @save-asset-reconciliation="$emit('save-asset-reconciliation')"
          @save-asset-price-override="$emit('save-asset-price-override')"
          @save-asset-fx-rate="$emit('save-asset-fx-rate')"
          @save-asset-adjustment="$emit('save-asset-adjustment')"
          @import-asset-trades-csv="$emit('import-asset-trades-csv', $event)"
          @import-asset-cash-csv="$emit('import-asset-cash-csv', $event)"
          @preview-asset-journal-import="$emit('preview-asset-journal-import')"
          @import-asset-journal="$emit('import-asset-journal')"
          @recompute-asset-tracking="$emit('recompute-asset-tracking')"
          @reset-asset-account-form="$emit('reset-asset-account-form')"
          @reset-asset-cash-form="$emit('reset-asset-cash-form')"
          @reset-asset-trade-form="$emit('reset-asset-trade-form')"
          @reset-asset-reconciliation-form="$emit('reset-asset-reconciliation-form')"
          @reset-asset-price-override-form="$emit('reset-asset-price-override-form')"
          @reset-asset-fx-rate-form="$emit('reset-asset-fx-rate-form')"
          @reset-asset-adjustment-form="$emit('reset-asset-adjustment-form')"
          @reset-asset-import-forms="$emit('reset-asset-import-forms')"
          @reset-asset-journal-import-form="$emit('reset-asset-journal-import-form')"
          @edit-asset-cash-entry="$emit('edit-asset-cash-entry', $event)"
          @edit-asset-trade-entry="$emit('edit-asset-trade-entry', $event)"
          @edit-asset-price-override="$emit('edit-asset-price-override', $event)"
          @edit-asset-fx-rate="$emit('edit-asset-fx-rate', $event)"
          @edit-asset-adjustment="$emit('edit-asset-adjustment', $event)"
          @delete-asset-account="$emit('delete-asset-account', $event)"
          @delete-asset-cash-entry="$emit('delete-asset-cash-entry', $event)"
          @delete-asset-trade-entry="$emit('delete-asset-trade-entry', $event)"
          @delete-asset-reconciliation="$emit('delete-asset-reconciliation', $event)"
          @delete-asset-price-override="$emit('delete-asset-price-override', $event)"
          @delete-asset-fx-rate="$emit('delete-asset-fx-rate', $event)"
          @delete-asset-adjustment="$emit('delete-asset-adjustment', $event)"
        />
      </div>

      <aside class="review-side-card">
        <div class="review-side-kicker">Workflow Focus</div>
        <div class="review-side-title">{{ reviewSideTitle }}</div>
        <p class="review-side-copy">{{ reviewSideCopy }}</p>
        <div class="review-side-metric">
          <span>右下 Toast</span>
          <strong>維持全域顯示</strong>
        </div>
        <div class="review-side-metric">
          <span>切換終端</span>
          <strong>一鍵返回 {{ currentTicker }}</strong>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";

import AssetTrackingPanel from "../AssetTrackingPanel.vue";
import BacktestPanel from "../BacktestPanel.vue";
import JournalPanel from "../JournalPanel.vue";

const props = defineProps({
  rightTab: { type: String, default: "journal" },
  currentTicker: { type: String, required: true },
  backtestForm: { type: Object, required: true },
  backtestResult: { type: Object, default: null },
  backtestHistory: { type: Array, default: () => [] },
  backtestCompareIds: { type: Array, default: () => [] },
  backtestCompareRuns: { type: Array, default: () => [] },
  backtestLoading: { type: Boolean, required: true },
  journalForm: { type: Object, required: true },
  journalEntries: { type: Array, default: () => [] },
  journalStats: { type: Object, default: null },
  journalLoading: { type: Boolean, required: true },
  journalFilterPresets: { type: Array, default: () => [] },
  journalFilterScope: { type: String, required: true },
  journalFilters: { type: Object, required: true },
  assetLoading: { type: Boolean, required: true },
  assetPerformanceRange: { type: String, default: "1y" },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetAccounts: { type: Array, default: () => [] },
  assetAccountsSummary: { type: Array, default: () => [] },
  assetHoldings: { type: Array, default: () => [] },
  assetWarnings: { type: Array, default: () => [] },
  assetQuoteGaps: { type: Array, default: () => [] },
  assetReconciliation: { type: Object, default: () => ({ items: [], summary: {} }) },
  assetPriceOverrides: { type: Array, default: () => [] },
  assetFxRates: { type: Array, default: () => [] },
  assetAdjustments: { type: Array, default: () => [] },
  assetPerformanceSummary: { type: Object, default: () => ({}) },
  assetPerformanceSeries: { type: Array, default: () => [] },
  assetMonthlyHeatmap: { type: Array, default: () => [] },
  assetRealizedVsUnrealized: { type: Array, default: () => [] },
  assetAlerts: { type: Array, default: () => [] },
  assetTradeImportResult: { type: Object, default: null },
  assetCashImportResult: { type: Object, default: null },
  assetJournalImportPreview: { type: Object, default: null },
  assetLastRecompute: { type: Object, default: null },
  assetAccountAllocation: { type: Array, default: () => [] },
  assetMarketAllocation: { type: Array, default: () => [] },
  assetContributors: { type: Object, default: () => ({ top_gainers: [], top_losers: [] }) },
  assetCashEntries: { type: Array, default: () => [] },
  assetTradeEntries: { type: Array, default: () => [] },
  assetReconciliationEntries: { type: Array, default: () => [] },
  assetAccountForm: { type: Object, required: true },
  assetCashForm: { type: Object, required: true },
  assetTradeForm: { type: Object, required: true },
  assetReconciliationForm: { type: Object, required: true },
  assetPriceOverrideForm: { type: Object, required: true },
  assetFxRateForm: { type: Object, required: true },
  assetAdjustmentForm: { type: Object, required: true },
  assetTradeImportForm: { type: Object, required: true },
  assetCashImportForm: { type: Object, required: true },
  assetJournalImportForm: { type: Object, required: true },
});

defineEmits([
  "open-terminal",
  "set-right-tab",
  "update-backtest-field",
  "run-backtest",
  "load-backtest",
  "toggle-backtest-compare",
  "clear-backtest-compare",
  "update-journal-field",
  "update-journal-filter",
  "apply-journal-filter-preset",
  "save-journal-filter-preset",
  "load-journal-filter-preset",
  "delete-journal-filter-preset",
  "save-journal-entry",
  "delete-journal-entry",
  "select-journal-entry",
  "reset-journal-form",
  "add-journal-attachment",
  "remove-journal-attachment",
  "create-watch-group",
  "add-watchlist",
  "open-alert-modal",
  "reload-asset-data",
  "set-asset-performance-range",
  "edit-asset-account",
  "update-asset-account-field",
  "update-asset-cash-field",
  "update-asset-trade-field",
  "update-asset-reconciliation-field",
  "update-asset-price-override-field",
  "update-asset-fx-rate-field",
  "update-asset-adjustment-field",
  "update-asset-trade-import-field",
  "update-asset-cash-import-field",
  "update-asset-journal-import-field",
  "save-asset-account",
  "save-asset-cash-entry",
  "save-asset-trade-entry",
  "save-asset-reconciliation",
  "save-asset-price-override",
  "save-asset-fx-rate",
  "save-asset-adjustment",
  "import-asset-trades-csv",
  "import-asset-cash-csv",
  "preview-asset-journal-import",
  "import-asset-journal",
  "recompute-asset-tracking",
  "reset-asset-account-form",
  "reset-asset-cash-form",
  "reset-asset-trade-form",
  "reset-asset-reconciliation-form",
  "reset-asset-price-override-form",
  "reset-asset-fx-rate-form",
  "reset-asset-adjustment-form",
  "reset-asset-import-forms",
  "reset-asset-journal-import-form",
  "edit-asset-cash-entry",
  "edit-asset-trade-entry",
  "edit-asset-price-override",
  "edit-asset-fx-rate",
  "edit-asset-adjustment",
  "delete-asset-account",
  "delete-asset-cash-entry",
  "delete-asset-trade-entry",
  "delete-asset-reconciliation",
  "delete-asset-price-override",
  "delete-asset-fx-rate",
  "delete-asset-adjustment",
]);

const normalizedTab = computed(() => {
  if (props.rightTab === "backtest") return "backtest";
  if (props.rightTab === "assets") return "assets";
  return "journal";
});
const journalPresetName = ref("");
const journalPresetDescription = ref("");
const editingJournalPresetId = ref(null);
const showAllJournalEntries = ref(false);

const reviewSideTitle = computed(() => ({
  journal: "盤後復盤",
  backtest: "策略驗證",
  assets: "資產現值",
}[normalizedTab.value] || "盤後復盤"));

const reviewSideCopy = computed(() => ({
  journal: "保留完整的交易上下文、情緒與標籤，回顧決策品質與市場情境。",
  backtest: "把回測結果、權益曲線與歷史比較放在同一頁，快速看出策略是否值得繼續打磨。",
  assets: "讓手動輸入的現金與交易流水，立即轉成持倉、市值、已實現與未實現損益，每次補記錄後都能看到總資產如何變化。",
}[normalizedTab.value] || ""));

function buildSparklinePath(points) {
  if (!Array.isArray(points) || points.length < 2) return "";
  const values = points.map((item) => Number(item?.equity ?? 0)).filter((value) => Number.isFinite(value));
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 240;
  const height = 90;
  const xStep = width / Math.max(values.length - 1, 1);
  return values.map((value, index) => {
    const x = Number((index * xStep).toFixed(2));
    const ratio = max === min ? 0.5 : (value - min) / (max - min);
    const y = Number((height - (ratio * (height - 12)) - 6).toFixed(2));
    return `${index === 0 ? "M" : "L"}${x} ${y}`;
  }).join(" ");
}

function formatPct(value) {
  if (value == null || value === "") return "—";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatPositionSizing(value) {
  const labels = {
    full_equity: "100% 資金",
    half_equity: "50% 資金",
    quarter_equity: "25% 資金",
  };
  return labels[String(value || "full_equity")] || String(value || "100% 資金");
}

function isBacktestRunCompared(runId) {
  return (props.backtestCompareIds || []).some((id) => String(id) === String(runId));
}

function formatDateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("zh-TW", { hour12: false });
}

const backtestEquityPath = computed(() => buildSparklinePath(props.backtestResult?.equity_curve || []));
const backtestTradeRows = computed(() => (props.backtestResult?.trades || []).slice(-5).reverse());
const backtestHistoryRows = computed(() => (props.backtestHistory || []).slice(0, 8));
const backtestCompareRows = computed(() => (props.backtestCompareRuns || []).slice(0, 3));
</script>

<style scoped>
.workspace-page {
  height: 100%;
  overflow: auto;
  padding: 18px;
}

.review-page {
  background:
    radial-gradient(circle at top left, rgba(0, 217, 163, 0.06), transparent 26%),
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
  background: linear-gradient(135deg, rgba(7, 26, 20, 0.5), rgba(10, 16, 26, 0.96));
}

.workspace-kicker {
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
  border: 1px solid rgba(0, 217, 163, 0.24);
  border-radius: 999px;
  background: rgba(0, 217, 163, 0.12);
  color: #c6fff0;
  cursor: pointer;
  font-size: 11px;
}

.review-tabs {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

.review-tab {
  padding: 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  font-size: 11px;
}

.review-tab.active {
  border-color: rgba(0, 217, 163, 0.24);
  background: rgba(0, 217, 163, 0.12);
  color: #c6fff0;
}

.review-stage {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 18px;
  margin-top: 18px;
  align-items: start;
}

.review-main-card,
.review-side-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  background: rgba(6, 10, 18, 0.72);
  overflow: hidden;
}

.review-main-card :deep(.rp-content),
.review-main-card :deep(.asset-shell) {
  padding: 18px;
}

.review-side-card {
  padding: 18px;
}

.review-side-kicker {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text3);
}

.review-side-title {
  margin-top: 8px;
  font-family: "Syne", sans-serif;
  font-size: 22px;
  line-height: 1.1;
}

.review-side-copy {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--text2);
}

.review-side-metric {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.review-side-metric span {
  display: block;
  font-size: 10px;
  color: var(--text3);
}

.review-side-metric strong {
  display: block;
  margin-top: 4px;
  font-size: 14px;
  color: var(--text1);
}

@media (max-width: 1180px) {
  .review-stage {
    grid-template-columns: 1fr;
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

  .workspace-hero-meta,
  .review-tabs {
    flex-wrap: wrap;
  }
}
</style>
