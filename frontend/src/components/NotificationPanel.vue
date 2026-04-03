<template>
  <div class="notif-center-shell">
    <button
      v-if="isCollapsed"
      class="notif-center-toggle"
      :class="{ empty: totalNotifications === 0 }"
      type="button"
      aria-label="展開本地通知中心"
      aria-expanded="false"
      data-testid="notif-center-toggle"
      @click="expandPanel"
    >
      <div class="notif-center-toggle-copy">
        <div class="notif-center-toggle-title">本地通知中心</div>
        <div class="notif-center-toggle-meta">{{ launcherSummary }}</div>
      </div>
      <div class="notif-center-toggle-count">{{ totalNotifications }}</div>
    </button>

    <Transition name="notif-center-fade">
      <aside
        v-if="!isCollapsed"
        class="notif-center-panel"
        data-testid="notif-center-panel"
        @keydown.esc="collapsePanel"
      >
        <div class="notif-header">
          <div>
            <div class="notif-eyebrow">Notification Center</div>
            <div class="notif-title">本地通知中心</div>
          </div>
          <div class="notif-header-actions">
            <div class="notif-count">{{ visibleNotifications.length }}</div>
            <button
              class="notif-header-btn"
              type="button"
              aria-label="縮小本地通知中心"
              data-testid="notif-center-collapse"
              @click="collapsePanel"
            >
              縮小
            </button>
          </div>
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

            <div
              v-if="item.contextSource || item.contextGroupName || item.contextTags?.length || item.macroSummary"
              class="notif-context-row"
            >
              <span v-if="item.contextSource">{{ formatContextSource(item.contextSource) }}</span>
              <span v-if="item.contextGroupName" class="notif-context-tag">
                {{ formatContextGroup(item.contextGroupName) }}
              </span>
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

            <div
              v-if="item.ticker || item.workspaceTarget || item.persisted || item.category === 'session'"
              class="notif-action-row"
            >
              <button
                v-if="item.ticker"
                class="notif-action-btn"
                @click="$emit('open-ticker', item.ticker)"
              >
                開啟 {{ item.ticker }}
              </button>
              <button
                v-if="item.contextGroupName"
                class="notif-action-btn"
                @click="$emit('open-watch-group', { groupName: item.contextGroupName, ticker: item.ticker || null })"
              >
                開啟群組
              </button>
              <button
                v-if="item.category === 'alert' && item.ticker"
                class="notif-action-btn"
                @click="$emit('open-journal-entry', buildJournalSeed(item))"
              >
                寫入日誌
              </button>
              <button
                v-if="item.category === 'alert' && (item.ticker || item.macroSummary || item.contextTags?.length)"
                class="notif-action-btn"
                @click="$emit('save-journal-filter-preset', buildJournalPresetDraft(item))"
              >
                存成模板
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
    </Transition>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  notifications: { type: Array, required: true },
});

defineEmits([
  "dismiss",
  "toggle-read",
  "open-ticker",
  "open-workspace",
  "open-watch-group",
  "open-journal-entry",
  "save-journal-filter-preset",
]);

const isCollapsed = ref(true);
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

const totalNotifications = computed(() => (props.notifications || []).length);
const unreadNotifications = computed(() => (props.notifications || []).filter((item) => !item.read).length);
const launcherSummary = computed(() => {
  if (totalNotifications.value === 0) return "暫無通知";
  if (unreadNotifications.value === 0) return "全部已讀";
  return `${unreadNotifications.value} 則未讀`;
});

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
      item.contextGroupName,
      item.macroSummary?.overall_risk,
      item.macroSummary?.trade_posture,
      item.macroSummary?.decision_hint,
      ...(item.contextTags || []),
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword));
  });
});

function expandPanel() {
  isCollapsed.value = false;
}

function collapsePanel() {
  isCollapsed.value = true;
}

function formatCategory(value) {
  return CATEGORY_LABELS[value] || value || "通知";
}

function formatSource(value) {
  return SOURCE_LABELS[value] || value || "Unknown";
}

function formatContextSource(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "watchlist") return "來源：觀察池";
  if (normalized === "watchlist_group") return "來源：觀察群組";
  if (!value) return "";
  return `來源：${value}`;
}

function formatContextGroup(value) {
  return `群組：${value}`;
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
  const sourceTag = item.contextSource === "watchlist_group" ? "來源:觀察群組警報" : "來源:警報通知";
  const tags = [...new Set([
    ...(item.contextTags || []),
    item.contextGroupName ? `觀察群組:${item.contextGroupName}` : "",
    item.macroSummary ? `市場:${formatMacroPosture(item.macroSummary.trade_posture)}` : "",
    sourceTag,
  ].filter(Boolean))];
  const thresholdText = item.thresholdValue == null ? "—" : String(item.thresholdValue);
  const triggerText = item.triggerValue == null ? "—" : String(item.triggerValue);
  const macroContext = item.macroSummary
    ? `${formatMacroRisk(item.macroSummary.overall_risk)} | ${formatMacroPosture(item.macroSummary.trade_posture)}`
    : "";
  const snapshotParts = [
    item.payload?.snapshot_price == null ? "" : `快照:${item.payload.snapshot_price}`,
    item.payload?.snapshot_source ? `來源:${item.payload.snapshot_source}` : "",
    item.payload?.snapshot_timestamp ? `時間:${item.payload.snapshot_timestamp}` : "",
  ].filter(Boolean);
  return {
    ticker: item.ticker,
    name: item.ticker,
    entry_reason: `通知回寫：${item.title || item.ticker}`,
    review_notes: `${item.msg || ""} | 門檻:${thresholdText} | 觸發:${triggerText}${item.contextSource ? ` | ${formatContextSource(item.contextSource)}` : ""}${item.contextGroupName ? ` | ${formatContextGroup(item.contextGroupName)}` : ""}${snapshotParts.length ? ` | ${snapshotParts.join(" / ")}` : ""}${macroContext ? ` | ${macroContext}` : ""}${item.macroSummary?.decision_hint ? ` | ${item.macroSummary.decision_hint}` : ""}`,
    tags,
  };
}

function buildJournalPresetDraft(item) {
  const postureLabel = item?.macroSummary?.trade_posture ? formatMacroPosture(item.macroSummary.trade_posture) : "";
  const nameBase = item?.ticker || item?.title || "通知";
  return {
    name: `通知：${nameBase}`,
    description: "由通知中心快速建立",
    scope: "all",
    filters: {
      market: "",
      strategy_code: "",
      tag: item?.contextGroupName
        ? `觀察群組:${item.contextGroupName}`
        : (postureLabel ? `市場:${postureLabel}` : "來源:警報通知"),
      search: item?.ticker || "",
    },
  };
}
</script>

<style scoped>
.notif-center-shell {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 30;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  max-width: min(360px, calc(100vw - 24px));
  pointer-events: none;
}

.notif-center-toggle,
.notif-center-panel {
  width: min(360px, calc(100vw - 24px));
  pointer-events: auto;
}

.notif-center-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 16px;
  background: rgba(5, 10, 17, 0.94);
  backdrop-filter: blur(16px);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.3);
  cursor: pointer;
}

.notif-center-toggle.empty {
  opacity: 0.78;
}

.notif-center-toggle-copy {
  min-width: 0;
  text-align: left;
}

.notif-center-toggle-title {
  font-family: "Syne", sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: var(--text1);
}

.notif-center-toggle-meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text3);
}

.notif-center-toggle-count {
  min-width: 34px;
  padding: 6px 8px;
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.12);
  color: #7be7ff;
  font-size: 11px;
  text-align: center;
  flex-shrink: 0;
}

.notif-center-panel {
  position: relative;
  min-width: 280px;
  min-height: 240px;
  max-height: min(72vh, 680px);
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 16px;
  background: rgba(5, 10, 17, 0.96);
  backdrop-filter: blur(16px);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.38);
  overflow: hidden;
  resize: vertical;
}

.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 14px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
}

.notif-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.notif-header-btn {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text2);
  font-size: 11px;
  padding: 6px 10px;
  cursor: pointer;
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
  flex-shrink: 0;
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
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
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

.notif-center-fade-enter-active,
.notif-center-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.notif-center-fade-enter-from,
.notif-center-fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

@media (max-width: 640px) {
  .notif-center-shell {
    right: 12px;
    left: 12px;
    bottom: 12px;
    max-width: none;
  }

  .notif-center-toggle,
  .notif-center-panel {
    width: 100%;
    min-width: 0;
  }

  .notif-center-panel {
    max-height: min(68vh, 560px);
    resize: none;
  }
}
</style>
