<template>
  <div v-if="open" class="command-overlay" @click.self="$emit('close')">
    <div class="command-shell" role="dialog" aria-modal="true" aria-label="Global search command">
      <div class="command-head">
        <div>
          <div class="command-kicker">Global Command</div>
          <div class="command-title">Ctrl/Cmd + K 快速切換標的與工作區</div>
        </div>
        <button class="command-close" type="button" @click="$emit('close')">
          Esc
        </button>
      </div>

      <div class="command-input-wrap">
        <span class="command-input-icon">⌕</span>
        <input
          ref="inputRef"
          :value="query"
          type="text"
          placeholder="輸入代號、公司名或快速命令..."
          autocomplete="off"
          @input="$emit('query-change', $event.target.value)"
          @keydown.enter.prevent="commitActiveEntry"
          @keydown.down.prevent="shiftActiveEntry(1)"
          @keydown.up.prevent="shiftActiveEntry(-1)"
          @keydown.esc.prevent="$emit('close')"
        />
      </div>

      <div class="command-grid">
        <section v-if="workspaceEntries.length" class="command-section">
          <div class="command-section-label">Workspace</div>
          <button
            v-for="entry in workspaceEntries"
            :key="entry.id"
            class="command-item"
            :class="{ active: isActiveEntry(entry) }"
            type="button"
            @mouseenter="setActiveEntry(entry)"
            @click="commitEntry(entry)"
          >
            <div>
              <div class="command-item-title">{{ entry.label }}</div>
              <div class="command-item-meta">{{ entry.meta }}</div>
            </div>
            <span class="command-item-shortcut">{{ entry.shortcut }}</span>
          </button>
        </section>

        <section v-if="resultEntries.length" class="command-section grow">
          <div class="command-section-label">
            {{ hasQuery ? "Search Results" : "Recent & Hot" }}
          </div>
          <button
            v-for="entry in resultEntries"
            :key="entry.id"
            class="command-item"
            :class="{ active: isActiveEntry(entry) }"
            type="button"
            @mouseenter="setActiveEntry(entry)"
            @click="commitEntry(entry)"
          >
            <div>
              <div class="command-item-title">{{ entry.label }}</div>
              <div class="command-item-meta">{{ entry.meta }}</div>
            </div>
            <span class="command-item-pill">{{ entry.tag }}</span>
          </button>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";

const HOT_TICKERS = [
  { ticker: "AAPL", name: "Apple" },
  { ticker: "NVDA", name: "NVIDIA" },
  { ticker: "MSFT", name: "Microsoft" },
  { ticker: "TSLA", name: "Tesla" },
  { ticker: "SPY", name: "SPDR S&P 500 ETF" },
  { ticker: "QQQ", name: "Invesco QQQ" },
  { ticker: "2330.TW", name: "台積電" },
  { ticker: "0050.TW", name: "元大台灣 50" },
];

const props = defineProps({
  open: { type: Boolean, default: false },
  query: { type: String, default: "" },
  searchResults: { type: Array, default: () => [] },
  recentTickers: { type: Array, default: () => [] },
  currentTicker: { type: String, default: "" },
});

const emit = defineEmits(["close", "query-change", "select-symbol", "navigate"]);

const inputRef = ref(null);
const activeEntryId = ref("");

const hasQuery = computed(() => Boolean(String(props.query || "").trim()));

const workspaceEntries = computed(() => ([
  {
    id: "workspace-terminal",
    kind: "workspace",
    page: "terminal",
    label: "Open Terminal",
    meta: props.currentTicker ? `目前焦點 ${props.currentTicker}` : "前往專業看盤終端",
    shortcut: "T",
  },
  {
    id: "workspace-overview",
    kind: "workspace",
    page: "overview",
    label: "Market Overview",
    meta: "宏觀風險、事件與熱力圖",
    shortcut: "O",
  },
  {
    id: "workspace-institutional",
    kind: "workspace",
    page: "institutional",
    label: "Institutional Analysis",
    meta: "法人籌碼與期權洞察",
    shortcut: "I",
  },
  {
    id: "workspace-review",
    kind: "workspace",
    page: "review",
    label: "Review Workspace",
    meta: "日誌、回測與復盤",
    shortcut: "R",
  },
]));

const searchEntries = computed(() => (Array.isArray(props.searchResults) ? props.searchResults : [])
  .slice(0, 10)
  .map((item) => ({
    id: `search-${item.ticker}`,
    kind: "symbol",
    ticker: item.ticker,
    name: item.name || item.ticker,
    label: item.ticker,
    meta: item.name || item.ticker,
    tag: "Search",
  })));

const recentEntries = computed(() => (Array.isArray(props.recentTickers) ? props.recentTickers : [])
  .slice(0, 6)
  .map((item) => ({
    id: `recent-${item.ticker}`,
    kind: "symbol",
    ticker: item.ticker,
    name: item.name || item.ticker,
    label: item.ticker,
    meta: item.name || item.ticker,
    tag: "Recent",
  })));

const hotEntries = computed(() => HOT_TICKERS
  .filter((item) => !recentEntries.value.some((recent) => recent.ticker === item.ticker))
  .slice(0, 6)
  .map((item) => ({
    id: `hot-${item.ticker}`,
    kind: "symbol",
    ticker: item.ticker,
    name: item.name || item.ticker,
    label: item.ticker,
    meta: item.name || item.ticker,
    tag: "Hot",
  })));

const resultEntries = computed(() => (
  hasQuery.value
    ? searchEntries.value
    : [...recentEntries.value, ...hotEntries.value]
));

const selectableEntries = computed(() => [...workspaceEntries.value, ...resultEntries.value]);

function setDefaultActiveEntry() {
  activeEntryId.value = selectableEntries.value[0]?.id || "";
}

function setActiveEntry(entry) {
  activeEntryId.value = entry?.id || "";
}

function isActiveEntry(entry) {
  return entry?.id === activeEntryId.value;
}

function shiftActiveEntry(step) {
  const entries = selectableEntries.value;
  if (!entries.length) return;
  const currentIndex = Math.max(0, entries.findIndex((entry) => entry.id === activeEntryId.value));
  const nextIndex = (currentIndex + step + entries.length) % entries.length;
  activeEntryId.value = entries[nextIndex].id;
}

function commitEntry(entry) {
  if (!entry) return;
  if (entry.kind === "workspace") {
    emit("navigate", entry.page);
  } else {
    emit("select-symbol", { ticker: entry.ticker, name: entry.name || entry.ticker });
  }
}

function commitActiveEntry() {
  const entry = selectableEntries.value.find((item) => item.id === activeEntryId.value) || selectableEntries.value[0];
  commitEntry(entry);
}

watch(
  () => props.open,
  async (value) => {
    if (!value) return;
    setDefaultActiveEntry();
    await nextTick();
    inputRef.value?.focus();
    inputRef.value?.select?.();
  },
  { immediate: true },
);

watch(
  () => [props.query, props.searchResults, props.recentTickers],
  () => setDefaultActiveEntry(),
  { deep: true },
);
</script>

<style scoped>
.command-overlay {
  position: fixed;
  inset: 0;
  z-index: 1500;
  display: grid;
  place-items: start center;
  padding: 8vh 20px 20px;
  background: rgba(4, 8, 14, 0.72);
  backdrop-filter: blur(12px);
}

.command-shell {
  width: min(920px, 100%);
  border: 1px solid rgba(123, 231, 255, 0.14);
  border-radius: 24px;
  background:
    radial-gradient(circle at top left, rgba(123, 231, 255, 0.12), transparent 28%),
    linear-gradient(180deg, rgba(7, 13, 22, 0.98), rgba(8, 14, 24, 0.98));
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.36);
  overflow: hidden;
}

.command-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.command-kicker {
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text3);
}

.command-title {
  margin-top: 6px;
  font-family: "Syne", sans-serif;
  font-size: 20px;
  color: var(--text1);
}

.command-close {
  min-width: 52px;
  padding: 8px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  font-size: 10px;
}

.command-input-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.command-input-icon {
  color: var(--text3);
  font-size: 14px;
}

.command-input-wrap input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text1);
  font-family: "JetBrains Mono", monospace;
  font-size: 13px;
}

.command-input-wrap input::placeholder {
  color: var(--text3);
}

.command-grid {
  display: grid;
  grid-template-columns: minmax(240px, 0.76fr) minmax(0, 1.24fr);
  gap: 0;
  min-height: 360px;
}

.command-section {
  padding: 16px;
}

.command-section.grow {
  border-left: 1px solid rgba(255, 255, 255, 0.06);
}

.command-section-label {
  margin-bottom: 10px;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text3);
}

.command-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 13px;
  border: 1px solid transparent;
  border-radius: 16px;
  background: transparent;
  color: var(--text1);
  cursor: pointer;
  text-align: left;
}

.command-item + .command-item {
  margin-top: 6px;
}

.command-item:hover,
.command-item.active {
  border-color: rgba(123, 231, 255, 0.18);
  background: rgba(123, 231, 255, 0.08);
}

.command-item-title {
  font-size: 13px;
  font-weight: 700;
}

.command-item-meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--text3);
}

.command-item-shortcut,
.command-item-pill {
  flex-shrink: 0;
  padding: 4px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text2);
  font-size: 10px;
}

@media (max-width: 820px) {
  .command-overlay {
    padding: 12px;
  }

  .command-grid {
    grid-template-columns: 1fr;
  }

  .command-section.grow {
    border-left: 0;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }
}
</style>
