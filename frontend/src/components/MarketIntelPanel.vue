<template>
  <div class="ind-group">
    <div class="ind-group-title">市場資訊</div>

    <div v-if="macroSummary" class="intel-card">
      <div class="intel-head">
        <strong>市場節奏</strong>
        <span>{{ formatMacroRisk(macroSummary.overall_risk) }}</span>
      </div>
      <div class="intel-title">{{ formatMacroPosture(macroSummary.trade_posture) }}</div>
      <p class="intel-copy">{{ macroSummary.decision_hint || "先以價格與風險控管為主。" }}</p>
    </div>

    <div v-if="tickerEvents.length" class="intel-card">
      <div class="intel-head">
        <strong>事件焦點</strong>
        <span>{{ tickerEvents.length }} 筆</span>
      </div>
      <button
        v-for="item in tickerEvents.slice(0, 4)"
        :key="`${item.event_type}-${item.event_date}-${item.title}`"
        type="button"
        class="intel-row intel-event-btn"
        @click="$emit('focus-event', item)"
      >
        <span>{{ item.title }}</span>
        <small>{{ item.event_date }}</small>
      </button>
    </div>

    <div v-if="fundamentalsSummary" class="intel-card">
      <div class="intel-head">
        <strong>基本面摘要</strong>
        <span>{{ fundamentalsSummary.updated_at ? "已同步" : "local" }}</span>
      </div>
      <div class="intel-title">{{ fundamentalsSummary.headline }}</div>
      <div class="intel-badges">
        <span
          v-for="signal in fundamentalsSummary.signals || []"
          :key="`${signal.label}-${signal.value}`"
          class="intel-badge"
        >
          {{ signal.label }} · {{ signal.value }}
        </span>
      </div>
    </div>

    <div v-if="taiwanChipSummary" class="intel-card">
      <div class="intel-head">
        <strong>台股籌碼</strong>
        <span :class="`bias-${taiwanChipSummary.bias || 'neutral'}`">{{ taiwanChipSummary.bias || "neutral" }}</span>
      </div>
      <div class="intel-badges">
        <span
          v-for="signal in taiwanChipSummary.signals || []"
          :key="`${signal.label}-${signal.value}`"
          class="intel-badge"
        >
          {{ signal.label }} · {{ signal.value }}
        </span>
      </div>
    </div>

    <div v-if="tickerNews.length" class="intel-card">
      <div class="intel-head">
        <strong>新聞快照</strong>
        <span>{{ tickerNews.length }} 則</span>
      </div>
      <a
        v-for="article in tickerNews.slice(0, 3)"
        :key="`${article.title}-${article.published_at}`"
        class="intel-row intel-link"
        :href="article.url"
        target="_blank"
        rel="noreferrer"
      >
        <span>{{ article.title }}</span>
        <small>{{ formatTimestamp(article.published_at) }}</small>
      </a>
    </div>

    <div v-if="!hasContent" class="intel-empty">
      {{ currentTicker ? `${currentTicker} 尚未同步事件、基本面與新聞摘要` : "尚未同步市場資訊" }}
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  currentTicker: { type: String, default: "" },
  macroSummary: { type: Object, default: null },
  tickerEvents: { type: Array, default: () => [] },
  tickerNews: { type: Array, default: () => [] },
  fundamentalsSummary: { type: Object, default: null },
  taiwanChipSummary: { type: Object, default: null },
});

defineEmits(["focus-event"]);

const hasContent = computed(() => Boolean(
  props.macroSummary
  || props.tickerEvents.length
  || props.tickerNews.length
  || props.fundamentalsSummary
  || props.taiwanChipSummary,
));

function formatTimestamp(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-TW", { hour12: false });
}

function formatMacroRisk(value) {
  if (value === "high") return "高風險";
  if (value === "medium") return "中風險";
  if (value === "low") return "低風險";
  return "未同步";
}

function formatMacroPosture(value) {
  if (value === "defensive") return "防守控倉";
  if (value === "selective") return "選擇性出手";
  if (value === "offensive") return "偏進攻";
  if (value === "balanced") return "平衡觀察";
  return "暫停判斷";
}
</script>

<style scoped>
.intel-card {
  display: grid;
  gap: 10px;
  margin-top: 10px;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(16, 20, 32, 0.92), rgba(10, 13, 22, 0.98));
}

.intel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--text3);
}

.intel-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text1);
}

.intel-copy {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text2);
}

.intel-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 10px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.03);
  color: inherit;
  text-decoration: none;
  text-align: left;
}

.intel-event-btn {
  cursor: pointer;
}

.intel-event-btn:hover,
.intel-link:hover {
  border-color: rgba(0, 212, 255, 0.28);
  background: rgba(0, 212, 255, 0.08);
}

.intel-row span {
  color: var(--text1);
  font-size: 12px;
  line-height: 1.5;
}

.intel-row small {
  flex-shrink: 0;
  color: var(--text3);
  font-size: 11px;
}

.intel-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.intel-badge {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text2);
  font-size: 11px;
}

.intel-empty {
  margin-top: 10px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text3);
  font-size: 12px;
  line-height: 1.6;
}

.bias-bullish {
  color: var(--green);
}

.bias-bearish {
  color: var(--red);
}

.bias-neutral {
  color: var(--text3);
}
</style>
