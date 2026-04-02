<template>
  <div class="macro-shell">
    <section class="macro-hero">
      <div class="hero-copy">
        <div class="macro-kicker">Macro Risk</div>
        <h2>宏觀風險儀表板</h2>
        <p>把波動、匯率、利率與半導體風向納入交易前檢查。</p>
        <div class="hero-meta">
          <span class="hero-pill">{{ regimeLabel }}</span>
          <span class="hero-pill muted">{{ postureLabel }}</span>
        </div>
        <div class="hero-hint">{{ decisionHint }}</div>
        <div class="hero-actions">
          <button class="macro-action-btn" @click="$emit('create-alert', { type: 'market_risk', condition: 'high' })">
            提醒高風險
          </button>
          <button class="macro-action-btn secondary" @click="$emit('create-alert', { type: 'market_risk', condition: 'risk_off' })">
            提醒 risk-off
          </button>
        </div>
      </div>
      <div class="hero-side">
        <div class="risk-badge" :class="riskClass">{{ riskLabel }}</div>
        <div class="posture-badge" :class="postureClass">{{ postureLabel }}</div>
        <div class="hero-updated">更新 {{ updatedLabel }}</div>
        <button class="refresh-btn" @click="$emit('refresh')">重新整理</button>
      </div>
    </section>

    <section class="summary-panel">
      <div class="summary-grid">
        <div class="summary-block">
          <div class="panel-title">風險摘要</div>
          <div v-if="riskDrivers.length" class="driver-list">
            <div v-for="driver in riskDrivers" :key="`risk-${driver.label}-${driver.value}`" class="driver-chip" :class="driver.tone">
              <span>{{ driver.label }}</span>
              <strong>{{ driver.value }}</strong>
            </div>
          </div>
          <div v-else class="empty-state">目前沒有明顯風險升溫訊號</div>
        </div>
        <div class="summary-block">
          <div class="panel-title">順風項</div>
          <div v-if="tailwinds.length" class="driver-list">
            <div v-for="driver in tailwinds" :key="`tailwind-${driver.label}-${driver.value}`" class="driver-chip" :class="driver.tone">
              <span>{{ driver.label }}</span>
              <strong>{{ driver.value }}</strong>
            </div>
          </div>
          <div v-else class="empty-state">尚未看到明確順風項</div>
        </div>
      </div>
    </section>

    <section class="metric-grid">
      <article v-for="item in items" :key="item.metric_code" class="metric-card">
        <div class="metric-head">
          <span class="metric-code">{{ item.metric_code }}</span>
          <span class="metric-date">{{ item.date || "—" }}</span>
        </div>
        <div class="metric-name">{{ item.metric_name }}</div>
        <div class="metric-value">{{ formatValue(item.value) }}</div>
        <div class="metric-change" :class="Number(item.change_pct || 0) >= 0 ? 'up' : 'dn'">
          {{ Number(item.change_pct || 0) >= 0 ? "+" : "" }}{{ Number(item.change_pct || 0).toFixed(2) }}%
        </div>
        <div class="metric-source">{{ item.source || "local_db" }}</div>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  macroDashboard: {
    type: Object,
    default: () => ({
      items: [],
      summary: {},
      snapshot_date: null,
    }),
  },
});

defineEmits(["refresh", "create-alert"]);

const items = computed(() => props.macroDashboard?.items || []);
const summary = computed(() => props.macroDashboard?.summary || {});
const riskLevel = computed(() => summary.value?.overall_risk || "unknown");
const riskClass = computed(() => `is-${riskLevel.value}`);
const postureClass = computed(() => `is-${summary.value?.trade_posture || "standby"}`);
const riskLabel = computed(() => {
  if (riskLevel.value === "high") return "高風險";
  if (riskLevel.value === "medium") return "中風險";
  if (riskLevel.value === "low") return "低風險";
  return "尚未同步";
});
const regimeLabel = computed(() => {
  if (summary.value?.regime === "risk_off") return "Risk-off";
  if (summary.value?.regime === "mixed") return "震盪混合";
  if (summary.value?.regime === "trend_supportive") return "趨勢順風";
  if (summary.value?.regime === "neutral") return "中性觀察";
  return "等待快照";
});
const postureLabel = computed(() => {
  if (summary.value?.trade_posture === "defensive") return "防守控倉";
  if (summary.value?.trade_posture === "selective") return "選擇性出手";
  if (summary.value?.trade_posture === "offensive") return "偏進攻";
  if (summary.value?.trade_posture === "balanced") return "平衡觀察";
  return "暫停判斷";
});
const decisionHint = computed(
  () => summary.value?.decision_hint || "尚未同步宏觀風險摘要，暫時不要把市場環境當成進場依據。",
);
const riskDrivers = computed(() => {
  if (summary.value?.risk_drivers?.length) return summary.value.risk_drivers;
  return (summary.value?.drivers || []).filter((item) => item.tone !== "positive");
});
const tailwinds = computed(() => {
  if (summary.value?.tailwinds?.length) return summary.value.tailwinds;
  return (summary.value?.drivers || []).filter((item) => item.tone === "positive");
});
const updatedLabel = computed(() => formatTimestamp(summary.value?.updated_at || props.macroDashboard?.snapshot_date));

function formatValue(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return numeric.toLocaleString("zh-TW", { maximumFractionDigits: 2 });
}

function formatTimestamp(value) {
  if (!value) return "未同步";
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "未同步";
  return parsed.toLocaleString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
</script>

<style scoped>
.macro-shell {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  background: linear-gradient(180deg, rgba(8, 12, 18, 0.98) 0%, rgba(12, 18, 28, 0.98) 100%);
}

.macro-hero,
.summary-panel,
.metric-card {
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(8, 15, 24, 0.9);
}

.macro-hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(61, 189, 255, 0.18), transparent 32%),
    radial-gradient(circle at bottom right, rgba(255, 129, 89, 0.16), transparent 28%),
    rgba(8, 15, 24, 0.92);
}

.hero-copy {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.macro-kicker {
  color: #7be7ff;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 11px;
}

.macro-hero h2 {
  margin: 10px 0 8px;
  color: var(--text1);
}

.macro-hero p {
  margin: 0;
  color: var(--text2);
  max-width: 560px;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-pill,
.posture-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
}

.hero-pill {
  background: rgba(123, 231, 255, 0.12);
  color: #b6f3ff;
}

.hero-pill.muted {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
}

.hero-hint {
  color: var(--text2);
  font-size: 13px;
  max-width: 620px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.risk-badge,
.refresh-btn {
  border-radius: 999px;
  padding: 9px 14px;
  font-size: 12px;
}

.risk-badge {
  color: #081018;
  background: #f5a623;
}

.risk-badge.is-high {
  background: #ff6b6b;
}

.risk-badge.is-low {
  background: #8ad18a;
}

.posture-badge {
  color: var(--text1);
  background: rgba(255, 255, 255, 0.08);
}

.posture-badge.is-defensive {
  background: rgba(255, 107, 107, 0.18);
}

.posture-badge.is-selective,
.posture-badge.is-balanced {
  background: rgba(245, 166, 35, 0.18);
}

.posture-badge.is-offensive {
  background: rgba(40, 167, 69, 0.18);
}

.hero-updated {
  color: var(--text3);
  font-size: 11px;
}

.refresh-btn {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text2);
  cursor: pointer;
}

.macro-action-btn {
  border: 1px solid rgba(255, 107, 107, 0.28);
  border-radius: 999px;
  padding: 8px 12px;
  background: rgba(255, 107, 107, 0.12);
  color: #ffd2d2;
  font-size: 12px;
  cursor: pointer;
}

.macro-action-btn.secondary {
  border-color: rgba(245, 166, 35, 0.28);
  background: rgba(245, 166, 35, 0.12);
  color: #ffe5b4;
}

.summary-panel {
  padding: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.summary-block {
  min-width: 0;
}

.panel-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text1);
  margin-bottom: 10px;
}

.driver-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.driver-chip {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text2);
  font-size: 12px;
}

.driver-chip.positive {
  background: rgba(40, 167, 69, 0.16);
}

.driver-chip.caution,
.driver-chip.risk {
  background: rgba(255, 107, 107, 0.16);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.metric-card {
  padding: 14px;
}

.metric-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--text3);
  font-size: 11px;
}

.metric-name {
  color: var(--text2);
  font-size: 12px;
  margin: 10px 0 8px;
  min-height: 32px;
}

.metric-value {
  color: var(--text1);
  font-size: 24px;
  font-weight: 700;
}

.metric-change {
  font-size: 12px;
  margin-top: 8px;
}

.metric-change.up {
  color: var(--green);
}

.metric-change.dn {
  color: var(--red);
}

.metric-source {
  margin-top: 10px;
  font-size: 11px;
  color: var(--text3);
}

.empty-state {
  color: var(--text3);
  font-size: 12px;
}

@media (max-width: 720px) {
  .macro-shell {
    gap: 12px;
    padding: 12px;
  }

  .macro-hero,
  .summary-panel,
  .metric-card {
    padding: 14px;
  }

  .macro-hero {
    flex-direction: column;
  }

  .hero-side {
    align-items: flex-start;
    width: 100%;
  }

  .refresh-btn {
    width: 100%;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .metric-grid {
    grid-template-columns: 1fr;
  }

  .driver-chip {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
