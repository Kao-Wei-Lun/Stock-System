<template>
  <section class="asset-card asset-activity-card">
    <div class="asset-card-head">
      <div>
        <div class="asset-card-title">最近流水</div>
        <div class="bt-trade-sub">最近交易、股利、入金、出金與費用</div>
      </div>
      <button class="asset-inline-btn" type="button" @click="$emit('open-tab', 'holdings')">查看明細</button>
    </div>

    <div v-if="assetLoading" class="asset-activity-skeleton">
      <span v-for="index in 5" :key="index"></span>
    </div>

    <div v-else-if="recentFlowItems.length" class="asset-activity-list">
      <button
        v-for="item in recentFlowItems"
        :key="item.key"
        class="asset-activity-item"
        type="button"
        @click="$emit('focus-holdings', item.filter)"
      >
        <div class="asset-activity-main">
          <span>{{ item.dateLabel }}</span>
          <strong>{{ item.title }}</strong>
          <small>{{ item.meta }}</small>
        </div>
        <div class="asset-activity-metrics">
          <span :class="item.tone">{{ item.value }}</span>
          <small>{{ item.kind }}</small>
        </div>
      </button>
    </div>

    <div v-else class="asset-empty-state">目前沒有最近流水。</div>
  </section>
</template>

<script setup>
import { computed } from "vue";
import {
  formatDateLabel,
  formatNumber,
  formatSignedCurrency,
  signedValueForFlow,
  toneForValue,
} from "./assetDashboardFormatters";

const props = defineProps({
  assetLoading: { type: Boolean, default: false },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetCashEntries: { type: Array, default: () => [] },
  assetTradeEntries: { type: Array, default: () => [] },
});

defineEmits(["focus-holdings", "open-tab"]);

const recentFlowItems = computed(() => {
  const trades = (props.assetTradeEntries || []).map((entry) => ({
    key: `trade-${entry.id}`,
    title: `${entry.ticker || "--"} · ${tradeSideLabel(entry.side)}`,
    meta: `${entry.account_name || entry.account_id || "帳戶"}${entry.market ? ` · ${entry.market}` : ""}`,
    dateLabel: formatDateLabel(entry.trade_date, true),
    value: `${formatNumber(entry.quantity, 4)} @ ${formatNumber(entry.price, 2)}`,
    tone: "neutral",
    kind: "交易",
    timestamp: new Date(entry.trade_date || 0).getTime(),
    filter: {
      accountKey: entry.account_name || "",
      marketKey: entry.market || "",
      ticker: entry.ticker || "",
      month: extractMonth(entry.trade_date),
    },
  }));

  const cash = (props.assetCashEntries || []).map((entry) => {
    const signedAmount = signedValueForFlow(entry.amount, entry.flow_type);
    return {
      key: `cash-${entry.id}`,
      title: flowTypeLabel(entry.flow_type),
      meta: entry.account_name || entry.account_id || "帳戶",
      dateLabel: formatDateLabel(entry.flow_date, true),
      value: formatSignedCurrency(entry.amount, entry.currency || props.assetBaseCurrency, entry.flow_type),
      tone: toneForValue(signedAmount),
      kind: "現金",
      timestamp: new Date(entry.flow_date || 0).getTime(),
      filter: {
        accountKey: entry.account_name || "",
        month: extractMonth(entry.flow_date),
      },
    };
  });

  return [...trades, ...cash]
    .sort((left, right) => right.timestamp - left.timestamp)
    .slice(0, 12);
});

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

.bt-trade-sub {
  color: var(--asset-text-secondary, #94a3b8);
  font-size: 11px;
  line-height: 1.5;
}

.asset-inline-btn {
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.72);
  color: var(--asset-text-secondary, #94a3b8);
  font: inherit;
  cursor: pointer;
}

.asset-inline-btn:hover {
  border-color: rgba(37, 99, 235, 0.4);
  color: var(--asset-text-primary, #e5e7eb);
}

.asset-activity-list {
  display: grid;
  gap: 8px;
}

.asset-activity-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: 12px;
  background: rgba(8, 14, 24, 0.66);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.asset-activity-item:hover {
  border-color: rgba(37, 99, 235, 0.34);
  background: rgba(37, 99, 235, 0.1);
}

.asset-activity-main {
  min-width: 0;
}

.asset-activity-main span {
  display: block;
  color: var(--asset-text-muted, #64748b);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.asset-activity-main strong {
  display: block;
  margin-top: 4px;
  color: var(--asset-text-primary, #e5e7eb);
  overflow-wrap: anywhere;
}

.asset-activity-main small {
  display: block;
  margin-top: 4px;
  color: var(--asset-text-secondary, #94a3b8);
}

.asset-activity-metrics {
  display: grid;
  justify-items: end;
  align-content: center;
  gap: 4px;
  white-space: nowrap;
}

.asset-activity-metrics span {
  color: var(--asset-text-primary, #e5e7eb);
  font-variant-numeric: tabular-nums;
  font-weight: 800;
}

.asset-activity-metrics span.positive {
  color: var(--asset-positive, #ef4444);
}

.asset-activity-metrics span.negative {
  color: var(--asset-negative, #22c55e);
}

.asset-activity-metrics span.neutral {
  color: var(--asset-text-secondary, #94a3b8);
}

.asset-activity-metrics small {
  color: var(--asset-text-muted, #64748b);
}

.asset-empty-state {
  display: grid;
  place-items: center;
  min-height: 180px;
  border: 1px dashed var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-card, 16px);
  color: var(--asset-text-secondary, #94a3b8);
  text-align: center;
}

.asset-activity-skeleton {
  display: grid;
  gap: 8px;
}

.asset-activity-skeleton span {
  height: 58px;
  border-radius: 12px;
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
  .asset-card-head {
    display: grid;
  }

  .asset-activity-item {
    grid-template-columns: 1fr;
  }

  .asset-activity-metrics {
    justify-items: start;
  }
}
</style>
