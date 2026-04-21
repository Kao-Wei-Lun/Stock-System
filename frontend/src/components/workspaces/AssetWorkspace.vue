<template>
  <section class="workspace-page asset-page">
    <div class="workspace-hero">
      <div>
        <div class="workspace-kicker">Personal Assets</div>
        <h1>把持倉、現金流、估值與對帳放進同一個日常資產工作台。</h1>
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

    <div class="asset-tabs">
      <button class="asset-tab" :class="{ active: activeTab === 'overview' }" type="button" @click="activeTab = 'overview'">
        總覽
      </button>
      <button class="asset-tab" :class="{ active: activeTab === 'holdings' }" type="button" @click="activeTab = 'holdings'">
        持倉與流水
      </button>
      <button class="asset-tab" :class="{ active: activeTab === 'maintenance' }" type="button" @click="activeTab = 'maintenance'">
        資料維護
      </button>
    </div>

    <div class="asset-stage">
      <div class="asset-main-card">
        <AssetOverviewPanel
          v-if="activeTab === 'overview'"
          :asset-performance-range="assetPerformanceRange"
          :asset-base-currency="assetBaseCurrency"
          :asset-summary="assetSummary"
          :asset-warnings="assetWarnings"
          :asset-quote-gaps="assetQuoteGaps"
          :asset-reconciliation="assetReconciliation"
          :asset-performance-summary="assetPerformanceSummary"
          :asset-performance-series="assetPerformanceSeries"
          :asset-monthly-heatmap="assetMonthlyHeatmap"
          :asset-alerts="assetAlerts"
          :asset-account-allocation="assetAccountAllocation"
          :asset-market-allocation="assetMarketAllocation"
          :asset-contributors="assetContributors"
          :asset-holdings="assetHoldings"
          :asset-cash-entries="assetCashEntries"
          :asset-trade-entries="assetTradeEntries"
          @set-asset-performance-range="$emit('set-asset-performance-range', $event)"
          @open-tab="openTab"
          @focus-holdings="focusHoldings"
        />

        <AssetHoldingsFlowsPanel
          v-else-if="activeTab === 'holdings'"
          :asset-base-currency="assetBaseCurrency"
          :asset-accounts-summary="assetAccountsSummary"
          :asset-holdings="assetHoldings"
          :asset-cash-entries="assetCashEntries"
          :asset-trade-entries="assetTradeEntries"
          :asset-filter="holdingsFilter"
          @open-tab="openTab"
          @clear-filter="resetHoldingsFilter"
        />

        <AssetTrackingPanel
          v-else
          panel-mode="maintenance"
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

      <aside class="asset-side-card">
        <div class="asset-side-kicker">Daily Focus</div>
        <div class="asset-side-title">{{ sideTitle }}</div>
        <p class="asset-side-copy">
          {{ sideCopy }}
        </p>
        <div class="asset-side-metric">
          <span>基準幣別</span>
          <strong>{{ assetBaseCurrency }}</strong>
        </div>
        <div class="asset-side-metric">
          <span>追蹤帳戶</span>
          <strong>{{ assetAccountsSummary.length }}</strong>
        </div>
        <div class="asset-side-metric">
          <span>目前持倉</span>
          <strong>{{ assetHoldings.length }}</strong>
        </div>
        <div class="asset-side-metric">
          <span>待處理提醒</span>
          <strong>{{ assetIssueCount }}</strong>
        </div>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";

import AssetHoldingsFlowsPanel from "../assets/AssetHoldingsFlowsPanel.vue";
import AssetOverviewPanel from "../assets/AssetOverviewPanel.vue";
import AssetTrackingPanel from "../AssetTrackingPanel.vue";

const props = defineProps({
  currentTicker: { type: String, required: true },
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

const activeTab = ref("overview");
const holdingsFilter = ref({
  accountKey: "",
  marketKey: "",
  ticker: "",
  month: "",
});

const assetIssueCount = computed(() => {
  const reconciliationItems = props.assetReconciliation?.items || [];
  const gapCount = reconciliationItems.filter((item) => item?.has_gap).length;
  return props.assetWarnings.length + props.assetQuoteGaps.length + props.assetAlerts.length + gapCount;
});

const sideTitle = computed(() => ({
  overview: "資產總覽",
  holdings: "持倉與流水",
  maintenance: "資料維護",
}[activeTab.value] || "個人資產"));

const sideCopy = computed(() => ({
  overview: "先看資產變化、績效與主要風險，再決定要不要深入查看明細。",
  holdings: "把帳戶摘要、目前持倉與最近流水集中在同一頁，方便追查資產來源。",
  maintenance: "所有手動輸入、匯入、對帳與例外修正都收在這一層，避免干擾日常查看。",
}[activeTab.value] || ""));

function openTab(tab) {
  activeTab.value = tab;
}

function resetHoldingsFilter() {
  holdingsFilter.value = {
    accountKey: "",
    marketKey: "",
    ticker: "",
    month: "",
  };
}

function focusHoldings(filter = {}) {
  holdingsFilter.value = {
    accountKey: filter.accountKey || "",
    marketKey: filter.marketKey || "",
    ticker: filter.ticker || "",
    month: filter.month || "",
  };
  activeTab.value = "holdings";
}
</script>

<style scoped>
.workspace-page {
  height: 100%;
  overflow: auto;
  padding: 18px;
}

.asset-page {
  background:
    radial-gradient(circle at top right, rgba(93, 211, 158, 0.1), transparent 28%),
    linear-gradient(180deg, rgba(8, 14, 22, 0.98), rgba(9, 15, 24, 0.98));
}

.workspace-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 22px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(16, 28, 43, 0.92), rgba(8, 18, 29, 0.92));
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.24);
}

.workspace-kicker {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: rgba(147, 232, 193, 0.78);
  margin-bottom: 8px;
}

.workspace-hero h1 {
  margin: 0;
  max-width: 760px;
  font-size: 28px;
  line-height: 1.18;
  color: #f4fbff;
}

.workspace-hero-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}

.hero-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 140px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(231, 243, 255, 0.84);
}

.hero-stat span {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.hero-stat strong {
  font-size: 18px;
}

.hero-action {
  border: 1px solid rgba(147, 232, 193, 0.4);
  background: linear-gradient(135deg, rgba(93, 211, 158, 0.22), rgba(17, 92, 63, 0.16));
  color: #f5fffa;
  padding: 10px 14px;
  border-radius: 999px;
  font-weight: 600;
  cursor: pointer;
}

.asset-stage {
  margin-top: 18px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 16px;
  align-items: start;
}

.asset-tabs {
  margin-top: 18px;
  display: flex;
  gap: 10px;
}

.asset-tab {
  padding: 10px 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: rgba(219, 229, 240, 0.82);
  cursor: pointer;
}

.asset-tab.active {
  border-color: rgba(147, 232, 193, 0.44);
  background: rgba(93, 211, 158, 0.14);
  color: #f5fffa;
}

.asset-main-card,
.asset-side-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  background: rgba(7, 14, 22, 0.92);
  box-shadow: 0 14px 38px rgba(0, 0, 0, 0.2);
}

.asset-main-card :deep(.asset-shell) {
  border: 0;
  border-radius: 20px;
}

.asset-side-card {
  padding: 18px;
  position: sticky;
  top: 18px;
}

.asset-side-kicker {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: rgba(147, 232, 193, 0.74);
}

.asset-side-title {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 700;
  color: #f5fbff;
}

.asset-side-copy {
  margin: 10px 0 0;
  color: rgba(219, 229, 240, 0.78);
  line-height: 1.6;
}

.asset-side-metric {
  margin-top: 14px;
  padding: 12px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: rgba(219, 229, 240, 0.74);
}

.asset-side-metric strong {
  color: #f5fbff;
  font-size: 16px;
}

@media (max-width: 1200px) {
  .asset-stage {
    grid-template-columns: 1fr;
  }

  .asset-side-card {
    position: static;
  }
}

@media (max-width: 900px) {
  .workspace-hero {
    flex-direction: column;
    align-items: stretch;
  }

  .workspace-hero h1 {
    font-size: 24px;
  }

  .asset-tabs,
  .workspace-hero-meta {
    flex-wrap: wrap;
    align-items: stretch;
  }
}
</style>
