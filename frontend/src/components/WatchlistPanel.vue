<template>
  <div class="left-panel">
    <div class="panel-tabs">
      <div class="ptab" :class="{ active: leftTab === 'watch' }" @click="$emit('set-left-tab', 'watch')">自選股</div>
      <div class="ptab" :class="{ active: leftTab === 'market' }" @click="$emit('set-left-tab', 'market')">大盤</div>
    </div>

    <div v-if="!loading && !error" class="watchlist-controls">
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
          </div>
          <div>
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
  "add-to-watchlist",
  "select-ticker",
]);

const marketCategories = ["ETF", "指數", "加密"];
const createGroupOpen = ref(false);
const newGroupName = ref("");
const newTicker = ref("");

const selectedGroup = computed(
  () => props.groups.find((group) => group.id === props.activeGroupId) || props.groups[0] || null,
);

const visibleItems = computed(() => {
  if (props.leftTab === "market") {
    return props.items.filter((item) => marketCategories.includes(item.category));
  }
  return selectedGroup.value?.items || [];
});

const sectionLabel = computed(() => {
  if (props.leftTab === "market") return "市場觀察";
  return selectedGroup.value?.name || "我的自選";
});

const emptyLabel = computed(() => {
  if (props.leftTab === "market") return "目前沒有市場觀察標的";
  if (!props.groups.length) return "尚未建立觀察群組";
  return "這個群組目前還沒有股票";
});

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
</script>
