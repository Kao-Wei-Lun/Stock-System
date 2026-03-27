<template>
  <div class="left-panel">
    <div class="panel-tabs">
      <div class="ptab" :class="{ active: leftTab === 'watch' }" @click="$emit('set-left-tab', 'watch')">自選股</div>
      <div class="ptab" :class="{ active: leftTab === 'market' }" @click="$emit('set-left-tab', 'market')">大盤</div>
    </div>

    <div class="watchlist">
      <div v-if="loading" class="loading-wl">
        <div style="width: 20px; height: 20px; border: 2px solid var(--border2); border-top-color: var(--green); border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto 8px;"></div>
        載入自選股...
      </div>
      <div v-else-if="error" class="loading-wl" style="color: var(--red)">⚠ 無法連線後端</div>
      <template v-else-if="groupedItems.length">
        <template v-for="group in groupedItems" :key="group.category">
          <div class="sec-label">{{ group.category }}</div>
          <div
            v-for="item in group.items"
            :key="item.ticker"
            class="wl-item"
            :class="{ active: item.ticker === activeTicker }"
            @click="$emit('select-ticker', item)"
          >
            <div>
              <div class="wl-ticker">{{ item.ticker }}</div>
              <div class="wl-name">{{ item.name || "" }}</div>
            </div>
            <div>
              <div class="wl-price" :class="item.change_pct >= 0 ? 'up' : 'dn'">{{ fmtPrice(item.close) }}</div>
              <div class="wl-chg" :class="item.change_pct >= 0 ? 'up' : 'dn'">
                {{ item.change_pct >= 0 ? "+" : "" }}{{ (item.change_pct || 0).toFixed(2) }}%
              </div>
            </div>
          </div>
        </template>
      </template>
      <div v-else class="loading-wl">無資料</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

import { fmtPrice } from "../utils/formatters";

const props = defineProps({
  items: { type: Array, required: true },
  leftTab: { type: String, required: true },
  activeTicker: { type: String, required: true },
  loading: { type: Boolean, required: true },
  error: { type: Boolean, required: true },
});

defineEmits(["set-left-tab", "select-ticker"]);

const marketCategories = ["ETF", "指數", "加密"];

const groupedItems = computed(() => {
  const filtered =
    props.leftTab === "market"
      ? props.items.filter((item) => marketCategories.includes(item.category))
      : props.items.filter((item) => !marketCategories.includes(item.category));
  const source = filtered.length ? filtered : props.items;
  const groups = new Map();
  source.forEach((item) => {
    if (!groups.has(item.category)) groups.set(item.category, []);
    groups.get(item.category).push(item);
  });
  return Array.from(groups.entries()).map(([category, items]) => ({ category, items }));
});
</script>
