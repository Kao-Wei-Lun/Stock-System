<template>
  <div class="chip-workspace-shell">
    <ChipWorkspaceTabs
      :active-view="activeView"
      :stock-supported="stockSupported"
      @change="activeView = $event"
    />

    <StockChipWorkspace
      v-if="activeView === 'stock'"
      :current-ticker="currentTicker"
      :current-name="currentName"
      :chip-detail="taiwanChipDetail"
      :chip-summary="resolvedChipSummary"
      :chip-history="taiwanChipHistory"
      :range-days="taiwanChipRangeDays"
      :range-options="taiwanChipRangeOptions"
      :loading="taiwanChipHistoryLoading"
      :error="taiwanChipHistoryError"
      :stock-supported="stockSupported"
      @set-range-days="$emit('set-chip-range-days', $event)"
      @refresh="$emit('refresh-chip')"
      @switch-market="activeView = 'market'"
    />

    <MarketInstitutionalDashboard
      v-else
      :data="data"
      :insights="insights"
      :loading="loading"
      :error="error"
      :insights-loading="insightsLoading"
      :insights-error="insightsError"
      :selected-date="selectedDate"
      :selected-futures-commodity="selectedFuturesCommodity"
      :selected-options-commodity="selectedOptionsCommodity"
      :history-days="historyDays"
      :current-ticker="currentTicker"
      :current-name="currentName"
      :taiwan-chip-detail="taiwanChipDetail"
      :taiwan-chip-summary="resolvedChipSummary"
      :show-current-chip-quickview="false"
      :taifex-structured-query="taifexStructuredQuery"
      :taifex-structured-data="taifexStructuredData"
      :taifex-structured-loading="taifexStructuredLoading"
      :taifex-structured-error="taifexStructuredError"
      @set-date="$emit('set-date', $event)"
      @shift-date="$emit('shift-date', $event)"
      @refresh-dashboard="$emit('refresh-dashboard')"
      @refresh-insights="$emit('refresh-insights')"
      @set-futures-commodity="$emit('set-futures-commodity', $event)"
      @set-options-commodity="$emit('set-options-commodity', $event)"
      @set-history-days="$emit('set-history-days', $event)"
      @create-alert="$emit('create-alert', $event)"
      @update-taifex-structured-query="$emit('update-taifex-structured-query', $event)"
      @refresh-taifex-structured="$emit('refresh-taifex-structured')"
      @reset-taifex-structured="$emit('reset-taifex-structured')"
    />
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import ChipWorkspaceTabs from "./chips/ChipWorkspaceTabs.vue";
import StockChipWorkspace from "./chips/StockChipWorkspace.vue";
import MarketInstitutionalDashboard from "./institutional/MarketInstitutionalDashboard.vue";

const props = defineProps({
  data: { type: Object, default: null },
  insights: { type: Object, default: null },
  loading: { type: Boolean, required: true },
  error: { type: String, default: "" },
  insightsLoading: { type: Boolean, default: false },
  insightsError: { type: String, default: "" },
  selectedDate: { type: String, required: true },
  selectedFuturesCommodity: { type: String, default: "" },
  selectedOptionsCommodity: { type: String, default: "" },
  historyDays: { type: Number, default: 30 },
  currentTicker: { type: String, default: "" },
  currentName: { type: String, default: "" },
  taiwanChipDetail: { type: Object, default: null },
  taiwanChipSummary: { type: Object, default: null },
  taiwanChipHistory: { type: Object, default: null },
  taiwanChipRangeDays: { type: Number, default: 20 },
  taiwanChipHistoryLoading: { type: Boolean, default: false },
  taiwanChipHistoryError: { type: String, default: "" },
  taifexStructuredQuery: { type: Object, default: () => ({}) },
  taifexStructuredData: { type: Object, default: () => ({ section: "futures", count: 0, filters: {}, items: [] }) },
  taifexStructuredLoading: { type: Boolean, default: false },
  taifexStructuredError: { type: String, default: "" },
});

defineEmits([
  "set-date",
  "shift-date",
  "refresh-dashboard",
  "refresh-insights",
  "refresh-chip",
  "set-futures-commodity",
  "set-options-commodity",
  "set-history-days",
  "set-chip-range-days",
  "create-alert",
  "update-taifex-structured-query",
  "refresh-taifex-structured",
  "reset-taifex-structured",
]);

function supportsTaiwanChipHistory(ticker) {
  const normalized = String(ticker || "").trim().toUpperCase();
  return normalized.endsWith(".TW") || normalized.endsWith(".TWO");
}

const taiwanChipRangeOptions = [5, 10, 20, 60];
const stockSupported = computed(() => supportsTaiwanChipHistory(props.currentTicker));
const activeView = ref(stockSupported.value ? "stock" : "market");
const resolvedChipSummary = computed(() =>
  props.taiwanChipSummary || props.taiwanChipHistory?.latest?.summary || props.taiwanChipDetail?.summary || null,
);
</script>
