<template>
  <section class="workspace-page institutional-page">
    <div class="workspace-hero">
      <div>
        <div class="workspace-kicker">Institutional Analysis</div>
        <h1>把法人動向、期選未平倉與成本帶拉到同一張研究桌上。</h1>
      </div>
      <button class="hero-action" type="button" @click="$emit('open-terminal')">
        回到終端
      </button>
    </div>

    <div class="institutional-stage">
      <InstitutionalDashboard
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
        :taiwan-chip-summary="taiwanChipSummary"
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
  </section>
</template>

<script setup>
import InstitutionalDashboard from "../InstitutionalDashboard.vue";

defineProps({
  data: { type: Object, default: null },
  insights: { type: Object, default: null },
  loading: { type: Boolean, required: true },
  error: { type: String, default: "" },
  insightsLoading: { type: Boolean, required: true },
  insightsError: { type: String, default: "" },
  selectedDate: { type: String, default: "" },
  selectedFuturesCommodity: { type: String, default: "" },
  selectedOptionsCommodity: { type: String, default: "" },
  historyDays: { type: Number, required: true },
  currentTicker: { type: String, default: "" },
  currentName: { type: String, default: "" },
  taiwanChipDetail: { type: Object, default: null },
  taiwanChipSummary: { type: Object, default: null },
  taifexStructuredQuery: { type: Object, default: () => ({}) },
  taifexStructuredData: { type: Object, default: () => ({ section: "futures", count: 0, filters: {}, items: [] }) },
  taifexStructuredLoading: { type: Boolean, default: false },
  taifexStructuredError: { type: String, default: "" },
});

defineEmits([
  "open-terminal",
  "set-date",
  "shift-date",
  "refresh-dashboard",
  "refresh-insights",
  "set-futures-commodity",
  "set-options-commodity",
  "set-history-days",
  "create-alert",
  "update-taifex-structured-query",
  "refresh-taifex-structured",
  "reset-taifex-structured",
]);
</script>

<style scoped>
.workspace-page {
  height: 100%;
  overflow: auto;
  padding: 18px;
}

.institutional-page {
  background:
    radial-gradient(circle at top right, rgba(255, 209, 102, 0.08), transparent 28%),
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
  background: linear-gradient(135deg, rgba(20, 17, 6, 0.42), rgba(10, 16, 26, 0.96));
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

.hero-action {
  padding: 10px 14px;
  border: 1px solid rgba(255, 209, 102, 0.22);
  border-radius: 999px;
  background: rgba(255, 209, 102, 0.1);
  color: #ffe7a2;
  cursor: pointer;
  font-size: 11px;
}

.institutional-stage {
  margin-top: 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  overflow: hidden;
  background: rgba(6, 10, 18, 0.74);
}

.institutional-stage :deep(.institutional-shell) {
  border-radius: 0;
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
}
</style>
