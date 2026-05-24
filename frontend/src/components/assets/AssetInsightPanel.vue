<template>
  <aside class="asset-insight-panel" aria-label="資產提醒">
    <header class="asset-insight-head">
      <div>
        <span>Insight Panel</span>
        <strong>資產提醒</strong>
      </div>
      <em>{{ insightItems.length }}</em>
    </header>

    <div class="asset-insight-summary">
      <div>
        <span>現金水位</span>
        <strong :class="cashRatioTone">{{ cashRatioLabel }}</strong>
      </div>
      <div>
        <span>持倉集中度</span>
        <strong :class="concentrationTone">{{ concentrationLabel }}</strong>
      </div>
    </div>

    <div v-if="insightItems.length" class="asset-insight-list">
      <article v-for="item in insightItems" :key="item.key" class="asset-insight-item" :class="item.tone">
        <span>{{ item.type }}</span>
        <strong>{{ item.title }}</strong>
        <p>{{ item.message }}</p>
      </article>
    </div>
    <div v-else class="asset-insight-empty">
      目前沒有需要特別注意的資產提醒
    </div>
  </aside>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetHoldings: { type: Array, default: () => [] },
  assetWarnings: { type: Array, default: () => [] },
  assetQuoteGaps: { type: Array, default: () => [] },
  assetReconciliation: { type: Object, default: () => ({ items: [], summary: {} }) },
  assetAlerts: { type: Array, default: () => [] },
});

const reconciliationGapItems = computed(() => (
  (props.assetReconciliation?.items || []).filter((item) => item?.has_gap)
));

const totalAssetValue = computed(() => parseFiniteNumber(props.assetSummary?.total_asset_value_base));
const cashTotal = computed(() => parseFiniteNumber(props.assetSummary?.cash_total_base));

const cashRatio = computed(() => {
  if (cashTotal.value == null || totalAssetValue.value == null || totalAssetValue.value === 0) return null;
  return (cashTotal.value / totalAssetValue.value) * 100;
});

const cashRatioTone = computed(() => {
  if (cashRatio.value == null) return "neutral";
  if (cashRatio.value < 10) return "warning";
  return "neutral";
});

const cashRatioLabel = computed(() => (cashRatio.value == null ? "--" : `${cashRatio.value.toFixed(2)}%`));

const heaviestHolding = computed(() => (
  [...(props.assetHoldings || [])]
    .sort((left, right) => Number(right?.market_value_base || 0) - Number(left?.market_value_base || 0))[0] || null
));

const concentrationPct = computed(() => {
  const value = parseFiniteNumber(heaviestHolding.value?.market_value_base);
  if (value == null || totalAssetValue.value == null || totalAssetValue.value === 0) return null;
  return (value / totalAssetValue.value) * 100;
});

const concentrationTone = computed(() => {
  if (concentrationPct.value == null) return "neutral";
  if (concentrationPct.value >= 30) return "warning";
  return "neutral";
});

const concentrationLabel = computed(() => (
  concentrationPct.value == null ? "--" : `${concentrationPct.value.toFixed(2)}%`
));

const insightItems = computed(() => {
  const items = [];

  (props.assetAlerts || []).forEach((alert, index) => {
    if (!alert?.title && !alert?.message) return;
    items.push({
      key: `alert-${alert.code || index}`,
      type: alert.level === "info" ? "資訊" : "提醒",
      title: alert.title || "資產提醒",
      message: alert.message || "",
      tone: alert.level === "info" ? "info" : "warning",
    });
  });

  (props.assetWarnings || []).forEach((warning, index) => {
    if (!warning) return;
    items.push({
      key: `warning-${index}`,
      type: "資料",
      title: "資產資料提醒",
      message: String(warning),
      tone: "warning",
    });
  });

  if ((props.assetQuoteGaps || []).length) {
    const sample = props.assetQuoteGaps.slice(0, 3).map((item) => item?.ticker).filter(Boolean).join("、");
    items.push({
      key: "quote-gaps",
      type: "估值",
      title: "部分持倉缺少最新估值",
      message: `${props.assetQuoteGaps.length} 檔標的暫時缺少報價${sample ? `：${sample}` : ""}。`,
      tone: "warning",
    });
  }

  if (reconciliationGapItems.value.length) {
    items.push({
      key: "reconciliation-gap",
      type: "對帳",
      title: "帳戶對帳仍有差異",
      message: `${reconciliationGapItems.value.length} 個帳戶或快照存在對帳差異，請留意現金或持倉校正。`,
      tone: "warning",
    });
  }

  if (cashRatio.value != null && cashRatio.value < 10) {
    items.push({
      key: "cash-ratio-low",
      type: "現金",
      title: "現金水位低於 10%",
      message: `目前現金約 ${props.assetBaseCurrency} ${formatNumber(cashTotal.value)}，占總資產 ${cashRatio.value.toFixed(2)}%。`,
      tone: "warning",
    });
  }

  if (concentrationPct.value != null && concentrationPct.value >= 30 && heaviestHolding.value) {
    items.push({
      key: "holding-concentration",
      type: "集中度",
      title: "單一持股權重偏高",
      message: `${heaviestHolding.value.ticker || "單一持股"} 目前約占總資產 ${concentrationPct.value.toFixed(2)}%，請留意波動風險。`,
      tone: "warning",
    });
  }

  return dedupeInsights(items).slice(0, 6);
});

function parseFiniteNumber(value) {
  if (value === "" || value == null) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatNumber(value) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return "--";
  return numeric.toLocaleString("zh-TW", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

function dedupeInsights(items) {
  const seen = new Set();
  return items.filter((item) => {
    const key = `${item.title}-${item.message}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
</script>

<style scoped>
.asset-insight-panel {
  padding: 18px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: 18px;
  background: var(--asset-card-bg, #111827);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.16);
}

.asset-insight-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.asset-insight-head div {
  display: grid;
  gap: 6px;
}

.asset-insight-head span {
  color: var(--asset-text-muted, #64748b);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.asset-insight-head strong {
  color: var(--asset-text-primary, #e5e7eb);
  font-size: 22px;
}

.asset-insight-head em {
  min-width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.14);
  color: var(--asset-info, #2563eb);
  font-style: normal;
  font-weight: 800;
}

.asset-insight-summary {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.asset-insight-summary div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--asset-border, #1f2937);
}

.asset-insight-summary span {
  color: var(--asset-text-secondary, #94a3b8);
}

.asset-insight-summary strong,
.asset-insight-item strong {
  color: var(--asset-text-primary, #e5e7eb);
  font-variant-numeric: tabular-nums;
}

.asset-insight-summary .warning {
  color: var(--asset-warning, #f59e0b);
}

.asset-insight-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.asset-insight-item {
  padding: 12px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.72);
}

.asset-insight-item.warning {
  border-color: rgba(245, 158, 11, 0.28);
}

.asset-insight-item.info {
  border-color: rgba(37, 99, 235, 0.3);
}

.asset-insight-item span {
  display: inline-flex;
  margin-bottom: 8px;
  color: var(--asset-text-muted, #64748b);
  font-size: 11px;
}

.asset-insight-item p {
  margin: 7px 0 0;
  color: var(--asset-text-secondary, #94a3b8);
  line-height: 1.6;
}

.asset-insight-empty {
  margin-top: 16px;
  padding: 18px 14px;
  border: 1px dashed var(--asset-border, #1f2937);
  border-radius: 14px;
  color: var(--asset-text-secondary, #94a3b8);
  line-height: 1.6;
}
</style>
