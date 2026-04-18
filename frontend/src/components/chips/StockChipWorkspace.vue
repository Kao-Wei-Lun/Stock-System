<template>
  <div class="institutional-shell chip-stock-shell">
    <div class="institutional-toolbar">
      <div>
        <div class="institutional-title">個股籌碼追蹤</div>
        <div class="institutional-subtitle">
          把單日 snapshot 拉成一段時間的連續畫面，直接看出法人方向、區間累積與價格對照。
        </div>
      </div>
      <div class="institutional-toolbar-actions chip-toolbar-actions">
        <button
          v-for="value in rangeOptions"
          :key="value"
          type="button"
          class="tool-btn"
          :class="{ active: rangeDays === value }"
          :disabled="!stockSupported || loading"
          @click="$emit('set-range-days', value)"
        >
          {{ value }} 日
        </button>
        <button class="tool-btn active" :disabled="loading || !stockSupported" @click="$emit('refresh')">
          {{ loading ? "整理中..." : "重新整理" }}
        </button>
      </div>
    </div>

    <div class="chart-meta institutional-meta">
      <div class="meta-chip">標的 {{ currentTicker || "—" }}</div>
      <div class="meta-chip">名稱 {{ currentName || "—" }}</div>
      <div class="meta-chip">區間 {{ chipHistory?.resolved_range?.from || "—" }} → {{ chipHistory?.resolved_range?.to || "—" }}</div>
      <div class="meta-chip">目前檢視 {{ rangeDays }} 日</div>
      <div class="meta-chip is-hint">資料來源：TWSE / TPEX 三大法人個股買賣超與本地收盤資料對照。</div>
    </div>

    <div v-if="!stockSupported" class="institutional-card chip-empty-card">
      <div class="chip-empty-title">目前標的不支援個股籌碼歷史</div>
      <p>請切換到 `.TW` 或 `.TWO` 個股後再看個股籌碼，或先回到大盤 / TAIFEX 法人籌碼繼續研究。</p>
      <button class="tool-btn active" type="button" @click="$emit('switch-market')">
        切回大盤 / TAIFEX
      </button>
    </div>

    <div v-else-if="loading && !chipHistory" class="institutional-loading">
      <div class="spinner"></div>
      <p>正在整理個股籌碼區間資料...</p>
    </div>

    <div v-else-if="error && !chipHistory" class="institutional-error">
      {{ error }}
    </div>

    <template v-else>
      <div v-if="error" class="institutional-inline-error">{{ error }}</div>
      <StockChipOverview
        :current-ticker="currentTicker"
        :current-name="currentName"
        :chip-detail="chipDetail"
        :chip-summary="chipSummary"
        :chip-history="chipHistory"
        :range-days="rangeDays"
      />
      <StockChipTrendChart :chip-history="chipHistory" />
      <StockChipStatsStrip :chip-history="chipHistory" />
      <StockChipTurningPoints :chip-history="chipHistory" :range-days="rangeDays" />
    </template>
  </div>
</template>

<script setup>
import StockChipOverview from "./StockChipOverview.vue";
import StockChipStatsStrip from "./StockChipStatsStrip.vue";
import StockChipTrendChart from "./StockChipTrendChart.vue";
import StockChipTurningPoints from "./StockChipTurningPoints.vue";

defineProps({
  currentTicker: { type: String, default: "" },
  currentName: { type: String, default: "" },
  chipDetail: { type: Object, default: null },
  chipSummary: { type: Object, default: null },
  chipHistory: { type: Object, default: null },
  rangeDays: { type: Number, default: 20 },
  rangeOptions: { type: Array, default: () => [5, 10, 20, 60] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: "" },
  stockSupported: { type: Boolean, default: false },
});

defineEmits(["set-range-days", "refresh", "switch-market"]);
</script>

<style scoped>
.chip-stock-shell {
  padding-bottom: 18px;
}

.chip-toolbar-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.chip-empty-card {
  display: grid;
  gap: 10px;
  margin: 18px;
}

.chip-empty-title {
  color: #f5f7fa;
  font-family: "Syne", sans-serif;
  font-size: 22px;
}

.chip-empty-card p {
  margin: 0;
  color: var(--text2);
  line-height: 1.6;
}

@media (max-width: 860px) {
  .chip-toolbar-actions {
    justify-content: flex-start;
  }
}
</style>
