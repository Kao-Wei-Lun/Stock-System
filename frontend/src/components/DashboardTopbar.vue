<template>
  <div ref="rootRef" class="topbar">
    <div class="logo">Quant<span>Vision</span> Pro</div>

    <div class="search-wrap">
      <span style="color: var(--text3); font-size: 13px">⌕</span>
      <input
        :value="searchQuery"
        type="text"
        placeholder="搜尋代號..."
        autocomplete="off"
        @input="$emit('search-change', $event.target.value)"
        @keydown.enter.prevent="$emit('submit-search')"
      />
      <div class="search-dropdown" :class="{ open: searchOpen }">
        <div
          v-for="result in searchResults"
          :key="result.ticker"
          class="search-item"
          @click="$emit('select-search-result', result)"
        >
          <span class="st">{{ result.ticker }}</span>
          <span class="sn">{{ result.name || "" }}</span>
        </div>
      </div>
    </div>

    <div class="tf-btns">
      <button
        v-for="timeframe in timeframeOptions"
        :key="timeframe.label"
        class="tf-btn"
        :class="{ active: currentPeriod === timeframe.tf && currentInterval === timeframe.iv }"
        @click="$emit('set-timeframe', timeframe)"
      >
        {{ timeframe.label }}
      </button>
    </div>

    <div class="market-pills">
      <div class="mpill"><div class="dot" :class="marketStatus.nyseOpen ? 'live' : 'closed'"></div>NYSE</div>
      <div class="mpill"><div class="dot" :class="marketStatus.nasdaqOpen ? 'live' : 'closed'"></div>NASDAQ</div>
      <div class="mpill"><div class="dot" :class="marketStatus.tseOpen ? 'live' : 'closed'"></div>TSE</div>
      <div class="mpill"><div class="dot" :class="marketStatus.hkOpen ? 'live' : 'closed'"></div>HKEX</div>
    </div>

    <div style="display: flex; gap: 5px; margin-left: auto">
      <div class="icon-btn" title="新增警報" @click="$emit('open-alert-modal')">🔔</div>
      <div class="icon-btn" :class="wsConnected ? 'live' : 'warn'" title="WebSocket 狀態">📡</div>
      <div class="icon-btn" title="資料庫" @click="$emit('open-db-tab')">🗄️</div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps({
  searchQuery: { type: String, required: true },
  searchResults: { type: Array, required: true },
  searchOpen: { type: Boolean, required: true },
  timeframeOptions: { type: Array, required: true },
  currentPeriod: { type: String, required: true },
  currentInterval: { type: String, required: true },
  marketStatus: { type: Object, required: true },
  wsConnected: { type: Boolean, required: true },
});

const emit = defineEmits([
  "search-change",
  "submit-search",
  "select-search-result",
  "close-search",
  "open-alert-modal",
  "open-db-tab",
  "set-timeframe",
]);

const rootRef = ref(null);

function handleDocumentClick(event) {
  if (!rootRef.value?.contains(event.target)) {
    emit("close-search");
  }
}

onMounted(() => {
  window.addEventListener("click", handleDocumentClick);
});

onBeforeUnmount(() => {
  window.removeEventListener("click", handleDocumentClick);
});
</script>
