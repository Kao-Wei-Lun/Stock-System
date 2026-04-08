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
          :style="getGroupAccentStyle(group)"
          @click="$emit('select-group', group.id)"
        >
          <span class="group-pill-color" :style="getGroupColorStyle(group.color)"></span>
          <span>{{ group.name }}</span>
          <span class="group-count">{{ group.items?.length || 0 }}</span>
        </button>
        <button class="group-pill add" @click="toggleCreateGroup">
          {{ createGroupOpen ? "取消" : "＋ 群組" }}
        </button>
        <button
          v-if="watchGroupAlertPayloads.length"
          class="reset-view-btn"
          data-testid="watch-batch-alerts"
          @click="$emit('create-alerts-batch', watchGroupAlertPayloads)"
        >
          &#25209;&#27425;&#35686;&#22577; ({{ watchGroupAlertPayloads.length }})
        </button>
      </div>

      <div v-if="createGroupOpen" class="watchlist-form">
        <input
          v-model.trim="newGroupName"
          type="text"
          placeholder="新增觀察群組"
          @keydown.enter.prevent="submitGroup"
        />
        <div class="group-swatch-row">
          <button
            v-for="color in colorOptions"
            :key="`new-${color}`"
            class="group-swatch"
            :class="{ active: newGroupColor === color }"
            type="button"
            :style="{ '--group-color': color }"
            @click="newGroupColor = color"
          ></button>
        </div>
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
          <div class="group-swatch-row">
            <button
              v-for="color in colorOptions"
              :key="`edit-${color}`"
              class="group-swatch"
              :class="{ active: editGroupColor === color }"
              type="button"
              :style="{ '--group-color': color }"
              @click="editGroupColor = color"
            ></button>
          </div>
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

      <div v-if="leftTab === 'watch' && selectedGroup" class="watchlist-viewbar">
        <label class="watchlist-viewfield">
          <span>Verdict</span>
          <select v-model="watchVerdictFilter" data-testid="watch-verdict-filter">
            <option value="all">全部</option>
            <option value="priority">優先候選</option>
            <option value="watch">觀察名單</option>
            <option value="wait">等待名單</option>
          </select>
        </label>
        <label class="watchlist-viewfield">
          <span>Q值</span>
          <select v-model="watchSetupFilter" data-testid="watch-setup-filter">
            <option value="all">全部</option>
            <option value="q4">Q4 以上</option>
            <option value="q3">Q3 以上</option>
          </select>
        </label>
        <label class="watchlist-viewfield">
          <span>市場</span>
          <select v-model="watchPostureFilter" data-testid="watch-posture-filter">
            <option value="all">全部</option>
            <option
              v-for="option in watchPostureOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="watchlist-viewfield">
          <span>排序</span>
          <select v-model="watchSortMode" data-testid="watch-sort-mode">
            <option value="manual">群組順序</option>
            <option value="verdict">Verdict 優先</option>
            <option value="setup_desc">Q值優先</option>
            <option value="change_pct">漲跌幅</option>
            <option value="freshness">資料新鮮度</option>
          </select>
        </label>
        <button
          v-if="hasWatchTransforms"
          class="reset-view-btn"
          data-testid="reset-watch-view"
          @click="resetWatchView"
        >
          重設
        </button>
      </div>

      <div
        v-if="leftTab === 'watch' && selectedGroup"
        class="watchlist-summary"
        data-testid="watchlist-summary"
      >
        {{ watchSummary }}
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
          :data-ticker="item.ticker"
          :style="getGroupAccentStyle(item)"
          @click="$emit('select-ticker', item)"
        >
          <span class="wl-item-accent" :style="getGroupColorStyle(item.group_color)"></span>
          <div>
            <div class="wl-ticker">{{ item.ticker }}</div>
            <div class="wl-name">{{ item.name || "" }}<span v-if="item.category"> &#183; {{ item.category }}</span></div>
            <div class="wl-meta-row">
              <span class="wl-meta-pill" :class="getFreshnessClass(item)">{{ getFreshnessLabel(item) }}</span>
              <span class="wl-meta-text">{{ formatSourceLabel(item.source) }}</span>
              <span class="wl-meta-text">{{ formatWatchTimestamp(item) }}</span>
            </div>
            <div v-if="getWatchTags(item).length" class="wl-tag-row">
              <span
                v-for="tag in getWatchTags(item)"
                :key="`${item.ticker}-${tag}`"
                class="wl-tag-pill"
              >
                {{ tag }}
              </span>
            </div>
          </div>
          <div class="wl-side">
            <div class="wl-shortcuts">
              <button
                class="wl-shortcut"
                :data-testid="`watch-journal-${item.ticker}`"
                title="建立日誌草稿"
                @click.stop="openJournalEntry(item)"
              >
                日誌
              </button>
              <button
                class="wl-shortcut"
                :data-testid="`watch-alert-${item.ticker}`"
                title="建立警報"
                @click.stop="openAlertShortcut(item)"
              >
                警報
              </button>
            </div>
            <div v-if="manualOrderingEnabled" class="wl-ops">
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
import { computed, ref, watch } from "vue";

import { WATCHLIST_COLOR_OPTIONS } from "../composables/useDashboard";
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
  "open-journal-entry",
  "open-alert-modal",
  "create-alerts-batch",
]);

const createGroupOpen = ref(false);
const newGroupName = ref("");
const newGroupColor = ref(WATCHLIST_COLOR_OPTIONS[0]);
const newTicker = ref("");
const editingGroupId = ref(null);
const editGroupName = ref("");
const editGroupColor = ref(WATCHLIST_COLOR_OPTIONS[0]);
const watchVerdictFilter = ref("all");
const watchSetupFilter = ref("all");
const watchPostureFilter = ref("all");
const watchSortMode = ref("manual");
const colorOptions = WATCHLIST_COLOR_OPTIONS;

const SOURCE_LABELS = {
  yahoo_finance: "Yahoo Finance",
  local_cache: "Local cache",
};

const VERDICT_TAGS = {
  priority: ["優先候選", "逆風強勢候選"],
  watch: ["觀察名單", "防守觀察"],
  wait: ["等待名單", "暫緩出手"],
};

const VERDICT_RANK = {
  priority: 3,
  watch: 2,
  wait: 1,
  other: 0,
};

const selectedGroup = computed(
  () => props.groups.find((group) => group.id === props.activeGroupId) || props.groups[0] || null,
);

const selectedWatchItems = computed(() => selectedGroup.value?.items || []);

const watchPostureOptions = computed(() => {
  const seen = new Set();
  return selectedWatchItems.value
    .map((item) => getPostureTag(item))
    .filter(Boolean)
    .filter((tag) => {
      if (seen.has(tag)) return false;
      seen.add(tag);
      return true;
    })
    .map((tag) => ({
      value: tag,
      label: tag.replace(/^市場:/, ""),
    }));
});

const hasWatchTransforms = computed(() => (
  props.leftTab === "watch"
  && (
    watchVerdictFilter.value !== "all"
    || watchSetupFilter.value !== "all"
    || watchPostureFilter.value !== "all"
    || watchSortMode.value !== "manual"
  )
));

const manualOrderingEnabled = computed(
  () => props.leftTab === "watch" && Boolean(selectedGroup.value) && !hasWatchTransforms.value,
);

const visibleItems = computed(() => {
  if (props.leftTab === "market") {
    return props.marketItems;
  }

  let items = [...selectedWatchItems.value];

  if (watchVerdictFilter.value !== "all") {
    items = items.filter((item) => getVerdictKey(item) === watchVerdictFilter.value);
  }

  if (watchSetupFilter.value !== "all") {
    const minimumSetup = watchSetupFilter.value === "q4" ? 4 : 3;
    items = items.filter((item) => getSetupQuality(item) >= minimumSetup);
  }

  if (watchPostureFilter.value !== "all") {
    items = items.filter((item) => getPostureTag(item) === watchPostureFilter.value);
  }

  if (watchSortMode.value === "manual") {
    return items;
  }

  return items.sort(compareWatchItems);
});

const sectionLabel = computed(() => {
  if (props.leftTab === "market") return "全球大盤與原物料";
  return selectedGroup.value?.name || "我的自選";
});

const emptyLabel = computed(() => {
  if (props.leftTab === "market") return "目前沒有市場指標資料";
  if (!props.groups.length) return "尚未建立觀察群組";
  if (hasWatchTransforms.value) return "目前篩選條件下沒有股票";
  return "這個群組目前還沒有股票";
});

const watchVerdictCounts = computed(() => selectedWatchItems.value.reduce((accumulator, item) => {
  const verdictKey = getVerdictKey(item);
  if (verdictKey === "priority" || verdictKey === "watch" || verdictKey === "wait") {
    accumulator[verdictKey] += 1;
  }
  return accumulator;
}, {
  priority: 0,
  watch: 0,
  wait: 0,
}));

const watchSummary = computed(() => {
  if (props.leftTab !== "watch" || !selectedGroup.value) return "";
  const totalCount = selectedWatchItems.value.length;
  if (!totalCount) return "此群組尚無標的";

  const verdictSummary = [
    watchVerdictCounts.value.priority ? `優先 ${watchVerdictCounts.value.priority}` : "",
    watchVerdictCounts.value.watch ? `觀察 ${watchVerdictCounts.value.watch}` : "",
    watchVerdictCounts.value.wait ? `等待 ${watchVerdictCounts.value.wait}` : "",
  ].filter(Boolean).join(" \u00B7 ");

  const baseSummary = verdictSummary
    ? `顯示 ${visibleItems.value.length} / ${totalCount} 檔 \u00B7 ${verdictSummary}`
    : `顯示 ${visibleItems.value.length} / ${totalCount} 檔`;
  if (!manualOrderingEnabled.value) {
    return `${baseSummary} \u00B7 目前為篩選/排序視圖，已暫停手動上下移`;
  }
  return baseSummary;
});

const watchGroupAlertPayloads = computed(() => {
  if (props.leftTab !== "watch" || !selectedGroup.value) return [];
  const groupTag = `${String.fromCharCode(35264, 23519, 32676, 32068)}:${selectedGroup.value.name}`;
  return visibleItems.value
    .map((item) => buildAlertShortcutPayload(item, {
      context_source: "watchlist_group",
      context_group_name: selectedGroup.value.name,
      extra_tags: [groupTag],
      prefill_hint: `${String.fromCharCode(32676, 32068, 25209, 27425, 35686, 22577, 65306)}${selectedGroup.value.name} - `
        + `${String.fromCharCode(30446, 21069, 39023, 31034)} ${visibleItems.value.length} ${String.fromCharCode(27284, 65292)}`
        + `${String.fromCharCode(20351, 29992, 21508, 33258, 24555, 29031, 20729, 26684, 20316, 28858, 38272, 27383, 12290)}`,
    }))
    .filter((payload) => payload && payload.snapshot_price != null);
});

watch(
  watchPostureOptions,
  (options) => {
    if (
      watchPostureFilter.value !== "all"
      && !options.some((option) => option.value === watchPostureFilter.value)
    ) {
      watchPostureFilter.value = "all";
    }
  },
  { immediate: true },
);

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
  return item?.is_delayed === false ? "最新快照" : "延遲快照";
}

function getFreshnessClass(item) {
  if (isStaleItem(item)) return "stale";
  return item?.is_delayed === false ? "live" : "delayed";
}

function getTagList(item) {
  return Array.isArray(item?.tags) ? item.tags.filter(Boolean) : [];
}

function getWatchTags(item) {
  return getTagList(item).slice(0, 3);
}

function getVerdictTag(item) {
  const tags = getTagList(item);
  const verdictCandidates = [
    ...VERDICT_TAGS.priority,
    ...VERDICT_TAGS.watch,
    ...VERDICT_TAGS.wait,
  ];
  return verdictCandidates.find((tag) => tags.includes(tag)) || "";
}

function getVerdictKey(item) {
  const verdictTag = getVerdictTag(item);
  if (VERDICT_TAGS.priority.includes(verdictTag)) return "priority";
  if (VERDICT_TAGS.watch.includes(verdictTag)) return "watch";
  if (VERDICT_TAGS.wait.includes(verdictTag)) return "wait";
  return "other";
}

function getSetupQuality(item) {
  const setupTag = getTagList(item).find((tag) => /^Q\d+$/.test(tag));
  if (!setupTag) return 0;
  return Number(setupTag.slice(1)) || 0;
}

function getPostureTag(item) {
  return getTagList(item).find((tag) => tag.startsWith("市場:")) || "";
}

function getFreshnessRank(item) {
  if (isStaleItem(item)) return 0;
  return item?.is_delayed === false ? 2 : 1;
}

function getManualOrder(item) {
  if (Number.isFinite(Number(item?.sort_order))) {
    return Number(item.sort_order);
  }
  return selectedWatchItems.value.findIndex((candidate) => candidate.id === item.id);
}

function compareByNumber(left, right, getter) {
  const leftValue = Number(getter(left) || 0);
  const rightValue = Number(getter(right) || 0);
  if (rightValue !== leftValue) return rightValue - leftValue;
  return getManualOrder(left) - getManualOrder(right);
}

function compareWatchItems(left, right) {
  if (watchSortMode.value === "verdict") {
    const verdictDelta = VERDICT_RANK[getVerdictKey(right)] - VERDICT_RANK[getVerdictKey(left)];
    if (verdictDelta !== 0) return verdictDelta;
    return compareByNumber(left, right, getSetupQuality);
  }

  if (watchSortMode.value === "setup_desc") {
    const setupDelta = getSetupQuality(right) - getSetupQuality(left);
    if (setupDelta !== 0) return setupDelta;
    const verdictDelta = VERDICT_RANK[getVerdictKey(right)] - VERDICT_RANK[getVerdictKey(left)];
    if (verdictDelta !== 0) return verdictDelta;
    return getManualOrder(left) - getManualOrder(right);
  }

  if (watchSortMode.value === "change_pct") {
    return compareByNumber(left, right, (item) => item.change_pct);
  }

  if (watchSortMode.value === "freshness") {
    const freshnessDelta = getFreshnessRank(right) - getFreshnessRank(left);
    if (freshnessDelta !== 0) return freshnessDelta;
    return getManualOrder(left) - getManualOrder(right);
  }

  return getManualOrder(left) - getManualOrder(right);
}

function resetWatchView() {
  watchVerdictFilter.value = "all";
  watchSetupFilter.value = "all";
  watchPostureFilter.value = "all";
  watchSortMode.value = "manual";
}

function openJournalEntry(item) {
  const tags = [...new Set([...getTagList(item), "來源:觀察池"])];
  const summaryParts = [];
  const verdictTag = getVerdictTag(item);
  if (verdictTag) summaryParts.push(verdictTag);
  if (getSetupQuality(item)) summaryParts.push(`Q${getSetupQuality(item)}`);
  if (getPostureTag(item)) summaryParts.push(getPostureTag(item));

  emit("open-journal-entry", {
    ticker: item.ticker,
    name: item.name || item.ticker,
    entry_price: item.close ?? "",
    entry_reason: summaryParts.length ? `觀察池跟蹤：${summaryParts.join(" / ")}` : "觀察池跟蹤標的",
    review_notes: `觀察池快照：${tags.join(" | ")} | 資料源:${formatSourceLabel(item.source)} | 狀態:${getFreshnessLabel(item)}`,
    tags,
  });
}

function buildAlertShortcutPayload(item, overrides = {}) {
  const ticker = String(item?.ticker || "").trim();
  if (!ticker) return null;
  const extraTags = Array.isArray(overrides.extra_tags) ? overrides.extra_tags : [];
  const contextTags = Array.from(new Set([...getTagList(item), ...extraTags.filter(Boolean)])).slice(0, 6);
  const hasPrice = Number.isFinite(Number(item.close));
  const latestPrice = hasPrice ? Number(item.close) : null;
  const latestPriceLabel = hasPrice ? fmtPrice(item.close) : String.fromCharCode(8212);
  const latestTimeLabel = formatWatchTimestamp(item);
  const latestTimestamp = resolveWatchTimestamp(item) || "";
  const defaultHint = `${String.fromCharCode(35264, 23519, 27744, 24555, 25463, 35686, 22577, 65306)}`
    + `${String.fromCharCode(20197)} ${latestPriceLabel} ${String.fromCharCode(28858, 22522, 28310, 65292)}`
    + `${String.fromCharCode(36039, 26009, 28304)} ${formatSourceLabel(item.source)}${String.fromCharCode(65292)}`
    + `${String.fromCharCode(26178, 38291)} ${latestTimeLabel}${String.fromCharCode(12290)}`;
  return {
    ticker,
    name: item.name || ticker,
    type: overrides.type || "price",
    condition: overrides.condition || (Number(item.change_pct || 0) >= 0 ? String.fromCharCode(22823, 26044) : String.fromCharCode(23567, 26044)),
    value: "value" in overrides ? overrides.value : latestPrice,
    prefill_hint: overrides.prefill_hint || defaultHint,
    context_tags: contextTags,
    context_source: overrides.context_source || "watchlist",
    context_group_name: overrides.context_group_name || selectedGroup.value?.name || "",
    snapshot_price: latestPrice,
    snapshot_source: item.source || "",
    snapshot_timestamp: latestTimestamp,
  };
}

function openAlertShortcut(item) {
  const payload = buildAlertShortcutPayload(item);
  if (!payload) return;
  emit("open-alert-modal", payload);
}

function getGroupColorStyle(color) {
  return {
    background: color || "rgba(255, 255, 255, 0.12)",
  };
}

function getGroupAccentStyle(item) {
  const color = item?.group_color || item?.color;
  return color
    ? {
      borderColor: `${color}33`,
      boxShadow: `inset 0 0 0 1px ${color}16`,
    }
    : {};
}

function toggleCreateGroup() {
  createGroupOpen.value = !createGroupOpen.value;
  if (!createGroupOpen.value) {
    newGroupName.value = "";
    newGroupColor.value = colorOptions[0];
  }
}

function submitGroup() {
  if (!newGroupName.value) return;
  emit("create-group", {
    name: newGroupName.value,
    color: newGroupColor.value,
  });
  newGroupName.value = "";
  newGroupColor.value = colorOptions[0];
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
  editGroupColor.value = group.color || colorOptions[0];
}

function cancelRenameGroup() {
  editingGroupId.value = null;
  editGroupName.value = "";
  editGroupColor.value = colorOptions[0];
}

function submitRenameGroup() {
  if (!editingGroupId.value || !editGroupName.value) return;
  emit("rename-group", editingGroupId.value, {
    name: editGroupName.value,
    color: editGroupColor.value,
  });
  cancelRenameGroup();
}

function requestDeleteGroup(group) {
  if (!window.confirm(`確定要刪除群組「${group.name}」嗎？`)) return;
  emit("delete-group", group.id);
}

function canMoveItem(item, direction) {
  const items = selectedWatchItems.value;
  const index = items.findIndex((candidate) => candidate.id === item.id);
  const targetIndex = index + direction;
  return index >= 0 && targetIndex >= 0 && targetIndex < items.length;
}

function moveItem(item, direction) {
  const items = [...selectedWatchItems.value];
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
.watchlist-viewbar {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.group-pill-color,
.wl-item-accent,
.group-swatch {
  flex-shrink: 0;
}

.group-pill-color {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.wl-item {
  position: relative;
}

.wl-item-accent {
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 4px;
  border-radius: 999px;
}

.group-swatch-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.group-swatch {
  width: 22px;
  height: 22px;
  border: 2px solid rgba(255, 255, 255, 0.12);
  border-radius: 50%;
  background: var(--group-color);
  cursor: pointer;
}

.group-swatch.active {
  border-color: rgba(255, 255, 255, 0.72);
  box-shadow: 0 0 0 2px rgba(123, 231, 255, 0.2);
}

.watchlist-viewfield {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 10px;
  color: var(--text3);
}

.watchlist-viewfield select {
  min-height: 30px;
  padding: 6px 8px;
  border: 1px solid var(--border2);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text1);
}

.reset-view-btn {
  align-self: end;
  min-height: 30px;
  border-radius: 10px;
}

.watchlist-summary {
  margin-top: 8px;
  font-size: 10px;
  line-height: 1.5;
  color: var(--text3);
}

.wl-shortcuts {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
  margin-bottom: 6px;
}

.wl-shortcut {
  padding: 4px 8px;
  border: 1px solid rgba(123, 231, 255, 0.2);
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.08);
  color: #bfefff;
  font-size: 10px;
  line-height: 1;
}

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

.wl-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.wl-tag-pill {
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 9px;
  line-height: 1.4;
  background: rgba(123, 231, 255, 0.12);
  color: #bfefff;
}

@media (max-width: 1100px) {
  .watchlist-viewbar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
