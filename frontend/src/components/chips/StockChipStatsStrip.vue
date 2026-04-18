<template>
  <div class="institutional-section">
    <div class="institutional-section-head">
      <div>
        <div class="ind-group-title">區間統計</div>
        <div class="institutional-section-note">把累積買賣超、連續性與極值拉成一排，方便快速判讀主導力量。</div>
      </div>
    </div>

    <div class="chip-stats-grid">
      <div v-for="card in cards" :key="card.label" class="institutional-card chip-stat-card">
        <div class="chip-stat-label">{{ card.label }}</div>
        <div class="chip-stat-value" :class="card.tone">{{ card.value }}</div>
        <div class="chip-stat-note">{{ card.note }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  chipHistory: { type: Object, default: null },
});

function formatSigned(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "±0";
  return `${numeric > 0 ? "+" : "-"}${Math.abs(numeric).toLocaleString()}`;
}

const series = computed(() => props.chipHistory?.series || []);
const stats = computed(() => props.chipHistory?.stats || {});

const extremes = computed(() => {
  const values = series.value
    .map((item) => Number(item?.institutional_net_buy_sell))
    .filter((value) => Number.isFinite(value));
  if (!values.length) return { buy: 0, sell: 0 };
  return {
    buy: Math.max(...values),
    sell: Math.min(...values),
  };
});

const cards = computed(() => [
  {
    label: "5 日合計",
    value: formatSigned(stats.value.foreign_5d_sum ?? 0),
    note: "外資近 5 日累積",
    tone: Number(stats.value.foreign_5d_sum || 0) >= 0 ? "up" : "dn",
  },
  {
    label: "10 日合計",
    value: formatSigned(stats.value.institutional_10d_sum ?? 0),
    note: "法人合計近 10 日累積",
    tone: Number(stats.value.institutional_10d_sum || 0) >= 0 ? "up" : "dn",
  },
  {
    label: "20 日合計",
    value: formatSigned(stats.value.institutional_20d_sum ?? 0),
    note: "預設觀察主區間",
    tone: Number(stats.value.institutional_20d_sum || 0) >= 0 ? "up" : "dn",
  },
  {
    label: "60 日合計",
    value: formatSigned(stats.value.institutional_60d_sum ?? 0),
    note: "拉長週期看累積方向",
    tone: Number(stats.value.institutional_60d_sum || 0) >= 0 ? "up" : "dn",
  },
  {
    label: "法人連續性",
    value: `${Number(stats.value.institutional_streak_days || 0)} 日`,
    note: Number(stats.value.institutional_streak_days || 0)
      ? `目前為${stats.value.institutional_streak_direction === "buy" ? "連買" : "連賣"}`
      : "尚未形成連續方向",
    tone: stats.value.institutional_streak_direction === "sell" ? "dn" : "up",
  },
  {
    label: "單日極值",
    value: `${formatSigned(extremes.value.buy)} / ${formatSigned(extremes.value.sell)}`,
    note: "區間內最大單日買超 / 賣超",
    tone: "",
  },
]);
</script>

<style scoped>
.chip-stats-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.chip-stat-card {
  display: grid;
  gap: 8px;
}

.chip-stat-label {
  color: var(--text3);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.chip-stat-value {
  color: #f5f7fa;
  font-family: "JetBrains Mono", monospace;
  font-size: 20px;
}

.chip-stat-note {
  color: var(--text2);
  font-size: 11px;
  line-height: 1.5;
}

@media (max-width: 1200px) {
  .chip-stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .chip-stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
