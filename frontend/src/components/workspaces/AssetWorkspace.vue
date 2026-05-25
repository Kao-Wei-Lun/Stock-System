<template>
  <section class="workspace-page asset-page">
    <div class="workspace-hero">
      <div>
        <div class="workspace-kicker">Personal Wealth</div>
        <h1>個人資產總覽</h1>
        <p>追蹤淨值、現金流、持股與投資績效</p>
      </div>
      <div class="workspace-hero-meta">
        <div class="hero-stat">
          <span>最後更新</span>
          <strong>{{ lastUpdatedLabel }}</strong>
        </div>
        <div class="asset-hero-actions">
          <button class="asset-action-btn secondary" type="button" :disabled="assetLoading" @click="$emit('reload-asset-data')">
            {{ assetLoading ? "同步中" : "同步資料" }}
          </button>
          <button class="asset-action-btn" type="button" :disabled="assetLoading" @click="$emit('recompute-asset-tracking')">
            重算資產
          </button>
          <button class="asset-action-btn ghost" type="button" @click="$emit('open-terminal')">
            回到終端
          </button>
        </div>
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
          :asset-loading="assetLoading"
          :asset-error="assetError"
          :asset-performance-range="assetPerformanceRange"
          :asset-base-currency="assetBaseCurrency"
          :asset-summary="assetSummary"
          :asset-warnings="assetWarnings"
          :asset-quote-gaps="assetQuoteGaps"
          :asset-reconciliation="assetReconciliation"
          :portfolio-calculation-metadata="portfolioCalculationMetadata"
          :portfolio-data-quality-summary="portfolioDataQualitySummary"
          :asset-performance-summary="assetPerformanceSummary"
          :performance-calculation-metadata="performanceCalculationMetadata"
          :performance-data-quality-summary="performanceDataQualitySummary"
          :asset-performance-series="assetPerformanceSeries"
          :asset-monthly-heatmap="assetMonthlyHeatmap"
          :asset-alerts="assetAlerts"
          :asset-account-allocation="assetAccountAllocation"
          :asset-market-allocation="assetMarketAllocation"
          :asset-currency-allocation="assetCurrencyAllocation"
          :asset-contributors="assetContributors"
          :asset-holdings="assetHoldings"
          :asset-cash-entries="assetCashEntries"
          :asset-trade-entries="assetTradeEntries"
          @set-asset-performance-range="$emit('set-asset-performance-range', $event)"
          @open-tab="openTab"
          @focus-holdings="focusHoldings"
          @focus-maintenance="focusMaintenance"
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

        <div v-else class="asset-maintenance-shell">
          <aside class="asset-maintenance-nav">
            <div class="asset-maintenance-nav-kicker">Maintenance</div>
            <button
              v-for="section in maintenanceNavSections"
              :key="section.key"
              class="asset-maintenance-nav-btn"
              type="button"
              @click="scrollMaintenanceSection(section.key)"
            >
              {{ section.label }}
            </button>
          </aside>

          <div ref="maintenanceContentRef" class="asset-maintenance-content">
            <AssetTrackingPanel
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
        </div>
      </div>

      <AssetInsightPanel
        class="asset-side-card"
        :asset-loading="assetLoading"
        :asset-base-currency="assetBaseCurrency"
        :asset-summary="assetSummary"
        :asset-holdings="assetHoldings"
        :asset-warnings="assetWarnings"
        :asset-quote-gaps="assetQuoteGaps"
        :asset-reconciliation="assetReconciliation"
        :portfolio-data-quality-summary="portfolioDataQualitySummary"
        :performance-data-quality-summary="performanceDataQualitySummary"
        :asset-alerts="assetAlerts"
      />
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, ref } from "vue";

import AssetHoldingsFlowsPanel from "../assets/AssetHoldingsFlowsPanel.vue";
import AssetInsightPanel from "../assets/AssetInsightPanel.vue";
import AssetOverviewPanel from "../assets/AssetOverviewPanel.vue";
import AssetTrackingPanel from "../AssetTrackingPanel.vue";

const props = defineProps({
  currentTicker: { type: String, required: true },
  assetLoading: { type: Boolean, required: true },
  assetError: { type: String, default: "" },
  assetPerformanceRange: { type: String, default: "1y" },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetAccounts: { type: Array, default: () => [] },
  assetAccountsSummary: { type: Array, default: () => [] },
  assetHoldings: { type: Array, default: () => [] },
  assetWarnings: { type: Array, default: () => [] },
  assetQuoteGaps: { type: Array, default: () => [] },
  assetReconciliation: { type: Object, default: () => ({ items: [], summary: {} }) },
  portfolioCalculationMetadata: { type: Object, default: () => ({}) },
  portfolioDataQualitySummary: { type: Object, default: null },
  assetPriceOverrides: { type: Array, default: () => [] },
  assetFxRates: { type: Array, default: () => [] },
  assetAdjustments: { type: Array, default: () => [] },
  assetPerformanceSummary: { type: Object, default: () => ({}) },
  performanceCalculationMetadata: { type: Object, default: () => ({}) },
  performanceDataQualitySummary: { type: Object, default: null },
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
  assetCurrencyAllocation: { type: Array, default: () => [] },
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
const maintenanceContentRef = ref(null);
const maintenanceNavSections = [
  { key: "accounts", label: "帳戶管理" },
  { key: "cash", label: "現金事件" },
  { key: "trades", label: "交易事件" },
  { key: "reconciliation", label: "對帳快照" },
  { key: "price-overrides", label: "價格覆蓋" },
  { key: "fx-rates", label: "FX 匯率" },
  { key: "adjustments", label: "持倉調整" },
  { key: "imports", label: "匯入工具" },
];

const lastUpdatedLabel = computed(() => (
  formatDateTime(props.assetLastRecompute?.generated_at)
  || formatDateTime(props.assetPerformanceSummary?.latest_snapshot_date)
  || "尚無資料"
));

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

function scrollMaintenanceSection(sectionKey) {
  const sectionIndexByKey = {
    accounts: 0,
    cash: 1,
    trades: 2,
    reconciliation: 3,
    "price-overrides": 4,
    "fx-rates": 5,
    adjustments: 6,
    imports: 7,
  };
  const cards = maintenanceContentRef.value?.querySelectorAll?.(".asset-card");
  const target = cards?.[sectionIndexByKey[sectionKey]];
  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

async function focusMaintenance(sectionKey = "") {
  activeTab.value = "maintenance";
  await nextTick();
  if (sectionKey) {
    scrollMaintenanceSection(sectionKey);
  }
}

function formatDateTime(value) {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleString("zh-TW", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
</script>

<style scoped>
.workspace-page {
  height: 100%;
  overflow: auto;
  padding: 18px;
}

.asset-page {
  --asset-bg: #0b111a;
  --asset-card-bg: #111827;
  --asset-card-bg-soft: #0f172a;
  --asset-border: #1f2937;
  --asset-text-primary: #e5e7eb;
  --asset-text-secondary: #94a3b8;
  --asset-text-muted: #64748b;
  --asset-positive: #ef4444;
  --asset-negative: #22c55e;
  --asset-warning: #f59e0b;
  --asset-info: #2563eb;
  --asset-radius-card: 16px;
  --asset-radius-shell: 20px;
  --asset-radius-control: 10px;
  --asset-radius-inner: 12px;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.1), transparent 30%),
    linear-gradient(180deg, rgba(11, 17, 26, 0.98), rgba(9, 15, 24, 0.98));
  color: var(--asset-text-primary);
}

.workspace-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  border: 1px solid var(--asset-border);
  border-radius: var(--asset-radius-shell);
  background: rgba(17, 24, 39, 0.88);
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.18);
}

.workspace-kicker {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--asset-text-muted);
  margin-bottom: 8px;
}

.workspace-hero h1 {
  margin: 0;
  max-width: 760px;
  font-size: 30px;
  line-height: 1.18;
  color: var(--asset-text-primary);
}

.workspace-hero p {
  margin: 8px 0 0;
  color: var(--asset-text-secondary);
  font-size: 14px;
  line-height: 1.6;
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
  min-width: 190px;
  padding: 12px 14px;
  border: 1px solid var(--asset-border);
  border-radius: var(--asset-radius-inner);
  background: rgba(15, 23, 42, 0.74);
  color: var(--asset-text-secondary);
}

.hero-stat span {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.hero-stat strong {
  color: var(--asset-text-primary);
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.asset-hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.asset-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  border: 1px solid rgba(37, 99, 235, 0.42);
  background: rgba(37, 99, 235, 0.16);
  color: var(--asset-text-primary);
  padding: 9px 13px;
  border-radius: var(--asset-radius-control);
  font-weight: 600;
  cursor: pointer;
}

.asset-action-btn.secondary {
  border-color: rgba(148, 163, 184, 0.24);
  background: rgba(15, 23, 42, 0.76);
}

.asset-action-btn.ghost {
  border-color: transparent;
  background: transparent;
  color: var(--asset-text-secondary);
}

.asset-action-btn:disabled {
  cursor: wait;
  opacity: 0.62;
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
  border: 1px solid var(--asset-border);
  border-radius: var(--asset-radius-control);
  background: rgba(15, 23, 42, 0.58);
  color: var(--asset-text-secondary);
  cursor: pointer;
}

.asset-tab.active {
  border-color: rgba(37, 99, 235, 0.42);
  background: rgba(37, 99, 235, 0.16);
  color: var(--asset-text-primary);
}

.asset-main-card,
.asset-side-card {
  min-width: 0;
  border: 1px solid var(--asset-border);
  border-radius: var(--asset-radius-shell);
  background: var(--asset-card-bg);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.16);
}

.asset-main-card :deep(.asset-shell) {
  border: 0;
  border-radius: var(--asset-radius-shell);
}

.asset-maintenance-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 0;
}

.asset-maintenance-nav {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(12, 22, 34, 0.92), rgba(7, 14, 22, 0.92));
}

.asset-maintenance-nav-kicker {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: rgba(147, 232, 193, 0.74);
  margin-bottom: 4px;
}

.asset-maintenance-nav-btn {
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--asset-radius-inner);
  background: rgba(255, 255, 255, 0.03);
  color: rgba(219, 229, 240, 0.82);
  text-align: left;
  cursor: pointer;
}

.asset-maintenance-nav-btn:hover {
  border-color: rgba(147, 232, 193, 0.26);
  background: rgba(93, 211, 158, 0.08);
}

.asset-maintenance-content {
  min-width: 0;
}

.asset-side-card {
  position: sticky;
  top: 18px;
}

.asset-page :deep(.up) {
  color: var(--asset-positive) !important;
}

.asset-page :deep(.dn) {
  color: var(--asset-negative) !important;
}

.asset-page :deep(.neutral) {
  color: var(--asset-text-secondary) !important;
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

  .asset-maintenance-shell {
    grid-template-columns: 1fr;
  }

  .asset-maintenance-nav {
    border-right: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
}

@media (max-width: 1024px) {
  .workspace-page {
    padding: 16px;
  }

  .asset-stage {
    gap: 14px;
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

@media (max-width: 768px) {
  .workspace-page {
    padding: 12px;
  }

  .workspace-hero {
    padding: 18px;
    gap: 14px;
  }

  .workspace-hero h1 {
    font-size: 22px;
  }

  .asset-hero-actions {
    align-items: center;
    justify-content: flex-start;
  }

  .asset-action-btn {
    flex: 0 1 auto;
    min-width: 118px;
    min-height: 40px;
  }

  .asset-tabs {
    overflow-x: auto;
    padding-bottom: 2px;
  }

  .asset-tab {
    flex: 0 0 auto;
  }
}
</style>
