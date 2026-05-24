<template>
  <section class="asset-kpi-section" aria-label="資產關鍵指標">
    <div v-if="assetLoading" class="asset-kpi-grid">
      <div v-for="index in 6" :key="index" class="asset-kpi-card skeleton">
        <span></span>
        <strong></strong>
        <small></small>
      </div>
    </div>
    <div v-else class="asset-kpi-grid">
      <article
        v-for="card in kpiCards"
        :key="card.key"
        class="asset-kpi-card"
        :class="[card.size, card.tone]"
        :title="card.title || card.helper"
      >
        <div class="asset-kpi-label-row">
          <span>{{ card.label }}</span>
          <em v-if="card.badge">{{ card.badge }}</em>
        </div>
        <strong>{{ card.value }}</strong>
        <small>{{ card.helper }}</small>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";

const EMPTY_MARK = "--";

const props = defineProps({
  assetLoading: { type: Boolean, default: false },
  assetPerformanceRange: { type: String, default: "1y" },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetPerformanceSummary: { type: Object, default: () => ({}) },
  assetPerformanceSeries: { type: Array, default: () => [] },
  assetHoldings: { type: Array, default: () => [] },
});

const latestPoint = computed(() => normalizedSeries.value.at(-1) || null);
const previousPoint = computed(() => normalizedSeries.value.length >= 2 ? normalizedSeries.value.at(-2) : null);

const normalizedSeries = computed(() => (
  (props.assetPerformanceSeries || [])
    .map((item) => ({
      date: String(item?.date || ""),
      total_asset_value_base: parseFiniteNumber(item?.total_asset_value_base),
    }))
    .filter((item) => item.date && item.total_asset_value_base != null)
));

const totalAssetValue = computed(() => firstFinite(
  props.assetSummary?.total_asset_value_base,
  latestPoint.value?.total_asset_value_base,
));

const totalPnl = computed(() => {
  const direct = parseFiniteNumber(props.assetSummary?.total_pnl_base);
  if (direct != null) return direct;
  const realized = parseFiniteNumber(props.assetSummary?.realized_total_base);
  const unrealized = parseFiniteNumber(props.assetSummary?.unrealized_total_base);
  if (realized == null && unrealized == null) return null;
  return Number(realized || 0) + Number(unrealized || 0);
});

const recentNetValueChange = computed(() => {
  if (!latestPoint.value || !previousPoint.value) return null;
  return latestPoint.value.total_asset_value_base - previousPoint.value.total_asset_value_base;
});

const cashRatio = computed(() => {
  const cash = parseFiniteNumber(props.assetSummary?.cash_total_base);
  const total = parseFiniteNumber(totalAssetValue.value);
  if (cash == null || total == null || total === 0) return null;
  return (cash / total) * 100;
});

const holdingCount = computed(() => {
  const direct = parseFiniteNumber(props.assetSummary?.holding_count);
  if (direct != null) return direct;
  return Array.isArray(props.assetHoldings) ? props.assetHoldings.length : null;
});

const kpiCards = computed(() => [
  {
    key: "total-assets",
    label: "總資產",
    value: formatCurrency(totalAssetValue.value),
    helper: `基準幣別 ${props.assetBaseCurrency}`,
    tone: "neutral",
    size: "featured",
  },
  {
    key: "total-pnl",
    label: "總損益",
    value: formatSignedCurrency(totalPnl.value),
    helper: "已實現 + 未實現",
    tone: toneForValue(totalPnl.value),
    size: "featured",
  },
  {
    key: "recent-change",
    label: "近一日淨值變化",
    value: recentNetValueChange.value == null ? EMPTY_MARK : formatSignedCurrency(recentNetValueChange.value),
    helper: recentNetValueChange.value == null ? "資料不足" : "由最近兩筆績效快照推估",
    title: "由最近兩筆績效快照推估，可能包含入出金、股利、匯率或重算影響。",
    tone: toneForValue(recentNetValueChange.value),
    badge: "估算",
  },
  {
    key: "cash-ratio",
    label: "現金水位",
    value: formatPercent(cashRatio.value),
    helper: `現金 ${formatCurrency(props.assetSummary?.cash_total_base)}`,
    tone: cashRatio.value != null && cashRatio.value < 10 ? "warning" : "neutral",
  },
  {
    key: "holding-count",
    label: "持有檔數",
    value: holdingCount.value == null ? EMPTY_MARK : formatInteger(holdingCount.value),
    helper: "目前持倉",
    tone: "neutral",
  },
  {
    key: "max-drawdown",
    label: "最大回撤",
    value: formatPercent(props.assetPerformanceSummary?.max_drawdown_pct),
    helper: `區間 ${formatRangeLabel(props.assetPerformanceRange)}`,
    tone: toneForValue(props.assetPerformanceSummary?.max_drawdown_pct),
  },
]);

function parseFiniteNumber(value) {
  if (value === "" || value == null) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function firstFinite(...values) {
  for (const value of values) {
    const numeric = parseFiniteNumber(value);
    if (numeric != null) return numeric;
  }
  return null;
}

function toneForValue(value) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null || numeric === 0) return "neutral";
  return numeric > 0 ? "positive" : "negative";
}

function formatCurrency(value, currency = props.assetBaseCurrency) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return EMPTY_MARK;
  return `${currency} ${numeric.toLocaleString("zh-TW", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function formatSignedCurrency(value, currency = props.assetBaseCurrency) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return EMPTY_MARK;
  const sign = numeric > 0 ? "+" : numeric < 0 ? "-" : "";
  return `${sign}${currency} ${Math.abs(numeric).toLocaleString("zh-TW", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function formatPercent(value) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return EMPTY_MARK;
  return `${numeric.toFixed(2)}%`;
}

function formatInteger(value) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return EMPTY_MARK;
  return numeric.toLocaleString("zh-TW", { maximumFractionDigits: 0 });
}

function formatRangeLabel(value) {
  return String(value || "1y").toUpperCase();
}
</script>

<style scoped>
.asset-kpi-section {
  margin-bottom: 18px;
}

.asset-kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.asset-kpi-card {
  min-width: 0;
  min-height: 132px;
  padding: 16px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: 16px;
  background: var(--asset-card-bg, #111827);
  box-shadow: 0 10px 26px rgba(0, 0, 0, 0.14);
}

.asset-kpi-card.featured {
  grid-column: span 2;
}

.asset-kpi-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--asset-text-secondary, #94a3b8);
  font-size: 12px;
}

.asset-kpi-label-row em {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.14);
  color: var(--asset-info, #2563eb);
  font-style: normal;
  font-size: 10px;
  font-weight: 700;
}

.asset-kpi-card strong {
  display: block;
  margin-top: 14px;
  color: var(--asset-text-primary, #e5e7eb);
  font-size: clamp(20px, 2.2vw, 30px);
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}

.asset-kpi-card small {
  display: block;
  margin-top: 10px;
  color: var(--asset-text-muted, #64748b);
  font-size: 11px;
  line-height: 1.45;
}

.asset-kpi-card.positive strong {
  color: var(--asset-positive, #dc2626);
}

.asset-kpi-card.negative strong {
  color: var(--asset-negative, #16a34a);
}

.asset-kpi-card.warning {
  border-color: rgba(245, 158, 11, 0.34);
}

.asset-kpi-card.warning strong {
  color: var(--asset-warning, #f59e0b);
}

.asset-kpi-card.skeleton span,
.asset-kpi-card.skeleton strong,
.asset-kpi-card.skeleton small {
  display: block;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.08), rgba(148, 163, 184, 0.2), rgba(148, 163, 184, 0.08));
  background-size: 180% 100%;
  animation: asset-skeleton 1.2s ease-in-out infinite;
}

.asset-kpi-card.skeleton span {
  width: 46%;
  height: 12px;
}

.asset-kpi-card.skeleton strong {
  width: 78%;
  height: 30px;
  margin-top: 16px;
}

.asset-kpi-card.skeleton small {
  width: 58%;
  height: 10px;
  margin-top: 16px;
}

@keyframes asset-skeleton {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@media (max-width: 1180px) {
  .asset-kpi-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .asset-kpi-card.featured {
    grid-column: span 1;
  }
}

@media (max-width: 760px) {
  .asset-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
