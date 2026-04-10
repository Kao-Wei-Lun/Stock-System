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
        />
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
            <span class="st">{{ result.ticker }}</span>
            <span class="sn">{{ result.name || "" }}</span>
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
import { onBeforeUnmount, onMounted, ref } from "vue";

defineProps({
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
  { key: "institutional", label: "籌碼", hint: "盤後深究", shortcut: "Alt+3" },
  { key: "review", label: "復盤", hint: "日誌回測", shortcut: "Alt+4" },
];

const rootRef = ref(null);
const searchInputRef = ref(null);

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
  grid-template-columns: auto minmax(0, 1.2fr) minmax(420px, 1fr);
  gap: 18px;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background:
    radial-gradient(circle at top left, rgba(123, 231, 255, 0.12), transparent 28%),
    linear-gradient(135deg, rgba(8, 12, 18, 0.98), rgba(12, 18, 29, 0.98));
  backdrop-filter: blur(18px);
  position: relative;
  z-index: 20;
}

.brand-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.brand-kicker {
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text3);
}

.brand-mark {
  border: 0;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  font-family: "Syne", sans-serif;
  font-size: 22px;
  font-weight: 800;
  text-align: left;
}

.brand-mark span {
  color: var(--green);
}

.workspace-nav {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.workspace-nav-btn {
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, transform 0.2s ease, background 0.2s ease;
}

.workspace-nav-btn:hover {
  border-color: rgba(123, 231, 255, 0.28);
  transform: translateY(-1px);
}

.workspace-nav-btn.active {
  border-color: rgba(123, 231, 255, 0.28);
  background: linear-gradient(135deg, rgba(10, 34, 48, 0.92), rgba(8, 18, 30, 0.92));
  color: var(--text1);
  box-shadow: 0 0 0 1px rgba(123, 231, 255, 0.1) inset;
}

.workspace-nav-label {
  display: block;
  font-size: 13px;
  font-weight: 700;
}

.workspace-nav-hint {
  display: block;
  margin-top: 3px;
  font-size: 10px;
  color: var(--text3);
}

.navbar-tools {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  min-width: 0;
}

.search-wrap {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 240px;
  width: min(320px, 100%);
  padding: 0 12px;
  height: 38px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
}

.search-icon {
  color: var(--text3);
  font-size: 13px;
}

.search-wrap input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text1);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  text-transform: uppercase;
}

.search-command-badge {
  flex: 0 0 auto;
  padding: 3px 7px;
  border: 1px solid rgba(123, 231, 255, 0.2);
  border-radius: 6px;
  background: rgba(123, 231, 255, 0.1);
  color: #d7fbff;
  cursor: pointer;
  font-family: "JetBrains Mono", monospace;
  font-size: 10px;
}

.search-command-badge:hover {
  border-color: rgba(123, 231, 255, 0.34);
}

.search-wrap input::placeholder {
  color: var(--text3);
}

.search-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  display: none;
  max-height: 260px;
  overflow: auto;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(6, 12, 20, 0.98);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.34);
}

.search-dropdown.open {
  display: block;
}

.search-item {
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  background: transparent;
  color: var(--text1);
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  text-align: left;
}

.search-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.search-item:last-child {
  border-bottom: 0;
}

.st {
  font-weight: 700;
}

.sn {
  color: var(--text3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tf-btns,
.heatmap-link,
.market-pills,
.review-switch,
.nav-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tf-btn,
.review-switch-btn,
.action-btn {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  font-family: "JetBrains Mono", monospace;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.tf-btn {
  padding: 7px 8px;
  font-size: 10px;
}

.tf-btn.active,
.review-switch-btn.active {
  border-color: rgba(123, 231, 255, 0.32);
  background: rgba(123, 231, 255, 0.14);
  color: #d7fbff;
}

.review-switch-btn {
  padding: 8px 12px;
  font-size: 10px;
}

.mpill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 9px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text3);
  font-size: 10px;
}

.heatmap-link {
  padding: 8px 10px;
  border: 1px solid rgba(255, 209, 102, 0.18);
  border-radius: 999px;
  background: rgba(255, 209, 102, 0.08);
  color: #ffe1a0;
  cursor: pointer;
  font-size: 10px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text3);
}

.dot.live {
  background: var(--green);
  box-shadow: 0 0 10px rgba(0, 217, 163, 0.6);
}

.action-btn {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  font-size: 13px;
}

.action-btn.status {
  cursor: default;
}

.action-btn.status.live {
  color: var(--green);
  border-color: rgba(0, 217, 163, 0.32);
}

.action-btn.status.warn {
  color: var(--amber);
  border-color: rgba(245, 166, 35, 0.24);
}

@media (max-width: 1480px) {
  .app-navbar {
    grid-template-columns: 1fr;
  }

  .navbar-tools {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}

@media (max-width: 960px) {
  .workspace-nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .search-wrap {
    width: 100%;
    min-width: 0;
  }

  .market-pills {
    display: none;
  }
}

@media (max-width: 640px) {
  .app-navbar {
    padding: 12px;
  }

  .workspace-nav {
    grid-template-columns: 1fr;
  }

  .tf-btns {
    overflow-x: auto;
    max-width: 100%;
  }
}
</style>
