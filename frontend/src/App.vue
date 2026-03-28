<template>
  <div class="app-shell">
    <DashboardTopbar
      :search-query="searchQuery"
      :search-results="searchResults"
      :search-open="searchOpen"
      :timeframe-options="timeframeOptions"
      :current-period="currentPeriod"
      :current-interval="currentInterval"
      :market-status="marketStatus"
      :ws-connected="wsConnected"
      @search-change="searchSymbols"
      @submit-search="submitSearch"
      @select-search-result="selectSearchResult"
      @close-search="closeSearch"
      @open-alert-modal="openAlertModal"
      @open-db-tab="handleOpenDbTab"
      @set-timeframe="setTimeframe"
    />

    <div class="main">
      <WatchlistPanel
        :items="watchlist"
        :left-tab="leftTab"
        :active-ticker="currentTicker"
        :loading="watchlistLoading"
        :error="watchlistError"
        @set-left-tab="setLeftTab"
        @select-ticker="handleSelectTicker"
      />

      <ChartWorkspace
        :current-ticker="currentTicker"
        :current-name="currentName"
        :quote="quote"
        :active-tool="activeTool"
        :active-panels="activePanels"
        :loading="chartLoading"
        :loading-message="loadingMessage"
        :crosshair="crosshair"
        :ohlc-data="ohlcData"
        :active-ind="activeInd"
        :drawings="drawings"
        :syncing-current="syncingCurrent"
        @set-tool="setTool"
        @add-signal="addSignal"
        @clear-drawings="clearDrawings"
        @remove-last-drawing="removeLastDrawing"
        @sync-current="syncCurrentTicker"
        @add-horizontal-line="addHorizontalLine"
        @add-drawing="addDrawing"
        @update-crosshair="updateCrosshair"
        @hide-crosshair="hideCrosshair"
      />

      <RightSidebar
        :right-tab="rightTab"
        :indicator-snapshot="indicatorSnapshot"
        :active-ind="activeInd"
        :active-panels="activePanels"
        :alerts="alerts"
        :backtest-form="backtestForm"
        :backtest-result="backtestResult"
        :db-stats="dbStats"
        :db-stats-error="dbStatsError"
        :syncing-all="syncingAll"
        @set-right-tab="setRightTab"
        @toggle-indicator="toggleIndicator"
        @toggle-panel="togglePanel"
        @open-alert-modal="openAlertModal"
        @update-backtest-field="handleBacktestField"
        @run-backtest="runBacktest"
        @sync-all="syncAll"
      />
    </div>

    <StatusBar
      :connected="wsConnected"
      :backend-url="backendUrl"
      :latency="latency"
      :last-update="lastUpdate"
      :clock-time="clockTime"
    />

    <NotificationPanel :notifications="notifications" @dismiss="dismissNotification" />

    <AlertModal
      :is-open="alertModalOpen"
      :form="alertForm"
      @close="closeAlertModal"
      @save="saveAlert"
      @update-field="handleAlertField"
    />
  </div>
</template>

<script setup>
import AlertModal from "./components/AlertModal.vue";
import ChartWorkspace from "./components/ChartWorkspace.vue";
import DashboardTopbar from "./components/DashboardTopbar.vue";
import NotificationPanel from "./components/NotificationPanel.vue";
import RightSidebar from "./components/RightSidebar.vue";
import StatusBar from "./components/StatusBar.vue";
import WatchlistPanel from "./components/WatchlistPanel.vue";
import { useDashboard } from "./composables/useDashboard";

const {
  timeframeOptions,
  searchQuery,
  searchResults,
  searchOpen,
  watchlist,
  watchlistLoading,
  watchlistError,
  leftTab,
  rightTab,
  currentTicker,
  currentName,
  currentPeriod,
  currentInterval,
  chartLoading,
  loadingMessage,
  ohlcData,
  drawings,
  alerts,
  notifications,
  wsConnected,
  latency,
  lastUpdate,
  clockTime,
  dbStats,
  dbStatsError,
  syncingCurrent,
  syncingAll,
  quote,
  marketStatus,
  activeInd,
  activePanels,
  activeTool,
  crosshair,
  alertModalOpen,
  alertForm,
  backtestForm,
  backtestResult,
  indicatorSnapshot,
  backendUrl,
  searchSymbols,
  closeSearch,
  submitSearch,
  selectSearchResult,
  setTimeframe,
  setLeftTab,
  setRightTab,
  selectTicker,
  toggleIndicator,
  togglePanel,
  setTool,
  addSignal,
  clearDrawings,
  addHorizontalLine,
  addDrawing,
  removeLastDrawing,
  updateCrosshair,
  hideCrosshair,
  syncCurrentTicker,
  syncAll,
  dismissNotification,
  openAlertModal,
  closeAlertModal,
  updateAlertField,
  saveAlert,
  updateBacktestField,
  runBacktest,
} = useDashboard();

function handleSelectTicker(item) {
  if (!item) return;
  selectTicker(item.ticker, item.name || item.ticker);
}

function handleOpenDbTab() {
  setRightTab("db");
}

function handleAlertField(payload) {
  if (!payload?.key) return;
  updateAlertField(payload.key, payload.value);
}

function handleBacktestField(payload) {
  if (!payload?.key) return;
  updateBacktestField(payload.key, payload.value);
}
</script>

<style>
#app,
.app-shell {
  height: 100%;
}

.app-shell {
  display: flex;
  flex-direction: column;
}
</style>
