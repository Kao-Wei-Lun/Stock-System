<template>
  <div
    ref="shellRef"
    class="notif-center-shell"
    :class="shellClasses"
    :style="shellStyle"
  >
    <div v-if="isCollapsed" class="notif-center-collapsed-row">
      <button
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
      <button
        class="notif-center-mini-drag"
        type="button"
        title="移動已縮小的通知中心；方向鍵可微調"
        aria-label="移動已縮小的通知中心；方向鍵可微調"
        data-testid="notif-collapsed-drag-handle"
        @pointerdown="startDrag"
        @pointermove="moveDrag"
        @pointerup="endDrag"
        @pointercancel="endDrag"
        @keydown="moveWithKeyboard"
      >
        ⠿
      </button>
    </div>

    <Transition name="notif-center-fade">
      <aside
        v-if="!isCollapsed"
        ref="panelRef"
        class="notif-center-panel"
        :style="panelStyle"
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

        <div class="notif-layout-toolbar" aria-label="通知中心位置控制">
          <div class="notif-layout-docks" role="group" aria-label="快速停靠位置">
            <button
              v-for="option in anchorOptions"
              :key="option.value"
              class="notif-layout-btn dock"
              :class="{ active: layout.anchor === option.value }"
              type="button"
              :title="option.label"
              :aria-label="option.label"
              :aria-pressed="layout.anchor === option.value"
              :data-testid="`notif-dock-${option.value}`"
              @click="dockPanel(option.value)"
            >
              {{ option.icon }}
            </button>
          </div>
          <button
            class="notif-layout-btn drag"
            :class="{ active: layout.anchor === 'custom' }"
            type="button"
            title="拖曳通知中心；方向鍵可微調"
            aria-label="拖曳通知中心；方向鍵可微調"
            data-testid="notif-drag-handle"
            @pointerdown="startDrag"
            @pointermove="moveDrag"
            @pointerup="endDrag"
            @pointercancel="endDrag"
            @keydown="moveWithKeyboard"
          >
            ⠿ 移動
          </button>
          <button
            class="notif-layout-btn reset"
            type="button"
            title="重設通知中心位置與高度"
            aria-label="重設通知中心位置與高度"
            data-testid="notif-layout-reset"
            @click="resetPanelLayout"
          >
            重設
          </button>
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
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
} from "vue";

import {
  DEFAULT_NOTIFICATION_LAYOUT,
  NOTIFICATION_PANEL_ANCHORS,
  anchorClassName,
  clampFloatingPanelPosition,
  loadNotificationLayout,
  saveNotificationLayout,
} from "../utils/floatingPanelLayout";

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

const initialLayout = loadNotificationLayout();
const layout = ref(initialLayout);
const isCollapsed = ref(initialLayout.collapsed);
const viewMode = ref("all");
const categoryFilter = ref("all");
const searchText = ref("");
const shellRef = ref(null);
const panelRef = ref(null);
const isCompactViewport = ref(false);
const isDragging = ref(false);

let activePointerId = null;
let dragOffset = { x: 0, y: 0 };
let panelResizeObserver = null;

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

const anchorOptions = NOTIFICATION_PANEL_ANCHORS.map((value) => ({
  value,
  icon: {
    "top-left": "↖",
    "top-right": "↗",
    "bottom-left": "↙",
    "bottom-right": "↘",
  }[value],
  label: {
    "top-left": "停靠左上",
    "top-right": "停靠右上",
    "bottom-left": "停靠左下",
    "bottom-right": "停靠右下",
  }[value],
}));

const shellClasses = computed(() => [
  anchorClassName(isCompactViewport.value ? "bottom-right" : layout.value.anchor),
  {
    "is-compact": isCompactViewport.value,
    "is-dragging": isDragging.value,
  },
]);

const shellStyle = computed(() => {
  if (isCompactViewport.value || layout.value.anchor !== "custom") return {};
  return {
    left: `${layout.value.x}px`,
    top: `${layout.value.y}px`,
    right: "auto",
    bottom: "auto",
  };
});

const panelStyle = computed(() => {
  if (isCompactViewport.value || !layout.value.panelHeight) return {};
  return { height: `${layout.value.panelHeight}px` };
});

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
  persistLayout({ collapsed: false });
  nextTick(() => {
    observePanelResize();
    clampCustomPosition();
  });
}

function collapsePanel() {
  isCollapsed.value = true;
  persistLayout({ collapsed: true });
  disconnectPanelResizeObserver();
  nextTick(clampCustomPosition);
}

function persistLayout(patch = {}) {
  layout.value = saveNotificationLayout({
    ...layout.value,
    ...patch,
    collapsed: patch.collapsed ?? isCollapsed.value,
  });
}

function dockPanel(anchor) {
  if (!NOTIFICATION_PANEL_ANCHORS.includes(anchor) || isCompactViewport.value) return;
  persistLayout({ anchor, x: null, y: null });
}

function resetPanelLayout() {
  layout.value = saveNotificationLayout({
    ...DEFAULT_NOTIFICATION_LAYOUT,
    collapsed: isCollapsed.value,
  });
  nextTick(observePanelResize);
}

function viewportSize() {
  const visualViewport = globalThis.visualViewport;
  return {
    width: Number(visualViewport?.width || globalThis.innerWidth || 0),
    height: Number(visualViewport?.height || globalThis.innerHeight || 0),
  };
}

function clampedPosition(position) {
  const shell = shellRef.value;
  const rect = shell?.getBoundingClientRect?.();
  const viewport = viewportSize();
  return clampFloatingPanelPosition(position, {
    panelWidth: rect?.width || 360,
    panelHeight: rect?.height || 64,
    viewportWidth: viewport.width,
    viewportHeight: viewport.height,
  });
}

function clampCustomPosition({ persist = true } = {}) {
  if (isCompactViewport.value || layout.value.anchor !== "custom") return;
  const nextPosition = clampedPosition({ x: layout.value.x, y: layout.value.y });
  if (nextPosition.x === layout.value.x && nextPosition.y === layout.value.y) return;
  layout.value = { ...layout.value, ...nextPosition };
  if (persist) persistLayout();
}

function startDrag(event) {
  if (isCompactViewport.value || (event.button != null && event.button !== 0)) return;
  const rect = shellRef.value?.getBoundingClientRect?.();
  if (!rect) return;
  activePointerId = event.pointerId;
  dragOffset = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  };
  isDragging.value = true;
  layout.value = {
    ...layout.value,
    anchor: "custom",
    x: Math.round(rect.left),
    y: Math.round(rect.top),
  };
  event.currentTarget?.setPointerCapture?.(event.pointerId);
  event.preventDefault?.();
}

function moveDrag(event) {
  if (!isDragging.value || event.pointerId !== activePointerId) return;
  const nextPosition = clampedPosition({
    x: event.clientX - dragOffset.x,
    y: event.clientY - dragOffset.y,
  });
  layout.value = {
    ...layout.value,
    anchor: "custom",
    ...nextPosition,
  };
  event.preventDefault?.();
}

function endDrag(event) {
  if (!isDragging.value || event.pointerId !== activePointerId) return;
  event.currentTarget?.releasePointerCapture?.(event.pointerId);
  activePointerId = null;
  isDragging.value = false;
  persistLayout();
}

function moveWithKeyboard(event) {
  if (isCompactViewport.value) return;
  const directions = {
    ArrowLeft: [-1, 0],
    ArrowRight: [1, 0],
    ArrowUp: [0, -1],
    ArrowDown: [0, 1],
  };
  const direction = directions[event.key];
  if (!direction) return;
  const rect = shellRef.value?.getBoundingClientRect?.();
  if (!rect) return;
  const step = event.shiftKey ? 1 : 10;
  const origin = layout.value.anchor === "custom"
    ? { x: layout.value.x, y: layout.value.y }
    : { x: rect.left, y: rect.top };
  const nextPosition = clampedPosition({
    x: origin.x + (direction[0] * step),
    y: origin.y + (direction[1] * step),
  });
  layout.value = {
    ...layout.value,
    anchor: "custom",
    ...nextPosition,
  };
  persistLayout();
  event.preventDefault();
}

function disconnectPanelResizeObserver() {
  panelResizeObserver?.disconnect?.();
  panelResizeObserver = null;
}

function observePanelResize() {
  disconnectPanelResizeObserver();
  if (
    isCollapsed.value
    || isCompactViewport.value
    || !panelRef.value
    || typeof globalThis.ResizeObserver !== "function"
  ) {
    return;
  }

  let previousHeight = Math.round(panelRef.value.getBoundingClientRect().height);
  panelResizeObserver = new ResizeObserver((entries) => {
    const height = Math.round(entries[0]?.contentRect?.height || 0);
    if (!height || Math.abs(height - previousHeight) < 2) return;
    previousHeight = height;
    persistLayout({ panelHeight: height });
    nextTick(clampCustomPosition);
  });
  panelResizeObserver.observe(panelRef.value);
}

function updateViewportLayout() {
  isCompactViewport.value = Number(globalThis.innerWidth || 0) <= 640;
  nextTick(() => {
    clampCustomPosition();
    observePanelResize();
  });
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

onMounted(() => {
  updateViewportLayout();
  globalThis.addEventListener?.("resize", updateViewportLayout);
  globalThis.addEventListener?.("orientationchange", updateViewportLayout);
  globalThis.visualViewport?.addEventListener?.("resize", updateViewportLayout);
  nextTick(() => {
    clampCustomPosition();
    observePanelResize();
  });
});

onBeforeUnmount(() => {
  disconnectPanelResizeObserver();
  globalThis.removeEventListener?.("resize", updateViewportLayout);
  globalThis.removeEventListener?.("orientationchange", updateViewportLayout);
  globalThis.visualViewport?.removeEventListener?.("resize", updateViewportLayout);
});
</script>

<style scoped>
.notif-center-shell {
  position: fixed;
  z-index: 320;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: min(360px, calc(100vw - 24px));
  pointer-events: none;
}

.notif-center-shell.is-top-left {
  top: 18px;
  left: 18px;
  align-items: flex-start;
}

.notif-center-shell.is-top-right {
  top: 18px;
  right: 18px;
  align-items: flex-end;
}

.notif-center-shell.is-bottom-left {
  bottom: 18px;
  left: 18px;
  align-items: flex-start;
}

.notif-center-shell.is-bottom-right {
  right: 18px;
  bottom: 18px;
  align-items: flex-end;
}

.notif-center-shell.is-custom {
  align-items: flex-start;
}

.notif-center-shell.is-dragging {
  user-select: none;
}

.notif-center-collapsed-row,
.notif-center-panel {
  width: min(360px, calc(100vw - 24px));
  pointer-events: auto;
}

.notif-center-collapsed-row {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.notif-center-toggle {
  min-width: 0;
  flex: 1;
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

.notif-center-mini-drag {
  width: 40px;
  flex: 0 0 40px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 14px;
  background: rgba(5, 10, 17, 0.94);
  color: var(--text3);
  backdrop-filter: blur(16px);
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.3);
  cursor: grab;
  touch-action: none;
}

.notif-center-mini-drag:hover,
.notif-center-mini-drag:focus-visible {
  border-color: rgba(123, 231, 255, 0.32);
  background: rgba(123, 231, 255, 0.1);
  color: #b9f5ff;
}

.notif-center-shell.is-dragging .notif-center-mini-drag {
  cursor: grabbing;
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
  max-height: min(calc(100vh - 36px), 680px);
  max-height: min(calc(100dvh - 36px), 680px);
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

.notif-layout-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.018);
  flex-shrink: 0;
}

.notif-layout-docks {
  display: flex;
  gap: 4px;
}

.notif-layout-btn {
  min-width: 28px;
  min-height: 28px;
  padding: 0 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text3);
  cursor: pointer;
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
}

.notif-layout-btn:hover,
.notif-layout-btn:focus-visible,
.notif-layout-btn.active {
  border-color: rgba(123, 231, 255, 0.32);
  background: rgba(123, 231, 255, 0.1);
  color: #b9f5ff;
}

.notif-layout-btn.drag {
  margin-left: auto;
  cursor: grab;
  touch-action: none;
}

.notif-center-shell.is-dragging .notif-layout-btn.drag {
  cursor: grabbing;
}

.notif-layout-btn.reset {
  color: var(--text2);
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
    top: auto !important;
    right: 12px !important;
    bottom: 12px !important;
    left: 12px !important;
    max-width: none;
    align-items: stretch;
  }

  .notif-center-collapsed-row,
  .notif-center-panel {
    width: 100%;
    min-width: 0;
  }

  .notif-center-mini-drag {
    display: none;
  }

  .notif-center-panel {
    max-height: min(68vh, 560px);
    resize: none;
  }

  .notif-layout-toolbar {
    display: none;
  }
}
</style>
