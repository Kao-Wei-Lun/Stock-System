<template>
  <section class="asset-holdings-table-section">
    <header class="asset-section-head">
      <div>
        <span>Holdings</span>
        <strong>持股明細</strong>
      </div>
      <div class="asset-holdings-actions">
        <input v-model="searchText" type="search" placeholder="搜尋代號或名稱" aria-label="搜尋持股" />
        <select v-model="marketFilter" aria-label="市場篩選">
          <option value="">全部市場</option>
          <option v-for="market in marketOptions" :key="market" :value="market">{{ market }}</option>
        </select>
      </div>
    </header>

    <div class="asset-sort-row" aria-label="持股排序">
      <button
        v-for="item in sortOptions"
        :key="item.key"
        type="button"
        :class="{ active: sortKey === item.key }"
        @click="setSort(item.key)"
      >
        {{ item.label }}
        <span v-if="sortKey === item.key">{{ sortDirection === 'desc' ? '↓' : '↑' }}</span>
      </button>
    </div>

    <div v-if="assetLoading" class="asset-table-skeleton">
      <span v-for="index in 8" :key="index"></span>
    </div>

    <div v-else-if="sortedHoldings.length" class="asset-table-wrap">
      <table class="asset-holdings-table">
        <thead>
          <tr>
            <th>代號</th>
            <th>名稱</th>
            <th>市場</th>
            <th class="number">持有股數</th>
            <th class="number">均價</th>
            <th class="number">現價</th>
            <th class="number">市值</th>
            <th class="number">未實現損益</th>
            <th class="number">報酬率</th>
            <th class="number">權重</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="holding in sortedHoldings"
            :key="holdingKey(holding)"
            @click="$emit('focus-holding', holding.ticker)"
          >
            <td>
              <button class="asset-ticker-btn" type="button">
                {{ holding.ticker || "--" }}
              </button>
            </td>
            <td>{{ holding.display_name || holding.ticker || "--" }}</td>
            <td>{{ holding.market || "--" }}</td>
            <td class="number">{{ formatNumber(holding.quantity, 4) }}</td>
            <td class="number">{{ formatNumber(holding.avg_cost, 2) }}</td>
            <td class="number">
              {{ holding.last_price == null ? "--" : formatNumber(holding.last_price, 2) }}
              <span v-if="holding.is_delayed" class="asset-price-badge">Delayed</span>
              <span v-if="holding.manual_price_override_id" class="asset-price-badge">Manual</span>
            </td>
            <td class="number">{{ formatCurrency(holding.market_value_base) }}</td>
            <td class="number" :class="toneForValue(holding.unrealized_pnl_base)">
              {{ formatSignedCurrency(holding.unrealized_pnl_base) }}
            </td>
            <td class="number" :class="toneForValue(resolveReturnPct(holding))">
              {{ formatPercent(resolveReturnPct(holding)) }}
            </td>
            <td class="number">{{ formatPercent(resolveWeightPct(holding)) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="asset-empty-state">
      目前沒有符合條件的持股。
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import {
  formatCurrency as formatAssetCurrency,
  formatNumber,
  formatPercent,
  formatSignedCurrency as formatAssetSignedCurrency,
  parseFiniteNumber,
  toneForValue,
} from "./assetDashboardFormatters";

const props = defineProps({
  assetLoading: { type: Boolean, default: false },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetHoldings: { type: Array, default: () => [] },
});

defineEmits(["focus-holding"]);

const searchText = ref("");
const marketFilter = ref("");
const sortKey = ref("market_value_base");
const sortDirection = ref("desc");

const sortOptions = [
  { key: "market_value_base", label: "依市值排序" },
  { key: "unrealized_pnl_base", label: "依損益排序" },
  { key: "return_pct", label: "依報酬率排序" },
];

const marketOptions = computed(() => (
  Array.from(new Set((props.assetHoldings || [])
    .map((holding) => String(holding?.market || "").trim().toUpperCase())
    .filter(Boolean)))
    .sort()
));

const filteredHoldings = computed(() => {
  const keyword = searchText.value.trim().toUpperCase();
  const market = marketFilter.value.trim().toUpperCase();
  return (props.assetHoldings || []).filter((holding) => {
    const ticker = String(holding?.ticker || "").toUpperCase();
    const name = String(holding?.display_name || "").toUpperCase();
    const holdingMarket = String(holding?.market || "").toUpperCase();
    if (market && holdingMarket !== market) return false;
    if (keyword && !ticker.includes(keyword) && !name.includes(keyword)) return false;
    return true;
  });
});

const totalHoldingValue = computed(() => (
  filteredHoldings.value.reduce((sum, holding) => sum + (parseFiniteNumber(holding?.market_value_base) ?? 0), 0)
));

const sortedHoldings = computed(() => {
  const direction = sortDirection.value === "asc" ? 1 : -1;
  return [...filteredHoldings.value].sort((left, right) => {
    const leftValue = resolveSortValue(left, sortKey.value);
    const rightValue = resolveSortValue(right, sortKey.value);
    return (leftValue - rightValue) * direction;
  });
});

function setSort(key) {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === "desc" ? "asc" : "desc";
    return;
  }
  sortKey.value = key;
  sortDirection.value = "desc";
}

function resolveSortValue(holding, key) {
  if (key === "return_pct") return parseFiniteNumber(resolveReturnPct(holding)) ?? 0;
  return parseFiniteNumber(holding?.[key]) ?? 0;
}

function resolveReturnPct(holding) {
  const direct = parseFiniteNumber(holding?.unrealized_pnl_pct);
  if (direct != null) return direct;
  const pnl = parseFiniteNumber(holding?.unrealized_pnl_base);
  const marketValue = parseFiniteNumber(holding?.market_value_base);
  if (pnl == null || marketValue == null) return null;
  const cost = marketValue - pnl;
  if (!Number.isFinite(cost) || cost === 0) return null;
  return (pnl / cost) * 100;
}

function resolveWeightPct(holding) {
  const value = parseFiniteNumber(holding?.market_value_base);
  if (value == null || !totalHoldingValue.value) return null;
  return (value / totalHoldingValue.value) * 100;
}

function holdingKey(holding) {
  return `${holding?.account_id || "account"}-${holding?.ticker || "ticker"}`;
}

function formatCurrency(value, currency = props.assetBaseCurrency) {
  return formatAssetCurrency(value, currency);
}

function formatSignedCurrency(value, currency = props.assetBaseCurrency) {
  return formatAssetSignedCurrency(value, currency);
}
</script>

<style scoped>
.asset-holdings-table-section {
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
  margin-bottom: 14px;
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

.asset-holdings-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.asset-holdings-actions input,
.asset-holdings-actions select {
  min-height: 36px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-control, 10px);
  background: rgba(15, 23, 42, 0.72);
  color: var(--asset-text-primary, #e5e7eb);
  padding: 8px 10px;
  outline: none;
}

.asset-holdings-actions input {
  min-width: 220px;
}

.asset-sort-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.asset-sort-row button {
  padding: 7px 10px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-control, 10px);
  background: rgba(15, 23, 42, 0.7);
  color: var(--asset-text-secondary, #94a3b8);
  cursor: pointer;
}

.asset-sort-row button.active {
  border-color: rgba(37, 99, 235, 0.48);
  background: rgba(37, 99, 235, 0.16);
  color: var(--asset-text-primary, #e5e7eb);
}

.asset-table-wrap {
  overflow: auto;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-inner, 12px);
}

.asset-holdings-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
}

.asset-holdings-table th,
.asset-holdings-table td {
  padding: 12px;
  border-bottom: 1px solid var(--asset-border, #1f2937);
  color: var(--asset-text-secondary, #94a3b8);
  text-align: left;
  white-space: nowrap;
}

.asset-holdings-table th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #0f172a;
  color: var(--asset-text-muted, #64748b);
  font-size: 11px;
  font-weight: 700;
}

.asset-holdings-table tbody tr {
  cursor: pointer;
}

.asset-holdings-table tbody tr:hover td {
  background: rgba(37, 99, 235, 0.08);
}

.asset-holdings-table tr:last-child td {
  border-bottom: 0;
}

.asset-holdings-table .number {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.asset-ticker-btn {
  border: 0;
  background: transparent;
  color: var(--asset-text-primary, #e5e7eb);
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}

.asset-price-badge {
  display: inline-flex;
  margin-left: 6px;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.16);
  color: var(--asset-info, #2563eb);
  font-size: 10px;
}

.positive {
  color: var(--asset-positive, #ef4444) !important;
}

.negative {
  color: var(--asset-negative, #22c55e) !important;
}

.neutral {
  color: var(--asset-text-secondary, #94a3b8) !important;
}

.asset-empty-state {
  display: grid;
  place-items: center;
  min-height: 180px;
  border: 1px dashed var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-card, 16px);
  color: var(--asset-text-secondary, #94a3b8);
}

.asset-table-skeleton {
  display: grid;
  gap: 8px;
}

.asset-table-skeleton span {
  height: 42px;
  border-radius: var(--asset-radius-inner, 12px);
  background: linear-gradient(90deg, rgba(148, 163, 184, 0.08), rgba(148, 163, 184, 0.2), rgba(148, 163, 184, 0.08));
  background-size: 180% 100%;
  animation: asset-skeleton 1.2s ease-in-out infinite;
}

@keyframes asset-skeleton {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@media (max-width: 768px) {
  .asset-section-head,
  .asset-holdings-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .asset-holdings-actions input,
  .asset-holdings-actions select {
    width: 100%;
    min-width: 0;
  }
}
</style>
