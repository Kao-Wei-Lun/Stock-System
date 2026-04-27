<template>
  <section class="frs-panel">
    <div class="frs-header">
      <h3>期貨口數風控</h3>
      <span v-if="loading" class="frs-muted">計算中...</span>
    </div>

    <div v-if="error" class="frs-error">{{ error }}</div>

    <div v-if="sizing" class="frs-grid">
      <div class="frs-main">
        <div class="frs-label">建議口數</div>
        <div class="frs-value">{{ sizing.suggested_contracts }}</div>
      </div>
      <div class="frs-main">
        <div class="frs-label">可新增</div>
        <div class="frs-value">{{ sizing.addable_contracts }}</div>
      </div>
      <div>
        <div class="frs-label">保證金限制</div>
        <div class="frs-subvalue">{{ sizing.margin_contracts }}</div>
      </div>
      <div>
        <div class="frs-label">壓力測試限制</div>
        <div class="frs-subvalue">{{ sizing.stress_contracts }}</div>
      </div>
      <div>
        <div class="frs-label">單筆停損限制</div>
        <div class="frs-subvalue">{{ sizing.risk_contracts }}</div>
      </div>
      <div>
        <div class="frs-label">每口停損風險</div>
        <div class="frs-subvalue">{{ formatMoney(sizing.loss_per_contract_at_stop) }}</div>
      </div>
      <div>
        <div class="frs-label">每口壓力損失</div>
        <div class="frs-subvalue">{{ formatMoney(sizing.loss_per_contract_under_stress) }}</div>
      </div>
      <div>
        <div class="frs-label">保證金預算</div>
        <div class="frs-subvalue">{{ formatMoney(sizing.margin_budget) }}</div>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  sizing: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  error: { type: String, default: "" },
});

function formatMoney(value) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  return new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 }).format(Number(value));
}
</script>

<style scoped>
.frs-panel {
  margin-top: 18px;
  padding: 14px;
  border: 1px solid rgba(144, 222, 255, 0.16);
  border-radius: 8px;
  background: rgba(144, 222, 255, 0.04);
}

.frs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.frs-header h3 {
  margin: 0;
  font-size: 14px;
  color: #e6f1ff;
}

.frs-muted,
.frs-label {
  color: rgba(196, 211, 226, 0.68);
  font-size: 11px;
}

.frs-error {
  color: #ff8c42;
  font-size: 12px;
}

.frs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
  gap: 10px;
}

.frs-grid > div {
  min-height: 64px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 8px;
  background: rgba(8, 12, 19, 0.42);
}

.frs-main {
  border-color: rgba(93, 211, 158, 0.24) !important;
  background: rgba(93, 211, 158, 0.07) !important;
}

.frs-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 800;
  color: #5dd39e;
}

.frs-subvalue {
  margin-top: 6px;
  font-size: 16px;
  font-weight: 700;
  color: #e6f1ff;
}
</style>
