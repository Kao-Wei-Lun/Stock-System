<template>
  <header class="app-navbar">
    <div class="brand-block">
      <div class="brand-kicker">Workflow Trading OS</div>
      <button class="brand-mark" type="button" @click="$emit('navigate', 'overview')">
        Quant<span>Vision</span>
      </button>
    </div>

    <nav class="workspace-nav" aria-label="Primary workspace navigation">
      <button
        v-for="item in navItems"
        :key="item.key"
        class="workspace-nav-btn"
        :class="{ active: workspacePage === item.key }"
        type="button"
        :title="`${item.label} · ${item.shortcut}`"
        @click="$emit('navigate', item.key)"
      >
        <span class="workspace-nav-label">{{ item.label }}</span>
        <span class="workspace-nav-hint">{{ item.hint }}</span>
      </button>
    </nav>

    <div class="navbar-tools">
      <div ref="rootRef" class="search-wrap">
        <span class="search-icon">⌕</span>
        <input
          ref="searchInputRef"
          :value="searchQuery"
          type="text"
          placeholder="搜尋代號或名稱..."
          autocomplete="off"
          @input="$emit('search-change', $event.target.value)"
          @keydown.enter.prevent="$emit('submit-search')"
        >
        <button
          class="search-command-badge"
          type="button"
          title="Ctrl/Cmd + K"
          @click="$emit('open-command-palette')"
        >
          ⌘K
        </button>

        <div class="search-dropdown" :class="{ open: searchOpen }">
          <button
            v-for="result in searchResults"
            :key="result.ticker"
            class="search-item"
            type="button"
            @click="$emit('select-search-result', result)"
          >
            <div class="search-item-main">
              <span class="st">{{ result.ticker }}</span>
              <span class="sn">{{ formatSearchMeta(result) }}</span>
            </div>
            <span v-if="searchResultTag(result)" class="search-tag">{{ searchResultTag(result) }}</span>
          </button>
        </div>
      </div>

      <div v-if="workspacePage === 'terminal'" class="tf-btns">
        <button
          v-for="timeframe in timeframeOptions"
          :key="timeframe.label"
          class="tf-btn"
          :class="{ active: currentPeriod === timeframe.tf && currentInterval === timeframe.iv }"
          type="button"
          @click="$emit('set-timeframe', timeframe)"
        >
          {{ timeframe.label }}
        </button>
      </div>

      <button class="heatmap-link" type="button" @click="$emit('open-heatmap')">
        Heatmap
      </button>

      <div class="market-pills">
        <div class="mpill">
          <div class="dot" :class="marketStatus.nyseOpen ? 'live' : 'closed'"></div>
          NYSE
        </div>
        <div class="mpill">
          <div class="dot" :class="marketStatus.nasdaqOpen ? 'live' : 'closed'"></div>
          NASDAQ
        </div>
        <div class="mpill">
          <div class="dot" :class="marketStatus.tseOpen ? 'live' : 'closed'"></div>
          TSE
        </div>
      </div>

      <div class="fubon-badge" :class="fubonStatusClass" :title="fubonStatusTitle">
        <span class="fubon-badge-dot"></span>
        <span>{{ fubonStatusLabel }}</span>
      </div>

      <div class="quote-badge" :class="quoteStatusClass">
        <span class="quote-badge-dot"></span>
        <span>{{ quoteStatusLabel }}</span>
      </div>

      <div v-if="workspacePage === 'review'" class="review-switch">
        <button
          class="review-switch-btn"
          :class="{ active: reviewTab === 'journal' }"
          type="button"
          @click="$emit('set-review-tab', 'journal')"
        >
          交易日誌
        </button>
        <button
          class="review-switch-btn"
          :class="{ active: reviewTab === 'backtest' }"
          type="button"
          @click="$emit('set-review-tab', 'backtest')"
        >
          系統回測
        </button>
      </div>

      <div class="nav-actions">
        <button class="action-btn" type="button" title="新增警報" @click="$emit('open-alert-modal')">
          🔔
        </button>
        <div class="action-btn status" :class="wsConnected ? 'live' : 'warn'" title="WebSocket 狀態">
          📡
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const props = defineProps({
  workspacePage: { type: String, required: true },
  reviewTab: { type: String, default: "journal" },
  searchQuery: { type: String, required: true },
  searchResults: { type: Array, required: true },
  searchOpen: { type: Boolean, required: true },
  timeframeOptions: { type: Array, required: true },
  currentPeriod: { type: String, required: true },
  currentInterval: { type: String, required: true },
  marketStatus: { type: Object, required: true },
  wsConnected: { type: Boolean, required: true },
  fubonStatus: { type: String, default: "unconfigured" },
  activeQuote: { type: Object, default: () => ({}) },
});

const emit = defineEmits([
  "navigate",
  "set-review-tab",
  "search-change",
  "submit-search",
  "select-search-result",
  "close-search",
  "set-timeframe",
  "open-heatmap",
  "open-alert-modal",
  "open-command-palette",
]);

const navItems = [
  { key: "overview", label: "總覽", hint: "盤前觀察", shortcut: "Alt+1" },
  { key: "terminal", label: "終端", hint: "盤中決策", shortcut: "Alt+2" },
  { key: "institutional", label: "籌碼", hint: "盤後研究", shortcut: "Alt+3" },
  { key: "review", label: "復盤", hint: "日誌回測", shortcut: "Alt+4" },
  { key: "assets", label: "資產", hint: "個人資產", shortcut: "Alt+5" },
  { key: "paper-trading", label: "模擬", hint: "TMF 練習", shortcut: "Alt+6" },
  { key: "settings", label: "設定", hint: "帳號連線", shortcut: "Alt+7" },
];

const rootRef = ref(null);
const searchInputRef = ref(null);

const quoteStatusLabel = computed(() => {
  if (props.activeQuote?.is_delayed === false) return "即時";
  if (props.activeQuote?.quote_type === "delayed_snapshot") return "盤後快照";
  return "快照";
});

const quoteStatusClass = computed(() => ({
  live: props.activeQuote?.is_delayed === false,
  delayed: props.activeQuote?.is_delayed !== false,
}));

const fubonStatusLabel = computed(() => ({
  connected: "富邦即時",
  connecting: "連線中",
  error: "連線錯誤",
  disconnected: "富邦待命",
  unconfigured: "未設定",
}[props.fubonStatus] || "未設定"));

const fubonStatusClass = computed(() => ({
  connected: props.fubonStatus === "connected",
  connecting: props.fubonStatus === "connecting",
  error: props.fubonStatus === "error",
  disconnected: props.fubonStatus === "disconnected",
  unconfigured: props.fubonStatus === "unconfigured",
}));

const fubonStatusTitle = computed(() => `富邦連線狀態：${fubonStatusLabel.value}`);

function searchResultTag(result) {
  if (result?.asset_class === "futopt") {
    return result?.instrument_type === "option" ? "選擇權" : "期貨";
  }
  if (result?.market === "TW") return "台股";
  if (result?.market === "HK") return "港股";
  if (result?.market === "INDEX") return "指數";
  return "";
}

function formatSearchMeta(result) {
  const name = String(result?.name || result?.ticker || "");
  const exchange = String(result?.exchange || "");
  return exchange && exchange !== name ? `${name} · ${exchange}` : name;
}

function handleDocumentClick(event) {
  if (!rootRef.value?.contains(event.target)) {
    emit("close-search");
  }
}

function focusSearchInput() {
  searchInputRef.value?.focus();
  searchInputRef.value?.select?.();
}

defineExpose({
  focusSearchInput,
});

onMounted(() => {
  window.addEventListener("click", handleDocumentClick);
});

onBeforeUnmount(() => {
  window.removeEventListener("click", handleDocumentClick);
});
</script>

<style scoped>
.app-navbar {
  display: grid;
  grid-template-columns: auto minmax(0, 1.15fr) minmax(420px, 1fr);
  gap: 18px;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(8, 12, 19, 0.98), rgba(10, 15, 24, 0.96));
}

.brand-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.brand-kicker {
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: rgba(144, 222, 255, 0.68);
}

.brand-mark {
  border: 0;
  background: transparent;
  color: #f5fbff;
  font-size: 28px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
  text-align: left;
}

.brand-mark span {
  color: #90deff;
}

.workspace-nav {
  display: flex;
  gap: 10px;
  min-width: 0;
}

.workspace-nav-btn {
  flex: 1 1 0;
  min-width: 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  color: rgba(230, 241, 255, 0.78);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  cursor: pointer;
}

.workspace-nav-btn.active {
  border-color: rgba(144, 222, 255, 0.5);
  background: linear-gradient(135deg, rgba(38, 74, 112, 0.42), rgba(17, 35, 52, 0.88));
  color: #f5fbff;
}

.workspace-nav-label {
  font-weight: 700;
}

.workspace-nav-hint {
  font-size: 11px;
  color: rgba(196, 211, 226, 0.72);
}

.navbar-tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  min-width: 0;
}

.search-wrap {
  position: relative;
  min-width: 260px;
  max-width: 340px;
}

.search-wrap input {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.04);
  color: #f5fbff;
  padding: 12px 78px 12px 34px;
  outline: none;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: rgba(196, 211, 226, 0.7);
}

.search-command-badge {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(230, 241, 255, 0.82);
  padding: 4px 8px;
  cursor: pointer;
}

.search-dropdown {
  position: absolute;
  left: 0;
  right: 0;
  top: calc(100% + 8px);
  display: none;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(11, 17, 26, 0.98);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.28);
  z-index: 20;
}

.search-dropdown.open {
  display: flex;
}

.search-item {
  border: 0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: #f5fbff;
  padding: 10px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  cursor: pointer;
}

.search-item-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.st {
  font-weight: 700;
}

.sn {
  font-size: 12px;
  color: rgba(196, 211, 226, 0.72);
}

.search-tag {
  font-size: 11px;
  color: #90deff;
}

.tf-btns,
.market-pills,
.review-switch,
.nav-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tf-btn,
.heatmap-link,
.review-switch-btn,
.action-btn {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(230, 241, 255, 0.82);
  padding: 8px 10px;
  cursor: pointer;
}

.tf-btn.active,
.review-switch-btn.active {
  border-color: rgba(144, 222, 255, 0.5);
  color: #f5fbff;
  background: rgba(56, 119, 179, 0.18);
}

.mpill,
.fubon-badge,
.quote-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  color: rgba(230, 241, 255, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 12px;
}

.dot,
.fubon-badge-dot,
.quote-badge-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #6b7d91;
}

.dot.live,
.fubon-badge.connected .fubon-badge-dot,
.quote-badge.live .quote-badge-dot,
.action-btn.status.live {
  background: #5dd39e;
}

.dot.closed,
.quote-badge.delayed .quote-badge-dot,
.action-btn.status.warn {
  background: #ff8c42;
}

.fubon-badge.error .fubon-badge-dot {
  background: #ff5a5f;
}

.action-btn.status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
}

@media (max-width: 1500px) {
  .app-navbar {
    grid-template-columns: 1fr;
  }

  .workspace-nav,
  .navbar-tools {
    flex-wrap: wrap;
    justify-content: flex-start;
  }
}

@media (max-width: 900px) {
  .search-wrap {
    min-width: 0;
    max-width: none;
    width: 100%;
  }
}
</style>
