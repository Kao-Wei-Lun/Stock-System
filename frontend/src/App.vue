<template>
  <div class="app-shell">
    <AppNavbar
      ref="appNavbarRef"
      :workspace-page="activeWorkspacePage"
      :review-tab="reviewTab"
      :search-query="searchQuery"
      :search-results="searchResults"
      :search-open="searchOpen"
      :timeframe-options="timeframeOptions"
      :current-period="currentPeriod"
      :current-interval="currentInterval"
      :market-status="marketStatus"
      :ws-connected="wsConnected"
      @navigate="handleNavigate"
      @set-review-tab="handleReviewTabChange"
      @search-change="searchSymbols"
      @submit-search="submitSearch"
      @select-search-result="selectSearchResult"
      @close-search="closeSearch"
      @set-timeframe="setTimeframe"
      @open-alert-modal="openAlertModal"
    />

    <div
      v-if="activeWorkspacePage === 'terminal'"
      ref="workspaceStageRef"
      class="workspace-stage terminal-stage-shell"
      :class="{ 'is-pseudo-fullscreen': pseudoFullscreen }"
    >
      <ProChartTerminalWorkspace
        :groups="userWatchGroups"
        :active-group-id="activeWatchGroupId"
        :watchlist="watchlist"
        :current-ticker="currentTicker"
        :current-name="currentName"
        :quote="quote"
        :active-tool="activeTool"
        :active-panels="activePanels"
        :kline-display-mode="klineDisplayMode"
        :clean-chart-mode="cleanChartMode"
        :chart-layout="chartLayout"
        :chart-loading="chartLoading"
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
        :alerts="alerts"
        :alert-trigger-logs="alertTriggerLogs"
        :alert-log-loading="alertLogLoading"
        :expanded-alert-log-id="expandedAlertLogId"
        :journal-form="journalForm"
        :journal-loading="journalLoading"
        :right-tab="drawerTab"
        :left-collapsed="terminalLeftCollapsed"
        :right-collapsed="terminalRightCollapsed"
        :chart-fullscreen="chartFullscreen"
        @open-overview="handleNavigate('overview')"
        @toggle-left="toggleTerminalLeft"
        @toggle-right="toggleTerminalRight"
        @select-ticker="handleSelectTicker"
        @set-right-tab="handleDrawerTabChange"
        @toggle-fullscreen="toggleChartFullscreen"
        @open-watch-group="handleNotificationWatchGroup"
        @toggle-alert-active="toggleAlertActive"
        @toggle-alert-log="toggleAlertLog"
        @delete-alert="deleteAlert"
        @open-alert-modal="handleTerminalAlertShortcut"
        @update-journal-field="handleJournalField"
        @add-journal-attachment="addJournalAttachment"
        @remove-journal-attachment="removeJournalAttachment"
        @save-journal-entry="saveJournalEntry"
        @reset-journal-form="resetJournalForm"
        @delete-journal-entry="deleteJournalEntry"
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
        @open-journal-entry="handleTerminalJournalEntry"
      />
    </div>

    <div v-else class="workspace-stage page-stage-shell">
      <MarketOverviewWorkspace
        v-if="activeWorkspacePage === 'overview'"
        :groups="userWatchGroups"
        :market-items="marketWatchItems"
        :active-group-id="activeWatchGroupId"
        :watchlist="watchlist"
        :watchlist-loading="watchlistLoading"
        :watchlist-error="watchlistError"
        :left-tab="leftTab"
        :current-ticker="currentTicker"
        :current-name="currentName"
        :macro-dashboard="macroDashboard"
        :calendar-events="calendarEvents"
        :ticker-events="tickerEvents"
        :ticker-news="tickerNews"
        :screener-filters="screenerFilters"
        :screener-results="screenerResults"
        :screener-presets="screenerPresets"
        :screener-loading="screenerLoading"
        @open-terminal="handleOpenTerminal"
        @refresh-macro="loadMacroDashboard(true)"
        @refresh-events="loadEventCalendar(true)"
        @refresh-news="loadTickerIntelligence(currentTicker, true)"
        @create-alert="handleOverviewAlertShortcut"
        @set-left-tab="setLeftTab"
        @select-group="setActiveWatchGroup"
        @create-group="createWatchGroup"
        @rename-group="renameWatchGroup"
        @delete-group="deleteWatchGroup"
        @add-to-watchlist="addTickerToWatchlist"
        @remove-from-watchlist="removeTickerFromWatchlist"
        @reorder-items="reorderWatchlistItems"
        @select-ticker="handleSelectTicker"
        @open-journal-entry="handleOverviewJournalEntry"
        @open-alert-modal="handleOverviewAlertShortcut"
        @create-alerts-batch="handleWatchlistAlertBatch"
        @update-screener-filter="handleScreenerFilter"
        @run-screener="runScreener"
        @save-screener-preset="saveScreenerPreset"
        @load-screener-preset="loadScreenerPreset"
        @delete-screener-preset="deleteScreenerPreset"
      />

      <InstitutionalAnalysisWorkspace
        v-else-if="activeWorkspacePage === 'institutional'"
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
        @open-terminal="handleOpenTerminal(currentTicker)"
        @set-date="setInstitutionalDate"
        @shift-date="shiftInstitutionalDate"
        @refresh-dashboard="loadInstitutionalData(institutionalDate, true)"
        @refresh-insights="loadInstitutionalInsights(institutionalDate, institutionalFuturesCommodity, institutionalOptionsCommodity, institutionalHistoryDays, true)"
        @set-futures-commodity="setInstitutionalFuturesCommodity"
        @set-options-commodity="setInstitutionalOptionsCommodity"
        @set-history-days="setInstitutionalHistoryDays"
        @create-alert="openAlertModal($event)"
      />

      <ReviewWorkspace
        v-else
        :right-tab="reviewTab"
        :current-ticker="currentTicker"
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
        @open-terminal="handleOpenTerminal(currentTicker)"
        @set-right-tab="handleReviewWorkspaceTabChange"
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
        @open-alert-modal="openAlertModal($event)"
      />
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
      @select="handleToastSelect"
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
  isRef,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import AppNavbar from "./components/AppNavbar.vue";
import AlertModal from "./components/AlertModal.vue";
import NotificationPanel from "./components/NotificationPanel.vue";
import StatusBar from "./components/StatusBar.vue";
import ToastStack from "./components/ToastStack.vue";
import InstitutionalAnalysisWorkspace from "./components/workspaces/InstitutionalAnalysisWorkspace.vue";
import MarketOverviewWorkspace from "./components/workspaces/MarketOverviewWorkspace.vue";
import ProChartTerminalWorkspace from "./components/workspaces/ProChartTerminalWorkspace.vue";
import ReviewWorkspace from "./components/workspaces/ReviewWorkspace.vue";
import { useDashboard } from "./composables/useDashboard";
import { useHotkeys } from "./composables/useHotkeys";

const props = defineProps({
  routeWorkspaceTab: { type: String, default: "overview" },
  routeRightTab: { type: String, default: "indicators" },
  routeTicker: { type: String, default: "" },
});

const emit = defineEmits(["route-change"]);

const appNavbarRef = ref(null);
const workspaceStageRef = ref(null);
const chartFullscreen = ref(false);
const pseudoFullscreen = ref(false);
const routeStateReady = ref(false);
const applyingRouteState = ref(false);
const activeWorkspacePage = ref("overview");
const terminalLeftCollapsed = ref(true);
const terminalRightCollapsed = ref(true);

const {
  timeframeOptions,
  klineDisplayOptions,
  searchQuery,
  searchResults,
  searchOpen,
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
  screenerFilters,
  screenerResults,
  screenerPresets,
  screenerLoading,
  syncingCurrent,
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

const reviewTab = ref("journal");

function readStateValue(source) {
  return isRef(source) ? source.value : source;
}

const drawerTab = ref("alerts");

function normalizeWorkspacePage(value) {
  const normalized = String(value || "").toLowerCase();
  if (["overview", "terminal", "institutional", "review"].includes(normalized)) {
    return normalized;
  }
  if (["macro", "events", "screener", "db"].includes(normalized)) return "overview";
  if (["journal", "backtest"].includes(normalized)) return "review";
  if (["dashboard", "alerts", "chart"].includes(normalized)) return "terminal";
  return "overview";
}

function normalizeReviewTab(value) {
  return String(value || "").toLowerCase() === "backtest" ? "backtest" : "journal";
}

function normalizeDrawerTab(value) {
  return String(value || "").toLowerCase() === "journal" ? "journal" : "alerts";
}

async function closeTerminalFullscreenIfNeeded() {
  if (document.fullscreenElement === workspaceStageRef.value) {
    await document.exitFullscreen();
  }
  if (pseudoFullscreen.value) {
    pseudoFullscreen.value = false;
  }
  syncChartFullscreenState();
}

async function ensureWorkspaceResources(page, secondaryTab = "indicators") {
  if (page === "terminal") {
    await setWorkspaceTab("chart");
    const nextDrawerTab = normalizeDrawerTab(secondaryTab);
    drawerTab.value = nextDrawerTab;
    if (!terminalRightCollapsed.value) {
      await setRightTab(nextDrawerTab);
    }
    return;
  }

  if (page === "overview") {
    if (chartFullscreen.value || pseudoFullscreen.value || document.fullscreenElement) {
      await closeTerminalFullscreenIfNeeded();
    }
    await setWorkspaceTab("screener");
    await Promise.all([
      loadMacroDashboard(true),
      loadEventCalendar(true),
      loadTickerIntelligence(readStateValue(currentTicker), true),
      readStateValue(screenerResults)?.items?.length ? Promise.resolve() : runScreener(),
    ]);
    return;
  }

  if (page === "institutional") {
    if (chartFullscreen.value || pseudoFullscreen.value || document.fullscreenElement) {
      await closeTerminalFullscreenIfNeeded();
    }
    await setWorkspaceTab("institutional");
    return;
  }

  if (chartFullscreen.value || pseudoFullscreen.value || document.fullscreenElement) {
    await closeTerminalFullscreenIfNeeded();
  }
  await setWorkspaceTab("chart");
  reviewTab.value = normalizeReviewTab(secondaryTab);
  await setRightTab(reviewTab.value);
}

async function applyWorkspacePage(nextPage, secondaryTab = "indicators") {
  const previousPage = activeWorkspacePage.value;
  activeWorkspacePage.value = normalizeWorkspacePage(nextPage);
  if (activeWorkspacePage.value === "terminal" && previousPage !== "terminal") {
    terminalLeftCollapsed.value = true;
    terminalRightCollapsed.value = true;
  }
  await ensureWorkspaceResources(activeWorkspacePage.value, secondaryTab);
}

async function applyIncomingRouteState() {
  const nextTicker = String(props.routeTicker || "").trim().toUpperCase();
  const nextPage = normalizeWorkspacePage(props.routeWorkspaceTab);
  const nextRightTab = String(props.routeRightTab || "indicators");

  applyingRouteState.value = true;
  try {
    if (nextTicker && nextTicker !== readStateValue(currentTicker)) {
      await selectTicker(nextTicker, nextTicker);
    }
    await applyWorkspacePage(nextPage, nextRightTab);
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
    activeWorkspacePage.value,
    reviewTab.value,
    drawerTab.value,
    readStateValue(currentTicker),
  ],
  ([workspacePage, nextReviewTab, nextDrawerTab, nextTicker]) => {
    if (!routeStateReady.value || applyingRouteState.value) return;
    emit("route-change", {
      workspaceTab: workspacePage,
      rightTab: workspacePage === "review" ? nextReviewTab : nextDrawerTab,
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

function toggleTerminalLeft() {
  terminalLeftCollapsed.value = !terminalLeftCollapsed.value;
}

async function toggleTerminalRight() {
  const nextCollapsed = !terminalRightCollapsed.value;
  terminalRightCollapsed.value = nextCollapsed;
  if (!nextCollapsed) {
    await setRightTab(drawerTab.value);
  }
}

async function handleNavigate(page) {
  const nextPage = normalizeWorkspacePage(page);
  await applyWorkspacePage(nextPage, nextPage === "review" ? reviewTab.value : drawerTab.value);
}

async function handleReviewTabChange(tab) {
  reviewTab.value = normalizeReviewTab(tab);
  await applyWorkspacePage("review", reviewTab.value);
}

async function handleReviewWorkspaceTabChange(tab) {
  reviewTab.value = normalizeReviewTab(tab);
  await setRightTab(reviewTab.value);
}

async function handleDrawerTabChange(tab) {
  drawerTab.value = normalizeDrawerTab(tab);
  await setRightTab(drawerTab.value);
}

async function handleOpenTerminal(ticker) {
  await applyWorkspacePage("terminal", drawerTab.value);
  if (ticker) {
    const normalized = String(ticker).trim().toUpperCase();
    if (normalized && normalized !== readStateValue(currentTicker)) {
      await selectTicker(normalized, normalized);
    }
  }
}

async function openReviewWithJournal(payload) {
  reviewTab.value = "journal";
  await applyWorkspacePage("review", "journal");
  if (payload?.ticker) {
    await selectTicker(payload.ticker, payload.name || payload.ticker);
  }
  startJournalEntry(payload);
}

async function openTerminalWithTicker(ticker, name) {
  await applyWorkspacePage("terminal", "alerts");
  if (ticker) {
    await selectTicker(ticker, name || ticker);
  }
}

function handleSelectTicker(item) {
  if (!item?.ticker) return;
  selectTicker(item.ticker, item.name || item.ticker);
}

function handleNotificationReadToggle(payload) {
  if (!payload?.id || typeof payload.read !== "boolean") return;
  setNotificationRead(payload.id, payload.read);
}

async function handleOpenNotificationTicker(ticker) {
  if (!ticker) return;
  await openTerminalWithTicker(ticker, ticker);
}

function resolveWorkspaceTarget(target) {
  const normalized = String(target || "").toLowerCase();
  if (["macro", "events", "screener", "overview", "db"].includes(normalized)) return "overview";
  if (normalized === "institutional") return "institutional";
  if (["journal", "backtest", "review"].includes(normalized)) return "review";
  return "terminal";
}

async function handleOpenNotificationWorkspace(workspace) {
  const targetPage = resolveWorkspaceTarget(workspace);
  if (targetPage === "review") {
    await applyWorkspacePage("review", String(workspace || "").toLowerCase() === "backtest" ? "backtest" : "journal");
    return;
  }
  await applyWorkspacePage(targetPage, drawerTab.value);
}

async function handleNotificationJournalEntry(payload) {
  if (!payload?.ticker) return;
  await openReviewWithJournal(payload);
}

async function handleNotificationWatchGroup(payload) {
  const groupName = String(payload?.groupName || "").trim();
  if (!groupName) return;
  await applyWorkspacePage("overview", "indicators");
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

async function handleOverviewJournalEntry(payload) {
  if (!payload?.ticker) return;
  await openReviewWithJournal(payload);
}

function handleOverviewAlertShortcut(payload) {
  if (payload?.type === "market_risk") {
    handleMacroAlertShortcut(payload);
    return;
  }
  if (!payload) {
    openAlertModal();
    return;
  }
  openAlertModal(payload);
}

function handleTerminalAlertShortcut(payload) {
  if (!payload) {
    openAlertModal();
    return;
  }
  if (payload?.ticker) {
    void selectTicker(payload.ticker, payload.name || payload.ticker);
  }
  openAlertModal(payload);
}

async function handleTerminalJournalEntry(payload) {
  drawerTab.value = "journal";
  if (terminalRightCollapsed.value) {
    terminalRightCollapsed.value = false;
  }
  await setRightTab("journal");
  startJournalEntry(payload);
}

async function handleWatchlistAlertBatch(payloads) {
  if (!Array.isArray(payloads) || !payloads.length) return;
  drawerTab.value = "alerts";
  await setRightTab("alerts");
  await createAlertsBatch(payloads);
}

async function handleJournalResultWatchlist(items) {
  if (!Array.isArray(items) || !items.length) return;
  await applyWorkspacePage("overview", "indicators");
  setLeftTab("watch");
  await addTickersToWatchlistBatch(items);
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
  await applyWorkspacePage("overview", "indicators");
  setLeftTab("watch");
  const groupName = getUniqueWatchGroupName(payload?.name);
  await createWatchGroup(groupName);
  const group = (userWatchGroups.value || []).find(
    (item) => String(item?.name || "").trim() === groupName,
  );
  if (!group?.id) return;
  await addTickersToWatchlistBatch(items, group.id);
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

async function handleToastSelect(item) {
  if (!item) return;
  if (item.ticker) {
    await openTerminalWithTicker(item.ticker, item.name || item.ticker);
    await dismissNotification(item.id);
    return;
  }
  if (item.workspaceTarget) {
    await handleOpenNotificationWorkspace(item.workspaceTarget);
    await dismissNotification(item.id);
    return;
  }
  await dismissNotification(item.id);
}

function focusSearchInput() {
  appNavbarRef.value?.focusSearchInput?.();
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
  {
    key: "z",
    altKey: true,
    preventDefault: true,
    handler: () => {
      if (activeWorkspacePage.value !== "terminal") return;
      void toggleChartFullscreen();
    },
  },
  {
    key: "a",
    altKey: true,
    preventDefault: true,
    handler: () => {
      if (activeWorkspacePage.value !== "terminal") return;
      drawerTab.value = "alerts";
      if (terminalRightCollapsed.value) {
        terminalRightCollapsed.value = false;
      }
      void setRightTab("alerts");
      openAlertModal();
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

.workspace-stage {
  flex: 1;
  min-height: 0;
  min-width: 0;
}

.terminal-stage-shell {
  display: flex;
  overflow: hidden;
  background: var(--bg);
}

.terminal-stage-shell:fullscreen,
.terminal-stage-shell.is-pseudo-fullscreen {
  display: flex;
  overflow: hidden;
  background: var(--bg);
}

.terminal-stage-shell.is-pseudo-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 1400;
}

.page-stage-shell {
  overflow: hidden;
}
</style>
