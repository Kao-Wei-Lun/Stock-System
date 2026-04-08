<template>
  <section class="terminal-page">
    <div class="terminal-commandbar">
      <div class="terminal-commandbar-main">
        <div class="terminal-kicker">Pro Chart Terminal</div>
        <div class="terminal-title-row">
          <h1>{{ currentTicker }}</h1>
          <div class="terminal-name">{{ currentName }}</div>
        </div>
        <div class="terminal-meta-row">
          <span class="terminal-meta-pill" :class="Number(quote.change_pct || 0) >= 0 ? 'up' : 'dn'">
            {{ Number(quote.change_pct || 0) >= 0 ? "+" : "" }}{{ Number(quote.change_pct || 0).toFixed(2) }}%
          </span>
          <span class="terminal-meta-pill">
            現價 {{ quote.price == null ? "—" : Number(quote.price).toLocaleString() }}
          </span>
          <span class="terminal-meta-pill">
            抽屜 {{ rightCollapsed ? "收合" : normalizedDrawerTab === "journal" ? "快速日誌" : "警報中心" }}
          </span>
        </div>
      </div>

      <div class="terminal-commandbar-actions">
        <button class="terminal-action" type="button" @click="$emit('toggle-left')">
          {{ leftCollapsed ? "展開觀察池" : "收合觀察池" }}
        </button>
        <button class="terminal-action" type="button" @click="openDrawer('alerts')">
          警報抽屜
        </button>
        <button class="terminal-action" type="button" @click="openDrawer('journal')">
          快速日誌
        </button>
        <button class="terminal-action emphasis" type="button" @click="$emit('toggle-fullscreen')">
          {{ chartFullscreen ? "離開 Zen" : "Zen Mode" }}
        </button>
      </div>
    </div>

    <div class="terminal-stage">
      <button
        v-if="leftCollapsed"
        class="terminal-collapsed-toggle left"
        type="button"
        @click="$emit('toggle-left')"
      >
        觀察池
      </button>

      <TerminalTickerRail
        v-if="!leftCollapsed"
        :items="watchlist"
        :groups="groups"
        :active-group-id="activeGroupId"
        :active-ticker="currentTicker"
        @select-ticker="$emit('select-ticker', $event)"
        @open-overview="$emit('open-overview')"
      />

      <div class="terminal-chart-shell">
        <ChartWorkspace
          :current-ticker="currentTicker"
          :current-name="currentName"
          :timeframe-options="timeframeOptions"
          :current-period="currentPeriod"
          :current-interval="currentInterval"
          :quote="quote"
          :active-tool="activeTool"
          :active-panels="activePanels"
          :kline-display-mode="klineDisplayMode"
          :engine-mode="chartEngineMode"
          :clean-chart-mode="cleanChartMode"
          :chart-layout="chartLayout"
          :loading="chartLoading"
          :loading-message="loadingMessage"
          :crosshair="crosshair"
          :ohlc-data="ohlcData"
          :active-ind="activeInd"
          :indicator-settings="indicatorSettings"
          :drawings="drawings"
          :selected-drawing-id="selectedDrawingId"
          :workspace-presets="workspacePresets"
          :active-workspace-preset-id="activeWorkspacePresetId"
          :syncing-current="syncingCurrent"
          :compare-series="compareSeries"
          :comparison-mode="comparisonMode"
          :institutional-overlay="institutionalOverlay"
          :ticker-events="tickerEvents"
          :macro-summary="macroSummary"
          :is-fullscreen="chartFullscreen"
          @set-tool="$emit('set-tool', $event)"
          @add-signal="$emit('add-signal', $event)"
          @clear-drawings="$emit('clear-drawings')"
          @remove-last-drawing="$emit('remove-last-drawing')"
          @sync-current="$emit('sync-current')"
          @add-horizontal-line="$emit('add-horizontal-line', $event)"
          @add-drawing="$emit('add-drawing', $event)"
          @select-drawing="$emit('select-drawing', $event)"
          @remove-drawing="$emit('remove-drawing', $event)"
          @update-drawing="$emit('update-drawing', $event)"
          @toggle-drawing-visibility="$emit('toggle-drawing-visibility', $event)"
          @toggle-drawing-lock="$emit('toggle-drawing-lock', $event)"
          @save-workspace="$emit('save-workspace', $event)"
          @load-workspace="$emit('load-workspace', $event)"
          @delete-workspace="$emit('delete-workspace', $event)"
          @update-crosshair="$emit('update-crosshair', $event)"
          @hide-crosshair="$emit('hide-crosshair')"
          @add-compare="$emit('add-compare', $event)"
          @remove-compare="$emit('remove-compare', $event)"
          @clear-compare="$emit('clear-compare')"
          @set-compare-mode="$emit('set-compare-mode', $event)"
          @set-timeframe="$emit('set-timeframe', $event)"
          @set-kline-display-mode="$emit('set-kline-display-mode', $event)"
          @set-engine-mode="$emit('set-chart-engine-mode', $event)"
          @set-chart-layout="$emit('set-chart-layout', $event)"
          @clear-indicators="$emit('clear-indicators')"
          @open-journal-entry="$emit('open-journal-entry', $event)"
          @toggle-fullscreen="$emit('toggle-fullscreen')"
        />
      </div>

      <button
        v-if="rightCollapsed"
        class="terminal-collapsed-toggle right"
        type="button"
        @click="openDrawer('alerts')"
      >
        工具抽屜
      </button>

      <TerminalUtilityDrawer
        v-if="!rightCollapsed"
        :right-tab="normalizedDrawerTab"
        :current-ticker="currentTicker"
        :alerts="alerts"
        :alert-trigger-logs="alertTriggerLogs"
        :alert-log-loading="alertLogLoading"
        :expanded-alert-log-id="expandedAlertLogId"
        :journal-form="journalForm"
        :journal-loading="journalLoading"
        @close="$emit('toggle-right')"
        @set-right-tab="$emit('set-right-tab', $event)"
        @open-watch-group="$emit('open-watch-group', $event)"
        @toggle-alert-active="$emit('toggle-alert-active', $event)"
        @toggle-alert-log="$emit('toggle-alert-log', $event)"
        @delete-alert="$emit('delete-alert', $event)"
        @open-alert-modal="$emit('open-alert-modal')"
        @update-journal-field="$emit('update-journal-field', $event)"
        @add-journal-attachment="$emit('add-journal-attachment')"
        @remove-journal-attachment="$emit('remove-journal-attachment', $event)"
        @save-journal-entry="$emit('save-journal-entry')"
        @reset-journal-form="$emit('reset-journal-form')"
        @delete-journal-entry="$emit('delete-journal-entry', $event)"
      />
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";

import ChartWorkspace from "../ChartWorkspace.vue";
import TerminalTickerRail from "./TerminalTickerRail.vue";
import TerminalUtilityDrawer from "./TerminalUtilityDrawer.vue";

const props = defineProps({
  groups: { type: Array, default: () => [] },
  activeGroupId: { type: Number, default: null },
  watchlist: { type: Array, default: () => [] },
  timeframeOptions: { type: Array, default: () => [] },
  currentTicker: { type: String, required: true },
  currentName: { type: String, required: true },
  currentPeriod: { type: String, default: "1y" },
  currentInterval: { type: String, default: "1d" },
  quote: { type: Object, required: true },
  activeTool: { type: String, required: true },
  activePanels: { type: Object, required: true },
  klineDisplayMode: { type: String, required: true },
  chartEngineMode: { type: String, default: "legacy" },
  cleanChartMode: { type: Boolean, required: true },
  chartLayout: { type: String, required: true },
  chartLoading: { type: Boolean, required: true },
  loadingMessage: { type: String, required: true },
  crosshair: { type: Object, required: true },
  ohlcData: { type: Array, default: () => [] },
  activeInd: { type: Object, required: true },
  indicatorSettings: { type: Object, required: true },
  drawings: { type: Array, default: () => [] },
  selectedDrawingId: { type: [String, Number], default: null },
  workspacePresets: { type: Array, default: () => [] },
  activeWorkspacePresetId: { type: [String, Number], default: null },
  syncingCurrent: { type: Boolean, required: true },
  compareSeries: { type: Array, default: () => [] },
  comparisonMode: { type: String, required: true },
  institutionalOverlay: { type: Object, default: null },
  tickerEvents: { type: Array, default: () => [] },
  macroSummary: { type: Object, default: null },
  alerts: { type: Array, default: () => [] },
  alertTriggerLogs: { type: Object, default: () => ({}) },
  alertLogLoading: { type: Object, default: () => ({}) },
  expandedAlertLogId: { type: [String, Number], default: null },
  journalForm: { type: Object, required: true },
  journalLoading: { type: Boolean, required: true },
  rightTab: { type: String, default: "alerts" },
  leftCollapsed: { type: Boolean, required: true },
  rightCollapsed: { type: Boolean, required: true },
  chartFullscreen: { type: Boolean, required: true },
});

const emit = defineEmits([
  "open-overview",
  "toggle-left",
  "toggle-right",
  "select-ticker",
  "set-right-tab",
  "toggle-fullscreen",
  "open-watch-group",
  "toggle-alert-active",
  "toggle-alert-log",
  "delete-alert",
  "open-alert-modal",
  "update-journal-field",
  "add-journal-attachment",
  "remove-journal-attachment",
  "save-journal-entry",
  "reset-journal-form",
  "delete-journal-entry",
  "set-tool",
  "add-signal",
  "clear-drawings",
  "remove-last-drawing",
  "sync-current",
  "add-horizontal-line",
  "add-drawing",
  "select-drawing",
  "remove-drawing",
  "update-drawing",
  "toggle-drawing-visibility",
  "toggle-drawing-lock",
  "save-workspace",
  "load-workspace",
  "delete-workspace",
  "update-crosshair",
  "hide-crosshair",
  "add-compare",
  "remove-compare",
  "clear-compare",
  "set-compare-mode",
  "set-timeframe",
  "set-kline-display-mode",
  "set-chart-engine-mode",
  "set-chart-layout",
  "clear-indicators",
  "open-journal-entry",
]);

const normalizedDrawerTab = computed(() => (props.rightTab === "journal" ? "journal" : "alerts"));

function openDrawer(tab) {
  emit("set-right-tab", tab);
  if (props.rightCollapsed) {
    emit("toggle-right");
  }
}
</script>

<style scoped>
.terminal-page {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  flex: 1;
  background:
    radial-gradient(circle at top left, rgba(59, 139, 255, 0.08), transparent 24%),
    linear-gradient(180deg, rgba(7, 12, 19, 0.98), rgba(8, 13, 21, 0.98));
}

.terminal-commandbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 18px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(9, 14, 23, 0.88);
  backdrop-filter: blur(16px);
}

.terminal-kicker {
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text3);
}

.terminal-title-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-top: 6px;
}

.terminal-title-row h1 {
  font-family: "Syne", sans-serif;
  font-size: 30px;
  line-height: 1;
}

.terminal-name {
  color: var(--text3);
  font-size: 12px;
}

.terminal-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.terminal-meta-pill {
  padding: 6px 9px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  font-size: 10px;
}

.terminal-meta-pill.up {
  color: var(--green);
}

.terminal-meta-pill.dn {
  color: var(--red);
}

.terminal-commandbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.terminal-action {
  padding: 9px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  font-size: 11px;
}

.terminal-action.emphasis {
  border-color: rgba(123, 231, 255, 0.26);
  background: rgba(123, 231, 255, 0.12);
  color: #d7fbff;
}

.terminal-stage {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  position: relative;
}

.terminal-chart-shell {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.terminal-collapsed-toggle {
  position: absolute;
  top: 18px;
  z-index: 9;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(7, 12, 19, 0.9);
  color: var(--text2);
  cursor: pointer;
  font-size: 10px;
  backdrop-filter: blur(14px);
}

.terminal-collapsed-toggle.left {
  left: 18px;
}

.terminal-collapsed-toggle.right {
  right: 18px;
}

@media (max-width: 1200px) {
  .terminal-commandbar {
    flex-direction: column;
  }

  .terminal-commandbar-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 960px) {
  .terminal-title-row h1 {
    font-size: 24px;
  }
}
</style>
