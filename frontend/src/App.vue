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
        :groups="userWatchGroups"
        :market-items="marketWatchItems"
        :active-group-id="activeWatchGroupId"
        :items="watchlist"
        :left-tab="leftTab"
        :active-ticker="currentTicker"
        :loading="watchlistLoading"
        :error="watchlistError"
        @set-left-tab="setLeftTab"
        @select-group="setActiveWatchGroup"
        @create-group="createWatchGroup"
        @rename-group="renameWatchGroup"
        @delete-group="deleteWatchGroup"
        @add-to-watchlist="addTickerToWatchlist"
        @remove-from-watchlist="removeTickerFromWatchlist"
        @reorder-items="reorderWatchlistItems"
        @select-ticker="handleSelectTicker"
      />

      <div
        ref="workspaceStageRef"
        class="workspace-stage"
        :class="{ 'is-pseudo-fullscreen': pseudoFullscreen }"
      >
        <div class="workspace-shell">
            <div class="workspace-mode-tabs">
              <button class="tool-btn" :class="{ active: workspaceTab === 'chart' }" @click="setWorkspaceTab('chart')">圖表分析</button>
              <button class="tool-btn" :class="{ active: workspaceTab === 'institutional' }" @click="setWorkspaceTab('institutional')">法人籌碼</button>
              <button class="tool-btn" :class="{ active: workspaceTab === 'events' }" @click="setWorkspaceTab('events')">事件中心</button>
              <button class="tool-btn" :class="{ active: workspaceTab === 'macro' }" @click="setWorkspaceTab('macro')">宏觀風險</button>
              <button class="tool-btn" :class="{ active: workspaceTab === 'screener' }" @click="setWorkspaceTab('screener')">選股器</button>
            </div>

          <template v-if="workspaceTab === 'chart'">
            <div class="workspace-content">
              <ChartWorkspace
                :current-ticker="currentTicker"
                :current-name="currentName"
                :quote="quote"
                :active-tool="activeTool"
                :active-panels="activePanels"
                :kline-display-mode="klineDisplayMode"
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
                :ticker-news="tickerNews"
                :fundamentals-summary="fundamentalsSummary"
                :taiwan-chip-summary="taiwanChipSummary"
                :is-fullscreen="chartFullscreen"
                @set-tool="setTool"
                @add-signal="addSignal"
                @clear-drawings="clearDrawings"
                @remove-last-drawing="removeLastDrawing"
                @sync-current="syncCurrentTicker"
                @add-horizontal-line="addHorizontalLine"
                @add-drawing="addDrawing"
                @select-drawing="selectDrawing"
                @remove-drawing="removeDrawing"
                @update-drawing="updateDrawing"
                @toggle-drawing-visibility="toggleDrawingVisibility"
                @toggle-drawing-lock="toggleDrawingLock"
                @save-workspace="saveWorkspacePreset"
                @load-workspace="loadWorkspacePreset"
                @delete-workspace="deleteWorkspacePreset"
                @update-crosshair="updateCrosshair"
                @hide-crosshair="hideCrosshair"
                @add-compare="addCompareTicker"
                @remove-compare="removeCompareTicker"
                @clear-compare="clearCompareTickers"
                @set-compare-mode="setComparisonMode"
                @set-kline-display-mode="setKlineDisplayMode"
                @set-chart-layout="setChartLayout"
                @clear-indicators="clearIndicators"
                @open-journal-entry="startJournalEntry"
                @toggle-fullscreen="toggleChartFullscreen"
              />

              <RightSidebar
                :right-tab="rightTab"
                :indicator-snapshot="indicatorSnapshot"
                :active-ind="activeInd"
                :active-panels="activePanels"
                :indicator-settings="indicatorSettings"
                :alerts="alerts"
                :alert-trigger-logs="alertTriggerLogs"
                :alert-log-loading="alertLogLoading"
                :expanded-alert-log-id="expandedAlertLogId"
                :backtest-form="backtestForm"
                :backtest-result="backtestResult"
                :backtest-history="backtestHistory"
                :backtest-loading="backtestLoading"
                :journal-form="journalForm"
                :journal-entries="journalEntries"
                :journal-stats="journalStats"
                :journal-loading="journalLoading"
                :journal-filter-scope="journalFilterScope"
                :journal-filters="journalFilters"
                :db-stats="dbStats"
                :db-stats-loading="dbStatsLoading"
                :db-stats-error="dbStatsError"
                :syncing-all="syncingAll"
                @set-right-tab="setRightTab"
                @toggle-indicator="toggleIndicator"
                @toggle-panel="togglePanel"
                @update-indicator-setting="updateIndicatorSetting"
                @apply-indicator-preset="applyIndicatorPreset"
                @open-alert-modal="openAlertModal"
                @toggle-alert-active="toggleAlertActive"
                @toggle-alert-log="toggleAlertLog"
                @delete-alert="deleteAlert"
                @update-backtest-field="handleBacktestField"
                @run-backtest="runBacktest"
                @load-backtest="selectBacktestRun"
                @update-journal-field="handleJournalField"
                @update-journal-filter="handleJournalFilter"
                @save-journal-entry="saveJournalEntry"
                @delete-journal-entry="deleteJournalEntry"
                @select-journal-entry="selectJournalEntry"
                @reset-journal-form="resetJournalForm"
                @add-journal-attachment="addJournalAttachment"
                @remove-journal-attachment="removeJournalAttachment"
                @sync-all="syncAll"
              />
            </div>
          </template>
          <InstitutionalDashboard
            v-else-if="workspaceTab === 'institutional'"
            :data="institutionalData"
            :insights="institutionalInsights"
            :loading="institutionalLoading"
            :error="institutionalError"
            :insights-loading="institutionalInsightsLoading"
            :insights-error="institutionalInsightsError"
            :selected-date="institutionalDate"
            :selected-futures-commodity="institutionalFuturesCommodity"
            :selected-options-commodity="institutionalOptionsCommodity"
            :history-days="institutionalHistoryDays"
            @set-date="setInstitutionalDate"
            @shift-date="shiftInstitutionalDate"
            @refresh-dashboard="loadInstitutionalData(institutionalDate, true)"
            @refresh-insights="loadInstitutionalInsights(institutionalDate, institutionalFuturesCommodity, institutionalOptionsCommodity, institutionalHistoryDays, true)"
            @set-futures-commodity="setInstitutionalFuturesCommodity"
            @set-options-commodity="setInstitutionalOptionsCommodity"
            @set-history-days="setInstitutionalHistoryDays"
          />

          <EventCenter
            v-else-if="workspaceTab === 'events'"
            :current-ticker="currentTicker"
            :current-name="currentName"
            :calendar-events="calendarEvents"
            :ticker-events="tickerEvents"
            :ticker-news="tickerNews"
            @refresh-events="loadEventCalendar(true)"
            @refresh-news="loadTickerIntelligence(currentTicker, true)"
            @open-ticker="handleSelectTicker({ ticker: $event, name: $event })"
          />

          <MacroDashboard
            v-else-if="workspaceTab === 'macro'"
            :macro-dashboard="macroDashboard"
            @refresh="loadMacroDashboard(true)"
          />

          <ScreenerWorkspace
            v-else
            :filters="screenerFilters"
            :results="screenerResults"
            :presets="screenerPresets"
            :loading="screenerLoading"
            :current-ticker="currentTicker"
            @update-filter="handleScreenerFilter"
            @run-screen="runScreener"
            @save-preset="saveScreenerPreset"
            @load-preset="loadScreenerPreset"
            @delete-preset="deleteScreenerPreset"
            @open-ticker="handleSelectTicker({ ticker: $event, name: $event })"
            @add-watchlist="addTickerToWatchlist"
          />
        </div>
      </div>
    </div>

    <StatusBar
      :connected="wsConnected"
      :backend-url="backendUrl"
      :latency="latency"
      :quote-source="quote.source || 'local_cache'"
      :quote-mode="quote.is_delayed ? '延遲快照' : '即時報價'"
      :last-update="lastUpdate"
      :clock-time="clockTime"
    />

    <NotificationPanel
      :notifications="notifications"
      @dismiss="dismissNotification"
      @toggle-read="handleNotificationReadToggle"
      @open-ticker="handleOpenNotificationTicker"
    />

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
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import AlertModal from "./components/AlertModal.vue";
import ChartWorkspace from "./components/ChartWorkspace.vue";
import DashboardTopbar from "./components/DashboardTopbar.vue";
import EventCenter from "./components/EventCenter.vue";
import InstitutionalDashboard from "./components/InstitutionalDashboard.vue";
import MacroDashboard from "./components/MacroDashboard.vue";
import NotificationPanel from "./components/NotificationPanel.vue";
import RightSidebar from "./components/RightSidebar.vue";
import ScreenerWorkspace from "./components/ScreenerWorkspace.vue";
import StatusBar from "./components/StatusBar.vue";
import WatchlistPanel from "./components/WatchlistPanel.vue";
import { useDashboard } from "./composables/useDashboard";

const workspaceStageRef = ref(null);
const chartFullscreen = ref(false);
const pseudoFullscreen = ref(false);

const {
  timeframeOptions,
  searchQuery,
  searchResults,
  searchOpen,
  watchlistGroups,
  userWatchGroups,
  marketWatchItems,
  activeWatchGroupId,
  workspacePresets,
  activeWorkspacePresetId,
  compareSeries,
  comparisonMode,
  watchlist,
  watchlistLoading,
  watchlistError,
  leftTab,
  rightTab,
  workspaceTab,
  currentTicker,
  currentName,
  currentPeriod,
  currentInterval,
  klineDisplayMode,
  cleanChartMode,
  chartLayout,
  chartLoading,
  loadingMessage,
  ohlcData,
  drawings,
  selectedDrawingId,
  alerts,
  alertTriggerLogs,
  alertLogLoading,
  expandedAlertLogId,
  notifications,
  wsConnected,
  latency,
  lastUpdate,
  clockTime,
  dbStats,
  dbStatsLoading,
  dbStatsError,
  institutionalDate,
  institutionalData,
  institutionalLoading,
  institutionalError,
  institutionalInsights,
  institutionalInsightsLoading,
  institutionalInsightsError,
  institutionalFuturesCommodity,
  institutionalOptionsCommodity,
  institutionalHistoryDays,
  calendarEvents,
  tickerEvents,
  tickerNews,
  macroDashboard,
  fundamentalsSummary,
  taiwanChipSummary,
  screenerFilters,
  screenerResults,
  screenerPresets,
  screenerLoading,
  syncingCurrent,
  syncingAll,
  quote,
  marketStatus,
  activeInd,
  activePanels,
  indicatorSettings,
  activeTool,
  crosshair,
  alertModalOpen,
  alertForm,
  backtestForm,
  backtestResult,
  backtestHistory,
  backtestLoading,
  journalForm,
  journalEntries,
  journalStats,
  journalLoading,
  journalFilterScope,
  journalFilters,
  indicatorSnapshot,
  institutionalOverlay,
  backendUrl,
  searchSymbols,
  closeSearch,
  submitSearch,
  selectSearchResult,
  createWatchGroup,
  renameWatchGroup,
  deleteWatchGroup,
  addTickerToWatchlist,
  removeTickerFromWatchlist,
  reorderWatchlistItems,
  addCompareTicker,
  removeCompareTicker,
  clearCompareTickers,
  setComparisonMode,
  setTimeframe,
  setKlineDisplayMode,
  setLeftTab,
  setActiveWatchGroup,
  setRightTab,
  setWorkspaceTab,
  setInstitutionalDate,
  setInstitutionalFuturesCommodity,
  setInstitutionalOptionsCommodity,
  setInstitutionalHistoryDays,
  shiftInstitutionalDate,
  loadInstitutionalData,
  loadInstitutionalInsights,
  loadEventCalendar,
  loadMacroDashboard,
  loadTickerIntelligence,
  setChartLayout,
  selectTicker,
  toggleIndicator,
  togglePanel,
  updateIndicatorSetting,
  applyIndicatorPreset,
  clearIndicators,
  setTool,
  addSignal,
  clearDrawings,
  addHorizontalLine,
  addDrawing,
  removeLastDrawing,
  selectDrawing,
  removeDrawing,
  updateDrawing,
  toggleDrawingVisibility,
  toggleDrawingLock,
  saveWorkspacePreset,
  loadWorkspacePreset,
  deleteWorkspacePreset,
  updateCrosshair,
  hideCrosshair,
  syncCurrentTicker,
  syncAll,
  dismissNotification,
  setNotificationRead,
  openAlertModal,
    closeAlertModal,
    updateAlertField,
    saveAlert,
    toggleAlertLog,
    toggleAlertActive,
    deleteAlert,
    updateBacktestField,
    runBacktest,
    selectBacktestRun,
    updateJournalField,
    updateJournalFilter,
    saveJournalEntry,
    deleteJournalEntry,
    selectJournalEntry,
    resetJournalForm,
    addJournalAttachment,
  removeJournalAttachment,
  startJournalEntry,
  updateScreenerFilter,
  runScreener,
  saveScreenerPreset,
  loadScreenerPreset,
  deleteScreenerPreset,
  } = useDashboard();

function syncChartFullscreenState() {
  chartFullscreen.value = pseudoFullscreen.value || document.fullscreenElement === workspaceStageRef.value;
  nextTick(() => {
    window.dispatchEvent(new Event("resize"));
  });
}

async function toggleChartFullscreen() {
  const stage = workspaceStageRef.value;
  if (!stage) return;

  if (document.fullscreenEnabled && typeof stage.requestFullscreen === "function") {
    try {
      if (document.fullscreenElement === stage) {
        await document.exitFullscreen();
      } else {
        pseudoFullscreen.value = false;
        await stage.requestFullscreen();
      }
      return;
    } catch (error) {
      pseudoFullscreen.value = !pseudoFullscreen.value;
      syncChartFullscreenState();
    }
  }

  pseudoFullscreen.value = !pseudoFullscreen.value;
  syncChartFullscreenState();
}

function handleFullscreenChange() {
  if (pseudoFullscreen.value) return;
  syncChartFullscreenState();
}

function handleWindowKeydown(event) {
  if (event.key === "Escape" && pseudoFullscreen.value) {
    pseudoFullscreen.value = false;
    syncChartFullscreenState();
  }
}

function handleSelectTicker(item) {
  if (!item) return;
  setWorkspaceTab("chart");
  selectTicker(item.ticker, item.name || item.ticker);
}

function handleOpenDbTab() {
  setWorkspaceTab("chart");
  setRightTab("db");
}

function handleNotificationReadToggle(payload) {
  if (!payload?.id || typeof payload.read !== "boolean") return;
  setNotificationRead(payload.id, payload.read);
}

function handleOpenNotificationTicker(ticker) {
  if (!ticker) return;
  setWorkspaceTab("chart");
  selectTicker(ticker, ticker);
}

function handleAlertField(payload) {
  if (!payload?.key) return;
  updateAlertField(payload.key, payload.value);
}

function handleBacktestField(payload) {
  if (!payload?.key) return;
  updateBacktestField(payload.key, payload.value);
}

function handleJournalField(payload) {
  if (!payload?.key) return;
  updateJournalField(payload.key, payload.value);
}

function handleJournalFilter(payload) {
  if (!payload?.key) return;
  updateJournalFilter(payload.key, payload.value);
}

function handleScreenerFilter(payload) {
  if (!payload?.key) return;
  updateScreenerFilter(payload.key, payload.value);
}

onMounted(() => {
  document.addEventListener("fullscreenchange", handleFullscreenChange);
  window.addEventListener("keydown", handleWindowKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", handleFullscreenChange);
  window.removeEventListener("keydown", handleWindowKeydown);
});
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
