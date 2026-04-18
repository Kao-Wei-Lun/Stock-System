<template>
  <div class="institutional-section">
    <div class="institutional-section-head">
      <div>
        <div class="ind-group-title">個股籌碼摘要</div>
        <div class="institutional-section-note">{{ note }}</div>
      </div>
      <div class="chip-overview-headline">
        {{ summaryHeadline }}
      </div>
    </div>

    <div class="institutional-card">
      <div class="institutional-kpi-strip">
        <div class="inst-kpi">
          <div class="inst-kpi-label">標的</div>
          <div class="inst-kpi-value">{{ currentName || currentTicker || "—" }}</div>
          <div class="inst-kpi-change">{{ currentTicker || "—" }}</div>
        </div>
        <div class="inst-kpi">
          <div class="inst-kpi-label">目前偏向</div>
          <div class="inst-kpi-value">{{ biasLabel }}</div>
          <div class="inst-kpi-change">{{ sourceLabel }}</div>
        </div>
        <div class="inst-kpi">
          <div class="inst-kpi-label">最新資料日</div>
          <div class="inst-kpi-value">{{ snapshotDate || "—" }}</div>
          <div class="inst-kpi-change">{{ rangeLabel }}</div>
        </div>
        <div class="inst-kpi">
          <div class="inst-kpi-label">區間法人合計</div>
          <div class="inst-kpi-value" :class="rangeNet >= 0 ? 'up' : 'dn'">
            {{ formatSigned(rangeNet) }}
          </div>
          <div class="inst-kpi-change">近 {{ rangeDays }} 日累積買賣超</div>
        </div>
      </div>

      <div v-if="signals.length" class="institutional-rows compact">
        <div v-for="signal in signals" :key="signal.label" class="inst-row">
          <span>{{ signal.label }}</span>
          <span :class="signal.tone === 'positive' ? 'up' : signal.tone === 'caution' ? 'dn' : ''">
            {{ signal.value }}
          </span>
        </div>
      </div>
      <div v-else class="institutional-empty institutional-empty-compact">
        尚未整理出可讀的籌碼訊號，先從下方區間走勢觀察方向。
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  currentTicker: { type: String, default: "" },
  currentName: { type: String, default: "" },
  chipDetail: { type: Object, default: null },
  chipSummary: { type: Object, default: null },
  chipHistory: { type: Object, default: null },
  rangeDays: { type: Number, default: 20 },
});

function formatSigned(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "±0";
  return `${numeric > 0 ? "+" : "-"}${Math.abs(numeric).toLocaleString()}`;
}

const resolvedSummary = computed(() =>
  props.chipSummary || props.chipHistory?.latest?.summary || props.chipDetail?.summary || null,
);

const snapshotDate = computed(() =>
  props.chipDetail?.snapshot_date || props.chipHistory?.latest?.snapshot_date || "",
);

const sourceLabel = computed(() => {
  const source = String(props.chipDetail?.source || props.chipHistory?.latest?.source || "").trim().toLowerCase();
  if (source === "twse_t86") return "TWSE 三大法人";
  if (source === "tpex_3itrade_hedge") return "TPEX 三大法人";
  return source ? source.toUpperCase() : "資料待補";
});

const biasLabel = computed(() => ({
  bullish: "偏多",
  bearish: "偏空",
  neutral: "中性",
}[String(resolvedSummary.value?.bias || "neutral")] || "中性"));

const signals = computed(() => resolvedSummary.value?.signals || []);

const rangeKey = computed(() => `institutional_${props.rangeDays}d_sum`);
const rangeNet = computed(() => Number(props.chipHistory?.stats?.[rangeKey.value] || 0));
const rangeLabel = computed(() => {
  const range = props.chipHistory?.resolved_range;
  if (!range?.from || !range?.to) return `近 ${props.rangeDays} 日觀察`;
  return `${range.from} → ${range.to}`;
});

const summaryHeadline = computed(() => (
  resolvedSummary.value?.headline
  || `用近 ${props.rangeDays} 日區間一起看外資、投信、自營商與法人合計的變化。`
));

const note = computed(() => {
  if (!props.currentTicker) {
    return "切到台股個股後，這裡會整理籌碼摘要與近幾日變化。";
  }
  if (!props.chipHistory?.series?.length) {
    return "目前先顯示最新可用資料，歷史區間資料整理完成後會同步補上。";
  }
  return "上面先看偏向與區間累積，下面再看每天的變化與轉折。";
});
</script>

<style scoped>
.chip-overview-headline {
  max-width: 420px;
  color: var(--text2);
  font-size: 12px;
  line-height: 1.5;
  text-align: right;
}

@media (max-width: 860px) {
  .chip-overview-headline {
    max-width: none;
    text-align: left;
  }
}
</style>
