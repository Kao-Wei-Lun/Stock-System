<template>
  <div class="app-shell">
    <DashboardTopbar
      ref="dashboardTopbarRef"
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
        @open-journal-entry="handleWatchlistJournalEntry"
        @open-alert-modal="handleWatchlistAlertShortcut"
        @create-alerts-batch="handleWatchlistAlertBatch"
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
                :macro-summary="macroDashboard.summary || null"
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
                :current-ticker="currentTicker"
                :indicator-snapshot="indicatorSnapshot"
                :active-ind="activeInd"
                :active-panels="activePanels"
                :indicator-settings="indicatorSettings"
                :macro-summary="macroDashboard.summary || null"
                :ticker-events="tickerEvents"
                :ticker-news="tickerNews"
                :fundamentals-summary="fundamentalsSummary"
                :taiwan-chip-summary="taiwanChipSummary"
                :alerts="alerts"
                :alert-trigger-logs="alertTriggerLogs"
                :alert-log-loading="alertLogLoading"
                :expanded-alert-log-id="expandedAlertLogId"
                :backtest-form="backtestForm"
                :backtest-result="backtestResult"
                :backtest-history="backtestHistory"
                :backtest-compare-ids="backtestCompareIds"
                :backtest-compare-runs="backtestCompareRuns"
                :backtest-loading="backtestLoading"
                :journal-form="journalForm"
                :journal-entries="journalEntries"
                :journal-stats="journalStats"
                :journal-loading="journalLoading"
                :journal-filter-presets="journalFilterPresets"
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
                @focus-event="focusTickerEvent"
                @open-alert-modal="handleRightSidebarAlertShortcut"
                @open-watch-group="handleNotificationWatchGroup"
                @toggle-alert-active="toggleAlertActive"
                @toggle-alert-log="toggleAlertLog"
                @delete-alert="deleteAlert"
                @update-backtest-field="handleBacktestField"
                @run-backtest="runBacktest"
                @load-backtest="selectBacktestRun"
                @toggle-backtest-compare="toggleBacktestCompare"
                @clear-backtest-compare="clearBacktestCompare"
                @update-journal-field="handleJournalField"
                @update-journal-filter="handleJournalFilter"
                @apply-journal-filter-preset="handleJournalFilterPreset"
                @save-journal-filter-preset="saveJournalFilterPreset"
                @load-journal-filter-preset="loadJournalFilterPreset"
                @delete-journal-filter-preset="deleteJournalFilterPreset"
                @save-journal-entry="saveJournalEntry"
                @delete-journal-entry="deleteJournalEntry"
                @select-journal-entry="selectJournalEntry"
                @reset-journal-form="resetJournalForm"
                @add-journal-attachment="addJournalAttachment"
                @remove-journal-attachment="removeJournalAttachment"
                @create-watch-group="handleJournalResultWatchGroup"
                @add-watchlist="handleJournalResultWatchlist"
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
            @create-alert="openAlertModal($event)"
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
            @create-alert="openAlertModal($event)"
          />

          <MacroDashboard
            v-else-if="workspaceTab === 'macro'"
            :macro-dashboard="macroDashboard"
            @refresh="loadMacroDashboard(true)"
            @create-alert="handleMacroAlertShortcut"
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
            @open-journal-entry="handleScreenerJournalEntry"
            @add-alert="openAlertModal($event)"
          />
        </div>
      </div>
    </div>

    <StatusBar
      :connected="wsConnected"
      :backend-url="backendUrl"
      :latency="latency"
      :quote-source="quote.source || 'local_cache'"
      :quote-mode="quote.is_delayed ? '延遲快照' : '最新快照'"
      :quote-timestamp="quote.quote_timestamp"
      :quote-synced-at="quote.synced_at"
      :quote-delayed="quote.is_delayed"
      :last-update="lastUpdate"
      :clock-time="clockTime"
    />

    <ToastStack
      :notifications="notifications"
      @dismiss="dismissNotification"
    />

    <NotificationPanel
      :notifications="notifications"
      @dismiss="dismissNotification"
      @toggle-read="handleNotificationReadToggle"
      @open-ticker="handleOpenNotificationTicker"
      @open-workspace="handleOpenNotificationWorkspace"
      @open-watch-group="handleNotificationWatchGroup"
      @open-journal-entry="handleNotificationJournalEntry"
      @save-journal-filter-preset="saveJournalFilterPreset"
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
import {
  defineAsyncComponent,
  isRef,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import DashboardTopbar from "./components/DashboardTopbar.vue";
import StatusBar from "./components/StatusBar.vue";
import ToastStack from "./components/ToastStack.vue";
import WatchlistPanel from "./components/WatchlistPanel.vue";
import { useDashboard } from "./composables/useDashboard";
import { useHotkeys } from "./composables/useHotkeys";

const ChartWorkspace = defineAsyncComponent(() => import("./components/ChartWorkspace.vue"));
const RightSidebar = defineAsyncComponent(() => import("./components/RightSidebar.vue"));
const InstitutionalDashboard = defineAsyncComponent(() => import("./components/InstitutionalDashboard.vue"));
const EventCenter = defineAsyncComponent(() => import("./components/EventCenter.vue"));
const MacroDashboard = defineAsyncComponent(() => import("./components/MacroDashboard.vue"));
const ScreenerWorkspace = defineAsyncComponent(() => import("./components/ScreenerWorkspace.vue"));
const NotificationPanel = defineAsyncComponent(() => import("./components/NotificationPanel.vue"));
const AlertModal = defineAsyncComponent(() => import("./components/AlertModal.vue"));

const props = defineProps({
  routeWorkspaceTab: { type: String, default: "chart" },
  routeRightTab: { type: String, default: "indicators" },
  routeTicker: { type: String, default: "" },
});

const emit = defineEmits(["route-change"]);

const dashboardTopbarRef = ref(null);
const workspaceStageRef = ref(null);
const chartFullscreen = ref(false);
const pseudoFullscreen = ref(false);
const routeStateReady = ref(false);
const applyingRouteState = ref(false);

const {
  timeframeOptions,
  klineDisplayOptions,
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
  backtestCompareIds,
  backtestCompareRuns,
  backtestLoading,
  journalForm,
  journalEntries,
  journalStats,
  journalLoading,
  journalFilterPresets,
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
  addTickersToWatchlistBatch,
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
  focusTickerEvent,
  syncCurrentTicker,
  syncAll,
  dismissNotification,
  setNotificationRead,
  openAlertModal,
    closeAlertModal,
    updateAlertField,
    saveAlert,
    createAlertsBatch,
    toggleAlertLog,
    toggleAlertActive,
    deleteAlert,
    updateBacktestField,
    runBacktest,
    selectBacktestRun,
    toggleBacktestCompare,
    clearBacktestCompare,
    updateJournalField,
    updateJournalFilter,
    applyJournalFilterPreset,
    saveJournalFilterPreset,
    loadJournalFilterPreset,
    deleteJournalFilterPreset,
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

function readStateValue(source) {
  return isRef(source) ? source.value : source;
}

async function applyIncomingRouteState() {
  const nextTicker = String(props.routeTicker || "").trim().toUpperCase();
  const nextWorkspaceTab = String(props.routeWorkspaceTab || "chart");
  const nextRightTab = String(props.routeRightTab || "indicators");

  applyingRouteState.value = true;
  try {
    if (nextTicker && nextTicker !== readStateValue(currentTicker)) {
      await selectTicker(nextTicker, nextTicker);
    }
    if (nextWorkspaceTab !== readStateValue(workspaceTab)) {
      await setWorkspaceTab(nextWorkspaceTab);
    }
    if (nextWorkspaceTab === "chart" && nextRightTab !== readStateValue(rightTab)) {
      await setRightTab(nextRightTab);
    }
  } finally {
    applyingRouteState.value = false;
    routeStateReady.value = true;
  }
}

watch(
  () => [props.routeWorkspaceTab, props.routeRightTab, props.routeTicker],
  () => {
    void applyIncomingRouteState();
  },
  { immediate: true },
);

watch(
  () => [
    readStateValue(workspaceTab),
    readStateValue(rightTab),
    readStateValue(currentTicker),
  ],
  ([nextWorkspaceTab, nextRightTab, nextTicker]) => {
    if (!routeStateReady.value || applyingRouteState.value) return;
    emit("route-change", {
      workspaceTab: nextWorkspaceTab,
      rightTab: nextRightTab,
      currentTicker: nextTicker,
    });
  },
);

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

function handleOpenNotificationWorkspace(workspace) {
  if (!workspace) return;
  setWorkspaceTab(workspace);
}

function handleNotificationJournalEntry(payload) {
  if (!payload?.ticker) return;
  setWorkspaceTab("chart");
  void selectTicker(payload.ticker, payload.name || payload.ticker);
  startJournalEntry(payload);
}

function handleNotificationWatchGroup(payload) {
  const groupName = String(payload?.groupName || "").trim();
  if (!groupName) return;
  setLeftTab("watch");
  const targetGroup = (userWatchGroups.value || []).find(
    (group) => String(group?.name || "").trim() === groupName,
  );
  if (targetGroup?.id) {
    setActiveWatchGroup(targetGroup.id);
  }
}

function handleMacroAlertShortcut(payload) {
  openAlertModal({
    ticker: "MARKET",
    type: payload?.type || "market_risk",
    condition: payload?.condition || "high",
    value: "",
  });
}

function handleScreenerJournalEntry(payload) {
  if (!payload?.ticker) return;
  setWorkspaceTab("chart");
  void selectTicker(payload.ticker, payload.name || payload.ticker);
  startJournalEntry(payload);
}

function handleWatchlistJournalEntry(payload) {
  if (!payload?.ticker) return;
  setWorkspaceTab("chart");
  void selectTicker(payload.ticker, payload.name || payload.ticker);
  startJournalEntry(payload);
}

function handleWatchlistAlertShortcut(payload) {
  if (!payload) {
    openAlertModal();
    return;
  }
  openAlertModal(payload);
}

function handleWatchlistAlertBatch(payloads) {
  if (!Array.isArray(payloads) || !payloads.length) return;
  setRightTab("alerts");
  void createAlertsBatch(payloads);
}

function handleJournalResultWatchlist(items) {
  if (!Array.isArray(items) || !items.length) return;
  setLeftTab("watch");
  void addTickersToWatchlistBatch(items);
}

function getUniqueWatchGroupName(baseName) {
  const trimmed = String(baseName || "").trim() || "日誌命中池";
  const existingNames = new Set(
    (userWatchGroups.value || [])
      .map((group) => String(group?.name || "").trim())
      .filter(Boolean),
  );
  if (!existingNames.has(trimmed)) return trimmed;
  let index = 2;
  let candidate = `${trimmed} (${index})`;
  while (existingNames.has(candidate)) {
    index += 1;
    candidate = `${trimmed} (${index})`;
  }
  return candidate;
}

async function handleJournalResultWatchGroup(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  if (!items.length) return;
  setLeftTab("watch");
  const groupName = getUniqueWatchGroupName(payload?.name);
  await createWatchGroup(groupName);
  const group = (userWatchGroups.value || []).find(
    (item) => String(item?.name || "").trim() === groupName,
  );
  if (!group?.id) return;
  await addTickersToWatchlistBatch(items, group.id);
}

function handleRightSidebarAlertShortcut(payload) {
  if (!payload) {
    openAlertModal();
    return;
  }
  if (payload?.ticker) {
    setWorkspaceTab("chart");
    void selectTicker(payload.ticker, payload.name || payload.ticker);
  }
  openAlertModal(payload);
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

function handleJournalFilterPreset(payload) {
  if (!payload || typeof payload !== "object") return;
  applyJournalFilterPreset(payload);
}

function handleScreenerFilter(payload) {
  if (!payload?.key) return;
  updateScreenerFilter(payload.key, payload.value);
}

function focusSearchInput() {
  dashboardTopbarRef.value?.focusSearchInput?.();
}

function shiftTimeframe(step) {
  const currentIndex = timeframeOptions.findIndex(
    (option) => option.tf === readStateValue(currentPeriod) && option.iv === readStateValue(currentInterval),
  );
  if (currentIndex < 0) return;
  const nextIndex = Math.max(0, Math.min(timeframeOptions.length - 1, currentIndex + step));
  if (nextIndex === currentIndex) return;
  void setTimeframe(timeframeOptions[nextIndex]);
}

function shiftKlineDisplay(step) {
  const optionKeys = (klineDisplayOptions || []).map((option) => option.key).filter(Boolean);
  const currentIndex = optionKeys.indexOf(String(readStateValue(klineDisplayMode) || "day"));
  if (currentIndex < 0) return;
  const nextIndex = Math.max(0, Math.min(optionKeys.length - 1, currentIndex + step));
  if (nextIndex === currentIndex) return;
  void setKlineDisplayMode(optionKeys[nextIndex]);
}

function getShortcutWorkspaceName() {
  const activeId = readStateValue(activeWorkspacePresetId);
  const presets = readStateValue(workspacePresets) || [];
  const activePreset = presets.find((item) => String(item?.id ?? "") === String(activeId ?? ""));
  if (activePreset?.name) return activePreset.name;
  return `${String(readStateValue(currentTicker) || "WORKSPACE").trim().toUpperCase()} Quick Save`;
}

async function handleSaveWorkspaceShortcut() {
  await saveWorkspacePreset(getShortcutWorkspaceName());
}

useHotkeys(() => [
  {
    key: "/",
    preventDefault: true,
    handler: focusSearchInput,
  },
  {
    key: "ArrowLeft",
    shiftKey: true,
    preventDefault: true,
    handler: () => shiftTimeframe(-1),
  },
  {
    key: "ArrowRight",
    shiftKey: true,
    preventDefault: true,
    handler: () => shiftTimeframe(1),
  },
  {
    key: "ArrowDown",
    shiftKey: true,
    preventDefault: true,
    handler: () => shiftKlineDisplay(-1),
  },
  {
    key: "ArrowUp",
    shiftKey: true,
    preventDefault: true,
    handler: () => shiftKlineDisplay(1),
  },
  {
    key: "s",
    ctrlOrMeta: true,
    allowInInputs: true,
    preventDefault: true,
    handler: () => {
      void handleSaveWorkspaceShortcut();
    },
  },
]);

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
