<template>
  <aside class="notif-panel">
    <div class="notif-header">
      <div>
        <div class="notif-eyebrow">Notification Center</div>
        <div class="notif-title">本地通知中心</div>
      </div>
      <div class="notif-count">{{ visibleNotifications.length }}</div>
    </div>

    <div class="notif-controls">
      <div class="notif-filter-row">
        <button
          v-for="option in viewOptions"
          :key="option.value"
          class="notif-filter-btn"
          :class="{ active: viewMode === option.value }"
          @click="viewMode = option.value"
        >
          {{ option.label }}
        </button>
      </div>

      <input
        v-model.trim="searchText"
        class="notif-search"
        type="text"
        placeholder="搜尋標題、訊息或 ticker"
      />

      <div class="notif-filter-row chips">
        <button
          v-for="option in categoryOptions"
          :key="option.value"
          class="notif-chip"
          :class="{ active: categoryFilter === option.value }"
          @click="categoryFilter = option.value"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <div v-if="visibleNotifications.length" class="notif-list">
      <div
        v-for="item in visibleNotifications"
        :key="item.id"
        class="notif-card"
        :class="[item.type, { read: item.read }]"
      >
        <div class="notif-card-top">
          <div class="notif-icon">{{ item.icon }}</div>
          <div class="notif-main">
            <div class="notif-card-title-row">
              <div class="notif-card-title">{{ item.title }}</div>
              <div class="notif-read-badge" :class="{ unread: !item.read }">
                {{ item.read ? "已讀" : "未讀" }}
              </div>
            </div>
            <div class="notif-card-msg">{{ item.msg }}</div>
          </div>
        </div>

        <div class="notif-meta-row">
          <span>{{ formatCategory(item.category) }}</span>
          <span>{{ formatSource(item.source) }}</span>
          <span>{{ item.time || "—" }}</span>
        </div>

        <div v-if="item.contextSource || item.contextTags?.length || item.macroSummary" class="notif-context-row">
          <span v-if="item.contextSource">{{ formatContextSource(item.contextSource) }}</span>
          <span v-if="item.macroSummary" class="notif-context-tag">
            {{ formatMacroRisk(item.macroSummary.overall_risk) }}
          </span>
          <span v-if="item.macroSummary" class="notif-context-tag">
            {{ formatMacroPosture(item.macroSummary.trade_posture) }}
          </span>
          <span
            v-for="tag in item.contextTags || []"
            :key="`${item.id}-${tag}`"
            class="notif-context-tag"
          >
            {{ tag }}
          </span>
        </div>

        <div v-if="item.ticker || item.workspaceTarget || item.persisted || item.category === 'session'" class="notif-action-row">
          <button
            v-if="item.ticker"
            class="notif-action-btn"
            @click="$emit('open-ticker', item.ticker)"
          >
            開啟 {{ item.ticker }}
          </button>
          <button
            v-if="item.category === 'alert' && item.ticker"
            class="notif-action-btn"
            @click="$emit('open-journal-entry', buildJournalSeed(item))"
          >
            寫入日誌
          </button>
          <button
            v-if="item.workspaceTarget"
            class="notif-action-btn"
            @click="$emit('open-workspace', item.workspaceTarget)"
          >
            開啟宏觀
          </button>
          <button
            v-if="item.persisted"
            class="notif-action-btn"
            @click="$emit('toggle-read', { id: item.id, read: !item.read })"
          >
            {{ item.read ? "標記未讀" : "標記已讀" }}
          </button>
          <button
            v-if="item.category === 'session'"
            class="notif-action-btn danger"
            @click="$emit('dismiss', item.id)"
          >
            關閉
          </button>
        </div>
      </div>
    </div>
    <div v-else class="notif-empty">目前沒有符合條件的通知</div>
  </aside>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  notifications: { type: Array, required: true },
});

defineEmits(["dismiss", "toggle-read", "open-ticker", "open-workspace", "open-journal-entry"]);

const viewMode = ref("all");
const categoryFilter = ref("all");
const searchText = ref("");

const CATEGORY_LABELS = {
  alert: "警報",
  system: "系統",
  session: "本次操作",
};

const SOURCE_LABELS = {
  yahoo_finance: "Yahoo Finance",
  local_db: "Local DB",
  session: "Session",
};

const viewOptions = [
  { value: "all", label: "全部" },
  { value: "unread", label: "未讀" },
];

const categoryOptions = computed(() => {
  const categories = Array.from(new Set((props.notifications || []).map((item) => item.category).filter(Boolean)));
  return [
    { value: "all", label: "全部類別" },
    ...categories.map((value) => ({
      value,
      label: formatCategory(value),
    })),
  ];
});

const visibleNotifications = computed(() => {
  const keyword = searchText.value.trim().toLowerCase();
  return (props.notifications || []).filter((item) => {
    if (viewMode.value === "unread" && item.read) return false;
    if (categoryFilter.value !== "all" && item.category !== categoryFilter.value) return false;
    if (!keyword) return true;
    return [
      item.title,
      item.msg,
      item.ticker,
      item.workspaceTarget,
      item.macroSummary?.overall_risk,
      item.macroSummary?.trade_posture,
      item.macroSummary?.decision_hint,
      ...(item.contextTags || []),
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword));
  });
});

function formatCategory(value) {
  return CATEGORY_LABELS[value] || value || "通知";
}

function formatSource(value) {
  return SOURCE_LABELS[value] || value || "Unknown";
}

function formatContextSource(value) {
  if (String(value || "").toLowerCase() === "watchlist") return "來源：觀察池";
  if (!value) return "";
  return `來源：${value}`;
}

function formatMacroRisk(value) {
  const labels = {
    high: "風險：高",
    medium: "風險：中",
    low: "風險：低",
    unknown: "風險：未知",
  };
  return labels[String(value || "").toLowerCase()] || `風險：${value || "未知"}`;
}

function formatMacroPosture(value) {
  const labels = {
    defensive: "防守控倉",
    selective: "選擇性出手",
    offensive: "偏進攻",
    balanced: "平衡觀察",
    standby: "等待同步",
  };
  return labels[String(value || "").toLowerCase()] || String(value || "等待同步");
}

function buildJournalSeed(item) {
  const tags = [...new Set([
    ...(item.contextTags || []),
    item.macroSummary ? `市場:${formatMacroPosture(item.macroSummary.trade_posture)}` : "",
    "來源:警報通知",
  ].filter(Boolean))];
  const thresholdText = item.thresholdValue == null ? "—" : String(item.thresholdValue);
  const triggerText = item.triggerValue == null ? "—" : String(item.triggerValue);
  const macroContext = item.macroSummary
    ? `${formatMacroRisk(item.macroSummary.overall_risk)} | ${formatMacroPosture(item.macroSummary.trade_posture)}`
    : "";
  return {
    ticker: item.ticker,
    name: item.ticker,
    entry_reason: `通知回寫：${item.title || item.ticker}`,
    review_notes: `${item.msg || ""} | 門檻:${thresholdText} | 觸發:${triggerText}${item.contextSource ? ` | ${formatContextSource(item.contextSource)}` : ""}${macroContext ? ` | ${macroContext}` : ""}${item.macroSummary?.decision_hint ? ` | ${item.macroSummary.decision_hint}` : ""}`,
    tags,
  };
}
</script>

<style scoped>
.notif-panel {
  position: fixed;
  right: 18px;
  bottom: 18px;
  width: min(360px, calc(100vw - 24px));
  max-height: min(72vh, 680px);
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 16px;
  background: rgba(5, 10, 17, 0.96);
  backdrop-filter: blur(16px);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.38);
  overflow: hidden;
  z-index: 30;
}

.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 14px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.notif-eyebrow {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text3);
}

.notif-title {
  margin-top: 2px;
  font-family: "Syne", sans-serif;
  font-size: 15px;
  font-weight: 700;
  color: var(--text1);
}

.notif-count {
  min-width: 36px;
  padding: 6px 8px;
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.12);
  color: #7be7ff;
  font-size: 11px;
  text-align: center;
}

.notif-controls {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.notif-filter-row {
  display: flex;
  gap: 8px;
}

.notif-filter-row.chips {
  flex-wrap: wrap;
  margin-top: 10px;
}

.notif-filter-btn,
.notif-chip,
.notif-action-btn {
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
}

.notif-filter-btn {
  flex: 1;
  padding: 8px 10px;
  border-radius: 10px;
  font-size: 11px;
}

.notif-filter-btn.active,
.notif-chip.active {
  border-color: rgba(123, 231, 255, 0.28);
  background: rgba(123, 231, 255, 0.12);
  color: #7be7ff;
}

.notif-search {
  width: 100%;
  margin-top: 10px;
  padding: 9px 10px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text1);
  font-size: 12px;
}

.notif-chip {
  padding: 6px 9px;
  border-radius: 999px;
  font-size: 10px;
}

.notif-list {
  flex: 1;
  overflow: auto;
  padding: 12px 14px 14px;
}

.notif-card {
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
}

.notif-card + .notif-card {
  margin-top: 10px;
}

.notif-card.read {
  opacity: 0.76;
}

.notif-card-top {
  display: flex;
  gap: 10px;
}

.notif-icon {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.notif-main {
  min-width: 0;
  flex: 1;
}

.notif-card-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.notif-card-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text1);
}

.notif-read-badge {
  flex-shrink: 0;
  padding: 3px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text3);
  font-size: 10px;
}

.notif-read-badge.unread {
  background: rgba(255, 209, 102, 0.14);
  color: #ffd166;
}

.notif-card-msg {
  margin-top: 6px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--text2);
}

.notif-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 9px;
  font-size: 10px;
  color: var(--text3);
}

.notif-action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.notif-context-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.notif-context-tag {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.1);
  color: #7be7ff;
  font-size: 10px;
}

.notif-action-btn {
  padding: 7px 9px;
  border-radius: 9px;
  font-size: 10px;
}

.notif-action-btn.danger {
  border-color: rgba(255, 77, 106, 0.24);
  color: #ff8a9d;
}

.notif-empty {
  padding: 24px 16px;
  color: var(--text3);
  font-size: 11px;
  text-align: center;
}

@media (max-width: 640px) {
  .notif-panel {
    right: 12px;
    left: 12px;
    bottom: 12px;
    width: auto;
    max-height: 60vh;
  }
}
</style>
