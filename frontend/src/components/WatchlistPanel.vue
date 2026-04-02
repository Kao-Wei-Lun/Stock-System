<template>
  <div class="left-panel">
    <div class="panel-tabs">
      <div class="ptab" :class="{ active: leftTab === 'watch' }" @click="$emit('set-left-tab', 'watch')">自選股</div>
      <div class="ptab" :class="{ active: leftTab === 'market' }" @click="$emit('set-left-tab', 'market')">大盤</div>
    </div>

    <div v-if="!loading && !error && leftTab === 'watch'" class="watchlist-controls">
      <div class="group-bar">
        <button
          v-for="group in groups"
          :key="group.id"
          class="group-pill"
          :class="{ active: group.id === activeGroupId }"
          @click="$emit('select-group', group.id)"
        >
          <span>{{ group.name }}</span>
          <span class="group-count">{{ group.items?.length || 0 }}</span>
        </button>
        <button class="group-pill add" @click="toggleCreateGroup">
          {{ createGroupOpen ? "取消" : "＋ 群組" }}
        </button>
      </div>

      <div v-if="createGroupOpen" class="watchlist-form">
        <input
          v-model.trim="newGroupName"
          type="text"
          placeholder="新增觀察群組"
          @keydown.enter.prevent="submitGroup"
        />
        <button @click="submitGroup">建立</button>
      </div>

      <div v-if="leftTab === 'watch' && selectedGroup" class="watchlist-form">
        <template v-if="editingGroupId === selectedGroup.id">
          <input
            v-model.trim="editGroupName"
            type="text"
            placeholder="重新命名群組"
            @keydown.enter.prevent="submitRenameGroup"
          />
          <button @click="submitRenameGroup">儲存</button>
          <button class="ghost" @click="cancelRenameGroup">取消</button>
        </template>
        <template v-else>
          <button class="secondary" @click="beginRenameGroup(selectedGroup)">✎ 重新命名</button>
          <button class="danger" @click="requestDeleteGroup(selectedGroup)">🗑 刪除群組</button>
        </template>
      </div>

      <div v-if="leftTab === 'watch'" class="watchlist-form">
        <input
          v-model.trim="newTicker"
          type="text"
          placeholder="新增代號，例如 AAPL / 2330"
          @keydown.enter.prevent="submitTicker"
        />
        <button :disabled="!activeGroupId || !newTicker" @click="submitTicker">加入</button>
      </div>
    </div>

    <div class="watchlist">
      <div v-if="loading" class="loading-wl">
        <div style="width: 20px; height: 20px; border: 2px solid var(--border2); border-top-color: var(--green); border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto 8px;"></div>
        載入自選股...
      </div>
      <div v-else-if="error" class="loading-wl" style="color: var(--red)">⚠ 無法連線後端</div>
      <template v-else-if="visibleItems.length">
        <div class="sec-label">{{ sectionLabel }}</div>
        <div
          v-for="item in visibleItems"
          :key="`${item.group_id || 'market'}-${item.ticker}`"
          class="wl-item"
          :class="{ active: item.ticker === activeTicker }"
          @click="$emit('select-ticker', item)"
        >
          <div>
            <div class="wl-ticker">{{ item.ticker }}</div>
            <div class="wl-name">{{ item.name || "" }}<span v-if="item.category"> · {{ item.category }}</span></div>
            <div class="wl-meta-row">
              <span class="wl-meta-pill" :class="getFreshnessClass(item)">{{ getFreshnessLabel(item) }}</span>
              <span class="wl-meta-text">{{ formatSourceLabel(item.source) }}</span>
              <span class="wl-meta-text">{{ formatWatchTimestamp(item) }}</span>
            </div>
          </div>
          <div class="wl-side">
            <div v-if="leftTab === 'watch' && selectedGroup" class="wl-ops">
              <button class="wl-op" title="上移" :disabled="!canMoveItem(item, -1)" @click.stop="moveItem(item, -1)">↑</button>
              <button class="wl-op" title="下移" :disabled="!canMoveItem(item, 1)" @click.stop="moveItem(item, 1)">↓</button>
              <button class="wl-op danger" title="移除" @click.stop="removeItem(item)">✕</button>
            </div>
            <div class="wl-price" :class="item.change_pct >= 0 ? 'up' : 'dn'">{{ fmtPrice(item.close) }}</div>
            <div class="wl-chg" :class="item.change_pct >= 0 ? 'up' : 'dn'">
              {{ item.change_pct >= 0 ? "+" : "" }}{{ Number(item.change_pct || 0).toFixed(2) }}%
            </div>
          </div>
        </div>
      </template>
      <div v-else class="loading-wl">{{ emptyLabel }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import { fmtPrice } from "../utils/formatters";

const props = defineProps({
  groups: { type: Array, required: true },
  marketItems: { type: Array, required: true },
  items: { type: Array, required: true },
  leftTab: { type: String, required: true },
  activeGroupId: { type: Number, default: null },
  activeTicker: { type: String, required: true },
  loading: { type: Boolean, required: true },
  error: { type: Boolean, required: true },
});

const emit = defineEmits([
  "set-left-tab",
  "select-group",
  "create-group",
  "rename-group",
  "delete-group",
  "add-to-watchlist",
  "remove-from-watchlist",
  "reorder-items",
  "select-ticker",
]);

const createGroupOpen = ref(false);
const newGroupName = ref("");
const newTicker = ref("");
const editingGroupId = ref(null);
const editGroupName = ref("");

const selectedGroup = computed(
  () => props.groups.find((group) => group.id === props.activeGroupId) || props.groups[0] || null,
);

const visibleItems = computed(() => {
  if (props.leftTab === "market") {
    return props.marketItems;
  }
  return selectedGroup.value?.items || [];
});

const sectionLabel = computed(() => {
  if (props.leftTab === "market") return "全球大盤與原物料";
  return selectedGroup.value?.name || "我的自選";
});

const emptyLabel = computed(() => {
  if (props.leftTab === "market") return "目前沒有市場指標資料";
  if (!props.groups.length) return "尚未建立觀察群組";
  return "這個群組目前還沒有股票";
});

const SOURCE_LABELS = {
  yahoo_finance: "Yahoo Finance",
  local_cache: "Local cache",
};

function parseWatchTimestamp(value) {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function resolveWatchTimestamp(item) {
  return item?.quote_timestamp || item?.synced_at || item?.date || null;
}

function formatSourceLabel(source) {
  return SOURCE_LABELS[source] || source || "Unknown source";
}

function formatWatchTimestamp(item) {
  const parsed = parseWatchTimestamp(resolveWatchTimestamp(item));
  if (!parsed) return "無時間戳";
  return parsed.toLocaleString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function isStaleItem(item) {
  const parsed = parseWatchTimestamp(resolveWatchTimestamp(item));
  if (!parsed) return true;
  return Date.now() - parsed.getTime() > 24 * 60 * 60 * 1000;
}

function getFreshnessLabel(item) {
  if (isStaleItem(item)) return "資料較舊";
  return item?.is_delayed === false ? "即時" : "延遲快照";
}

function getFreshnessClass(item) {
  if (isStaleItem(item)) return "stale";
  return item?.is_delayed === false ? "live" : "delayed";
}

function toggleCreateGroup() {
  createGroupOpen.value = !createGroupOpen.value;
  if (!createGroupOpen.value) newGroupName.value = "";
}

function submitGroup() {
  if (!newGroupName.value) return;
  emit("create-group", newGroupName.value);
  newGroupName.value = "";
  createGroupOpen.value = false;
}

function submitTicker() {
  if (!newTicker.value || !props.activeGroupId) return;
  emit("add-to-watchlist", newTicker.value, props.activeGroupId);
  newTicker.value = "";
}

function beginRenameGroup(group) {
  editingGroupId.value = group.id;
  editGroupName.value = group.name || "";
}

function cancelRenameGroup() {
  editingGroupId.value = null;
  editGroupName.value = "";
}

function submitRenameGroup() {
  if (!editingGroupId.value || !editGroupName.value) return;
  emit("rename-group", editingGroupId.value, editGroupName.value);
  cancelRenameGroup();
}

function requestDeleteGroup(group) {
  if (!window.confirm(`確定要刪除群組「${group.name}」嗎？`)) return;
  emit("delete-group", group.id);
}

function canMoveItem(item, direction) {
  const items = selectedGroup.value?.items || [];
  const index = items.findIndex((candidate) => candidate.id === item.id);
  const targetIndex = index + direction;
  return index >= 0 && targetIndex >= 0 && targetIndex < items.length;
}

function moveItem(item, direction) {
  const items = [...(selectedGroup.value?.items || [])];
  const index = items.findIndex((candidate) => candidate.id === item.id);
  const targetIndex = index + direction;
  if (index < 0 || targetIndex < 0 || targetIndex >= items.length) return;
  [items[index], items[targetIndex]] = [items[targetIndex], items[index]];
  emit("reorder-items", props.activeGroupId, items.map((entry) => entry.id));
}

function removeItem(item) {
  if (!window.confirm(`確定要從群組移除 ${item.ticker} 嗎？`)) return;
  emit("remove-from-watchlist", item.id);
}
</script>

<style scoped>
.wl-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.wl-meta-pill {
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 9px;
  line-height: 1.4;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
}

.wl-meta-pill.live {
  background: rgba(0, 217, 163, 0.12);
  color: var(--green);
}

.wl-meta-pill.delayed {
  background: rgba(255, 209, 102, 0.14);
  color: #ffd166;
}

.wl-meta-pill.stale {
  background: rgba(255, 77, 106, 0.14);
  color: #ff8a9d;
}

.wl-meta-text {
  font-size: 9px;
  line-height: 1.6;
  color: var(--text3);
}
</style>
