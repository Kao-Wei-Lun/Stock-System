<template>
  <section class="workspace-page overview-page">
    <div class="workspace-hero">
      <div>
        <div class="workspace-kicker">Market Overview</div>
        <h1>盤前先看風險，再挑今天值得追蹤的標的。</h1>
      </div>
      <div class="workspace-hero-meta">
        <div class="hero-stat">
          <span>目前焦點</span>
          <strong>{{ currentTicker }}</strong>
        </div>
        <button class="hero-action" type="button" @click="$emit('open-terminal', currentTicker)">
          前往終端
        </button>
      </div>
    </div>

    <div class="overview-macro">
      <MacroDashboard
        :macro-dashboard="macroDashboard"
        @refresh="$emit('refresh-macro')"
        @create-alert="$emit('create-alert', $event)"
      />
    </div>

    <div class="overview-grid">
      <div class="overview-card overview-watch">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">Watchlist</div>
            <div class="overview-card-title">自選觀察池</div>
          </div>
        </div>
        <WatchlistPanel
          :groups="groups"
          :market-items="marketItems"
          :active-group-id="activeGroupId"
          :items="watchlist"
          :left-tab="leftTab"
          :active-ticker="currentTicker"
          :loading="watchlistLoading"
          :error="watchlistError"
          @set-left-tab="$emit('set-left-tab', $event)"
          @select-group="$emit('select-group', $event)"
          @create-group="$emit('create-group', $event)"
          @rename-group="$emit('rename-group', $event)"
          @delete-group="$emit('delete-group', $event)"
          @add-to-watchlist="$emit('add-to-watchlist', $event)"
          @remove-from-watchlist="$emit('remove-from-watchlist', $event)"
          @reorder-items="$emit('reorder-items', $event)"
          @select-ticker="$emit('select-ticker', $event)"
          @open-journal-entry="$emit('open-journal-entry', $event)"
          @open-alert-modal="$emit('open-alert-modal', $event)"
          @create-alerts-batch="$emit('create-alerts-batch', $event)"
        />
      </div>

      <div class="overview-card overview-events">
        <div class="overview-card-head">
          <div>
            <div class="overview-card-kicker">Event Center</div>
            <div class="overview-card-title">事件與催化因子</div>
          </div>
          <button class="hero-action ghost" type="button" @click="$emit('refresh-events')">
            重新整理
          </button>
        </div>
        <EventCenter
          :current-ticker="currentTicker"
          :current-name="currentName"
          :calendar-events="calendarEvents"
          :ticker-events="tickerEvents"
          :ticker-news="tickerNews"
          @refresh-events="$emit('refresh-events')"
          @refresh-news="$emit('refresh-news')"
          @open-ticker="$emit('select-ticker', { ticker: $event, name: $event })"
          @create-alert="$emit('create-alert', $event)"
        />
      </div>
    </div>

    <div class="overview-card overview-screener">
      <div class="overview-card-head">
        <div>
          <div class="overview-card-kicker">Screener Workspace</div>
          <div class="overview-card-title">策略掃描結果</div>
        </div>
      </div>
      <ScreenerWorkspace
        :filters="screenerFilters"
        :results="screenerResults"
        :presets="screenerPresets"
        :loading="screenerLoading"
        :current-ticker="currentTicker"
        @update-filter="$emit('update-screener-filter', $event)"
        @run-screen="$emit('run-screener')"
        @save-preset="$emit('save-screener-preset', $event)"
        @load-preset="$emit('load-screener-preset', $event)"
        @delete-preset="$emit('delete-screener-preset', $event)"
        @open-ticker="$emit('select-ticker', { ticker: $event, name: $event })"
        @add-watchlist="$emit('add-to-watchlist', $event)"
        @open-journal-entry="$emit('open-journal-entry', $event)"
        @add-alert="$emit('open-alert-modal', $event)"
      />
    </div>
  </section>
</template>

<script setup>
import EventCenter from "../EventCenter.vue";
import MacroDashboard from "../MacroDashboard.vue";
import ScreenerWorkspace from "../ScreenerWorkspace.vue";
import WatchlistPanel from "../WatchlistPanel.vue";

defineProps({
  groups: { type: Array, required: true },
  marketItems: { type: Array, required: true },
  activeGroupId: { type: Number, default: null },
  watchlist: { type: Array, required: true },
  watchlistLoading: { type: Boolean, required: true },
  watchlistError: { type: Boolean, required: true },
  leftTab: { type: String, required: true },
  currentTicker: { type: String, required: true },
  currentName: { type: String, required: true },
  macroDashboard: { type: Object, required: true },
  calendarEvents: { type: Array, default: () => [] },
  tickerEvents: { type: Array, default: () => [] },
  tickerNews: { type: Array, default: () => [] },
  screenerFilters: { type: Object, required: true },
  screenerResults: { type: Object, required: true },
  screenerPresets: { type: Array, default: () => [] },
  screenerLoading: { type: Boolean, required: true },
});

defineEmits([
  "open-terminal",
  "refresh-macro",
  "refresh-events",
  "refresh-news",
  "create-alert",
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
  "update-screener-filter",
  "run-screener",
  "save-screener-preset",
  "load-screener-preset",
  "delete-screener-preset",
]);
</script>

<style scoped>
.workspace-page {
  height: 100%;
  overflow: auto;
  padding: 18px;
}

.overview-page {
  background:
    radial-gradient(circle at top left, rgba(123, 231, 255, 0.08), transparent 24%),
    linear-gradient(180deg, rgba(7, 12, 19, 0.98), rgba(8, 13, 21, 0.98));
}

.workspace-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 20px 22px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(6, 20, 30, 0.94), rgba(10, 16, 26, 0.96));
}

.workspace-kicker,
.overview-card-kicker {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text3);
}

.workspace-hero h1 {
  margin-top: 8px;
  font-family: "Syne", sans-serif;
  font-size: 28px;
  line-height: 1.1;
}

.workspace-hero-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.hero-stat {
  min-width: 120px;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.03);
}

.hero-stat span {
  display: block;
  font-size: 10px;
  color: var(--text3);
}

.hero-stat strong {
  display: block;
  margin-top: 4px;
  font-size: 16px;
  color: var(--text1);
}

.hero-action {
  padding: 10px 14px;
  border: 1px solid rgba(123, 231, 255, 0.22);
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.12);
  color: #d7fbff;
  cursor: pointer;
  font-size: 11px;
}

.hero-action.ghost {
  border-color: rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
}

.overview-macro {
  margin-top: 18px;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.92fr) minmax(0, 1.08fr);
  gap: 18px;
  margin-top: 18px;
  align-items: start;
}

.overview-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 20px;
  background: rgba(6, 10, 18, 0.68);
  overflow: hidden;
}

.overview-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px 10px;
}

.overview-card-title {
  margin-top: 4px;
  font-family: "Syne", sans-serif;
  font-size: 17px;
  font-weight: 700;
}

.overview-watch,
.overview-events {
  min-height: 640px;
}

.overview-watch :deep(.left-panel) {
  width: 100%;
  min-width: 0;
  height: 100%;
  border-right: 0;
  background: transparent;
}

.overview-events :deep(.intel-shell) {
  height: 100%;
  min-height: 0;
  border-radius: 0;
  border: 0;
  background: transparent;
}

.overview-screener {
  margin-top: 18px;
}

.overview-screener :deep(.screen-shell) {
  border: 0;
  border-radius: 0;
  background: transparent;
}

@media (max-width: 1280px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .overview-watch,
  .overview-events {
    min-height: 0;
  }
}

@media (max-width: 720px) {
  .workspace-page {
    padding: 12px;
  }

  .workspace-hero {
    flex-direction: column;
    align-items: stretch;
  }

  .workspace-hero h1 {
    font-size: 24px;
  }

  .workspace-hero-meta {
    flex-wrap: wrap;
  }
}
</style>
