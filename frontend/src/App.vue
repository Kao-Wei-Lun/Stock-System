<template>
  <div class="app-shell">
    <AppNavbar
      ref="appNavbarRef"
      :workspace-page="activeWorkspacePage"
      :review-tab="reviewTab"
      :search-query="searchQuery"
      :search-results="searchResults"
      :search-open="searchOpen && !commandPaletteOpen"
      :timeframe-options="timeframeOptions"
      :current-period="currentPeriod"
      :current-interval="currentInterval"
      :market-status="marketStatus"
      :ws-connected="wsConnected"
      :fubon-status="fubonStatus"
      :active-quote="quote"
      @navigate="handleNavigate"
      @set-review-tab="handleReviewTabChange"
      @search-change="searchSymbols"
      @submit-search="submitSearch"
      @select-search-result="selectSearchResult"
      @close-search="closeSearch"
      @set-timeframe="setTimeframe"
      @open-heatmap="handleOpenHeatmap"
      @open-alert-modal="openAlertModal"
      @open-command-palette="openCommandPalette"
    />

    <section v-if="showFubonOnboardingBanner && activeWorkspacePage !== 'settings'" class="app-notice-banner">
      <div class="app-notice-copy">
        <div class="app-notice-kicker">Setup</div>
        <strong>尚未設定富邦 API 帳號</strong>
        <span>先完成帳號設定後，主畫面才會接上即時行情與帳號分流狀態。</span>
      </div>
      <div class="app-notice-actions">
        <button class="app-notice-link" type="button" @click="handleNavigate('settings')">
          前往設定
        </button>
        <button class="app-notice-dismiss" type="button" @click="dismissFubonOnboardingBanner">
          稍後提醒
        </button>
      </div>
    </section>

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
        :timeframe-options="timeframeOptions"
        :current-ticker="currentTicker"
        :current-name="currentName"
        :current-period="currentPeriod"
        :current-interval="currentInterval"
        :quote="quote"
        :active-tool="activeTool"
        :active-panels="activePanels"
        :kline-display-mode="klineDisplayMode"
        :chart-engine-mode="chartEngineMode"
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
        @set-timeframe="setTimeframe"
        @set-kline-display-mode="setKlineDisplayMode"
        @set-chart-engine-mode="setChartEngineMode"
        @toggle-indicator="toggleIndicator"
        @toggle-panel="togglePanel"
        @apply-indicator-preset="applyIndicatorPreset"
        @set-chart-layout="setChartLayout"
        @clear-indicators="clearIndicators"
        @open-journal-entry="handleTerminalJournalEntry"
      />
    </div>

    <div v-else class="workspace-stage page-stage-shell">
      <MarketOverviewWorkspace
        v-if="activeWorkspacePage === 'overview'"
        ref="marketOverviewRef"
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
        :market-breadth-cards="marketBreadthCards"
        :market-strong-movers="marketStrongMovers"
        :market-weak-movers="marketWeakMovers"
        :market-active-leaders="marketActiveLeaders"
        :market-snapshot-loading="marketSnapshotLoading"
        :market-snapshot-error="marketSnapshotError"
        :calendar-events="calendarEvents"
        :ticker-events="tickerEvents"
        :ticker-news="tickerNews"
        :screener-filters="screenerFilters"
        :screener-results="screenerResults"
        :screener-presets="screenerPresets"
        :screener-loading="screenerLoading"
        @open-terminal="handleOpenTerminal"
        @refresh-macro="loadMacroDashboard(true)"
        @refresh-market-snapshot="loadMarketSnapshots(true)"
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
        :current-ticker="currentTicker"
        :current-name="currentName"
        :taiwan-chip-detail="taiwanChipDetail"
        :taiwan-chip-summary="taiwanChipSummary"
        :taiwan-chip-history="taiwanChipHistory"
        :taiwan-chip-range-days="taiwanChipRangeDays"
        :taiwan-chip-history-loading="taiwanChipHistoryLoading"
        :taiwan-chip-history-error="taiwanChipHistoryError"
        :taifex-structured-query="{
          section: taifexStructuredSection,
          dateMode: taifexStructuredDateMode,
          exactDate: taifexStructuredExactDate,
          startDate: taifexStructuredStartDate,
          endDate: taifexStructuredEndDate,
          commodity: taifexStructuredCommodity,
          institution: taifexStructuredInstitution,
          optionSide: taifexStructuredOptionSide,
          limit: taifexStructuredLimit,
          autoSync: taifexStructuredAutoSync,
        }"
        :taifex-structured-data="taifexStructuredData"
        :taifex-structured-loading="taifexStructuredLoading"
        :taifex-structured-error="taifexStructuredError"
        @open-terminal="handleOpenTerminal(currentTicker)"
        @set-date="setInstitutionalDate"
        @shift-date="shiftInstitutionalDate"
        @refresh-dashboard="loadInstitutionalData(institutionalDate, true)"
        @refresh-insights="loadInstitutionalInsights(institutionalDate, institutionalFuturesCommodity, institutionalOptionsCommodity, institutionalHistoryDays, true)"
        @refresh-chip="loadTickerIntelligence(currentTicker, true)"
        @set-futures-commodity="setInstitutionalFuturesCommodity"
        @set-options-commodity="setInstitutionalOptionsCommodity"
        @set-history-days="setInstitutionalHistoryDays"
        @set-chip-range-days="setTaiwanChipRangeDays"
        @create-alert="openAlertModal($event)"
        @update-taifex-structured-query="updateTaifexStructuredQuery"
        @refresh-taifex-structured="loadTaifexStructuredData"
        @reset-taifex-structured="resetTaifexStructuredQuery"
      />

      <SettingsWorkspace v-else-if="activeWorkspacePage === 'settings'" />

      <AssetWorkspace
        v-else-if="activeWorkspacePage === 'assets'"
        :current-ticker="currentTicker"
        :asset-loading="assetLoading"
        :asset-error="assetError"
        :asset-performance-range="assetPerformanceRange"
        :asset-base-currency="assetBaseCurrency"
        :asset-summary="assetSummary"
        :asset-accounts="assetAccounts"
        :asset-accounts-summary="assetAccountsSummary"
        :asset-holdings="assetHoldings"
        :asset-warnings="assetWarnings"
        :asset-quote-gaps="assetQuoteGaps"
        :asset-reconciliation="assetReconciliation"
        :asset-price-overrides="assetPriceOverrides"
        :asset-fx-rates="assetFxRates"
        :asset-adjustments="assetAdjustments"
        :asset-performance-summary="assetPerformanceSummary"
        :asset-performance-series="assetPerformanceSeries"
        :asset-monthly-heatmap="assetMonthlyHeatmap"
        :asset-realized-vs-unrealized="assetRealizedVsUnrealized"
        :asset-alerts="assetAlerts"
        :asset-trade-import-result="assetTradeImportResult"
        :asset-cash-import-result="assetCashImportResult"
        :asset-journal-import-preview="assetJournalImportPreview"
        :asset-last-recompute="assetLastRecompute"
        :asset-account-allocation="assetAccountAllocation"
        :asset-market-allocation="assetMarketAllocation"
        :asset-contributors="assetContributors"
        :asset-cash-entries="assetCashEntries"
        :asset-trade-entries="assetTradeEntries"
        :asset-reconciliation-entries="assetReconciliationEntries"
        :asset-account-form="assetAccountForm"
        :asset-cash-form="assetCashForm"
        :asset-trade-form="assetTradeForm"
        :asset-reconciliation-form="assetReconciliationForm"
        :asset-price-override-form="assetPriceOverrideForm"
        :asset-fx-rate-form="assetFxRateForm"
        :asset-adjustment-form="assetAdjustmentForm"
        :asset-trade-import-form="assetTradeImportForm"
        :asset-cash-import-form="assetCashImportForm"
        :asset-journal-import-form="assetJournalImportForm"
        @open-terminal="handleOpenTerminal(currentTicker)"
        @reload-asset-data="loadAssetTrackingData({ refresh: true, silent: false })"
        @edit-asset-account="editAssetAccount"
        @update-asset-account-field="handleAssetAccountField"
        @update-asset-cash-field="handleAssetCashField"
        @update-asset-trade-field="handleAssetTradeField"
        @update-asset-reconciliation-field="handleAssetReconciliationField"
        @set-asset-performance-range="setAssetPerformanceRange"
        @update-asset-price-override-field="handleAssetPriceOverrideField"
        @update-asset-fx-rate-field="handleAssetFxRateField"
        @update-asset-adjustment-field="handleAssetAdjustmentField"
        @update-asset-trade-import-field="handleAssetTradeImportField"
        @update-asset-cash-import-field="handleAssetCashImportField"
        @update-asset-journal-import-field="handleAssetJournalImportField"
        @save-asset-account="saveAssetAccount"
        @save-asset-cash-entry="saveAssetCashEntry"
        @save-asset-trade-entry="saveAssetTradeEntry"
        @save-asset-reconciliation="saveAssetReconciliation"
        @save-asset-price-override="saveAssetPriceOverride"
        @save-asset-fx-rate="saveAssetFxRate"
        @save-asset-adjustment="saveAssetAdjustment"
        @import-asset-trades-csv="importAssetTradesCsv($event || {})"
        @import-asset-cash-csv="importAssetCashCsv($event || {})"
        @preview-asset-journal-import="previewAssetJournalImport"
        @import-asset-journal="importAssetJournalEntries"
        @recompute-asset-tracking="recomputeAssetTracking"
        @reset-asset-account-form="resetAssetAccountForm"
        @reset-asset-cash-form="resetAssetCashForm"
        @reset-asset-trade-form="resetAssetTradeForm"
        @reset-asset-reconciliation-form="resetAssetReconciliationForm"
        @reset-asset-price-override-form="resetAssetPriceOverrideForm"
        @reset-asset-fx-rate-form="resetAssetFxRateForm"
        @reset-asset-adjustment-form="resetAssetAdjustmentForm"
        @reset-asset-import-forms="resetAssetImportForms"
        @reset-asset-journal-import-form="resetAssetJournalImportForm"
        @edit-asset-cash-entry="editAssetCashEntry"
        @edit-asset-trade-entry="editAssetTradeEntry"
        @edit-asset-price-override="editAssetPriceOverride"
        @edit-asset-fx-rate="editAssetFxRate"
        @edit-asset-adjustment="editAssetAdjustment"
        @delete-asset-account="deleteAssetAccount"
        @delete-asset-cash-entry="deleteAssetCashEntry"
        @delete-asset-trade-entry="deleteAssetTradeEntry"
        @delete-asset-reconciliation="deleteAssetReconciliation"
        @delete-asset-price-override="deleteAssetPriceOverride"
        @delete-asset-fx-rate="deleteAssetFxRate"
        @delete-asset-adjustment="deleteAssetAdjustment"
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

    <GlobalSearchCommand
      :open="commandPaletteOpen"
      :query="searchQuery"
      :search-results="searchResults"
      :recent-tickers="recentTickers"
      :current-ticker="currentTicker"
      @close="closeCommandPalette"
      @query-change="handleCommandQueryChange"
      @select-symbol="handleCommandSelectSymbol"
      @navigate="handleCommandNavigate"
    />

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
  defineAsyncComponent,
  isRef,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import AppNavbar from "./components/AppNavbar.vue";
import AlertModal from "./components/AlertModal.vue";
import GlobalSearchCommand from "./components/GlobalSearchCommand.vue";
import NotificationPanel from "./components/NotificationPanel.vue";
import StatusBar from "./components/StatusBar.vue";
import ToastStack from "./components/ToastStack.vue";
import { useDashboard } from "./composables/useDashboard";
import { useFubonWorkspaceStatus } from "./composables/useFubonWorkspaceStatus";
import { useHotkeys } from "./composables/useHotkeys";

const SettingsWorkspace = defineAsyncComponent(() => import("./components/settings/SettingsWorkspace.vue"));
const InstitutionalAnalysisWorkspace = defineAsyncComponent(() => import("./components/workspaces/InstitutionalAnalysisWorkspace.vue"));
const MarketOverviewWorkspace = defineAsyncComponent(() => import("./components/workspaces/MarketOverviewWorkspace.vue"));
const ProChartTerminalWorkspace = defineAsyncComponent(() => import("./components/workspaces/ProChartTerminalWorkspace.vue"));
const AssetWorkspace = defineAsyncComponent(() => import("./components/workspaces/AssetWorkspace.vue"));
const ReviewWorkspace = defineAsyncComponent(() => import("./components/workspaces/ReviewWorkspace.vue"));

const props = defineProps({
  routeWorkspaceTab: { type: String, default: "overview" },
  routeRightTab: { type: String, default: "indicators" },
  routeTicker: { type: String, default: "" },
});

const emit = defineEmits(["route-change"]);

const appNavbarRef = ref(null);
const marketOverviewRef = ref(null);
const workspaceStageRef = ref(null);
const chartFullscreen = ref(false);
const pseudoFullscreen = ref(false);
const commandPaletteOpen = ref(false);
const routeStateReady = ref(false);
const applyingRouteState = ref(false);
const activeWorkspacePage = ref("overview");
const terminalLeftCollapsed = ref(true);
const terminalRightCollapsed = ref(true);
const {
  fubonStatus,
  showFubonOnboardingBanner,
  dismissFubonOnboardingBanner,
} = useFubonWorkspaceStatus();

const {
  timeframeOptions,
  klineDisplayOptions,
  searchQuery,
  searchResults,
  searchOpen,
  recentTickers,
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
  chartEngineMode,
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
  taifexStructuredSection,
  taifexStructuredDateMode,
  taifexStructuredExactDate,
  taifexStructuredStartDate,
  taifexStructuredEndDate,
  taifexStructuredCommodity,
  taifexStructuredInstitution,
  taifexStructuredOptionSide,
  taifexStructuredLimit,
  taifexStructuredAutoSync,
  taifexStructuredData,
  taifexStructuredLoading,
  taifexStructuredError,
  taiwanChipDetail,
  taiwanChipSummary,
  taiwanChipHistory,
  taiwanChipRangeDays,
  taiwanChipHistoryLoading,
  taiwanChipHistoryError,
  calendarEvents,
  tickerEvents,
  tickerNews,
  macroDashboard,
  marketBreadthCards,
  marketStrongMovers,
  marketWeakMovers,
  marketActiveLeaders,
  marketSnapshotLoading,
  marketSnapshotError,
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
  assetLoading,
  assetError,
  assetPerformanceRange,
  assetAccounts,
  assetCashEntries,
  assetTradeEntries,
  assetReconciliationEntries,
  assetPriceOverrides,
  assetFxRates,
  assetAdjustments,
  assetPerformance,
  assetAlerts,
  assetTradeImportResult,
  assetCashImportResult,
  assetJournalImportPreview,
  assetLastRecompute,
  assetBaseCurrency,
  assetSummary,
  assetAccountsSummary,
  assetHoldings,
  assetWarnings,
  assetQuoteGaps,
  assetReconciliation,
  assetAccountAllocation,
  assetMarketAllocation,
  assetContributors,
  assetPerformanceSummary,
  assetPerformanceSeries,
  assetMonthlyHeatmap,
  assetRealizedVsUnrealized,
  assetAccountForm,
  assetCashForm,
  assetTradeForm,
  assetReconciliationForm,
  assetPriceOverrideForm,
  assetFxRateForm,
  assetAdjustmentForm,
  assetTradeImportForm,
  assetCashImportForm,
  assetJournalImportForm,
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
  setChartEngineMode,
  toggleIndicator,
  togglePanel,
  applyIndicatorPreset,
  setLeftTab,
  setActiveWatchGroup,
  setRightTab,
  setWorkspaceTab,
  setInstitutionalDate,
  setInstitutionalFuturesCommodity,
  setInstitutionalOptionsCommodity,
  setInstitutionalHistoryDays,
  setTaiwanChipRangeDays,
  shiftInstitutionalDate,
  loadTaifexStructuredData,
  updateTaifexStructuredQuery,
  resetTaifexStructuredQuery,
  loadInstitutionalData,
  loadInstitutionalInsights,
  loadEventCalendar,
  loadMacroDashboard,
  loadMarketSnapshots,
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
  loadAssetTrackingData,
  loadAssetPerformance,
  setAssetPerformanceRange,
  updateAssetAccountField,
  updateAssetCashField,
  updateAssetTradeField,
  updateAssetReconciliationField,
  updateAssetPriceOverrideField,
  updateAssetFxRateField,
  updateAssetAdjustmentField,
  updateAssetTradeImportField,
  updateAssetCashImportField,
  updateAssetJournalImportField,
  editAssetAccount,
  editAssetCashEntry,
  editAssetTradeEntry,
  editAssetPriceOverride,
  editAssetFxRate,
  editAssetAdjustment,
  resetAssetAccountForm,
  resetAssetCashForm,
  resetAssetTradeForm,
  resetAssetReconciliationForm,
  resetAssetPriceOverrideForm,
  resetAssetFxRateForm,
  resetAssetAdjustmentForm,
  resetAssetImportForms,
  resetAssetJournalImportForm,
  saveAssetAccount,
  saveAssetCashEntry,
  saveAssetTradeEntry,
  saveAssetReconciliation,
  saveAssetPriceOverride,
  saveAssetFxRate,
  saveAssetAdjustment,
  deleteAssetAccount,
  deleteAssetCashEntry,
  deleteAssetTradeEntry,
  deleteAssetReconciliation,
  deleteAssetPriceOverride,
  deleteAssetFxRate,
  deleteAssetAdjustment,
  importAssetTradesCsv,
  importAssetCashCsv,
  previewAssetJournalImport,
  importAssetJournalEntries,
  recomputeAssetTracking,
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

function writeStateValue(target, value) {
  if (isRef(target)) {
    target.value = value;
  }
}

const drawerTab = ref("alerts");

function normalizeWorkspacePage(value) {
  const normalized = String(value || "").toLowerCase();
  if (["overview", "terminal", "institutional", "review", "assets", "settings"].includes(normalized)) {
    return normalized;
  }
  if (["macro", "events", "screener", "db"].includes(normalized)) return "overview";
  if (["journal", "backtest", "review"].includes(normalized)) return "review";
  if (normalized === "assets") return "assets";
  if (["dashboard", "alerts", "chart"].includes(normalized)) return "terminal";
  return "overview";
}

function normalizeReviewTab(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "backtest") return "backtest";
  return "journal";
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

  if (page === "settings") {
    if (chartFullscreen.value || pseudoFullscreen.value || document.fullscreenElement) {
      await closeTerminalFullscreenIfNeeded();
    }
    return;
  }

  if (page === "assets") {
    if (chartFullscreen.value || pseudoFullscreen.value || document.fullscreenElement) {
      await closeTerminalFullscreenIfNeeded();
    }
    await setWorkspaceTab("chart");
    await setRightTab("assets");
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
      rightTab: workspacePage === "review" ? nextReviewTab : workspacePage === "assets" ? "assets" : nextDrawerTab,
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
  if (page === "paper-trading") {
    window.location.href = "/paper-trading";
    return;
  }
  const nextPage = normalizeWorkspacePage(page);
  await applyWorkspacePage(nextPage, nextPage === "review" ? reviewTab.value : nextPage === "assets" ? "assets" : drawerTab.value);
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
  if (normalized === "assets") return "assets";
  if (["journal", "backtest", "review"].includes(normalized)) return "review";
  return "terminal";
}

async function handleOpenNotificationWorkspace(workspace) {
  const targetPage = resolveWorkspaceTarget(workspace);
  if (targetPage === "review") {
    const normalized = String(workspace || "").toLowerCase();
    await applyWorkspacePage("review", normalized === "backtest" ? "backtest" : "journal");
    return;
  }
  if (targetPage === "assets") {
    await applyWorkspacePage("assets", "assets");
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

function handleAssetAccountField(payload) {
  if (!payload?.key) return;
  updateAssetAccountField(payload.key, payload.value);
}

function handleAssetCashField(payload) {
  if (!payload?.key) return;
  updateAssetCashField(payload.key, payload.value);
}

function handleAssetTradeField(payload) {
  if (!payload?.key) return;
  updateAssetTradeField(payload.key, payload.value);
}

function handleAssetReconciliationField(payload) {
  if (!payload?.key) return;
  updateAssetReconciliationField(payload.key, payload.value);
}

function handleAssetPriceOverrideField(payload) {
  if (!payload?.key) return;
  updateAssetPriceOverrideField(payload.key, payload.value);
}

function handleAssetFxRateField(payload) {
  if (!payload?.key) return;
  updateAssetFxRateField(payload.key, payload.value);
}

function handleAssetAdjustmentField(payload) {
  if (!payload?.key) return;
  updateAssetAdjustmentField(payload.key, payload.value);
}

function handleAssetTradeImportField(payload) {
  if (!payload?.key) return;
  updateAssetTradeImportField(payload.key, payload.value);
}

function handleAssetCashImportField(payload) {
  if (!payload?.key) return;
  updateAssetCashImportField(payload.key, payload.value);
}

function handleAssetJournalImportField(payload) {
  if (!payload?.key) return;
  updateAssetJournalImportField(payload.key, payload.value);
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

function resetSearchState() {
  writeStateValue(searchQuery, "");
  writeStateValue(searchResults, []);
  writeStateValue(searchOpen, false);
}

function openCommandPalette() {
  commandPaletteOpen.value = true;
}

function closeCommandPalette() {
  commandPaletteOpen.value = false;
  writeStateValue(searchOpen, false);
}

function handleCommandQueryChange(value) {
  const query = String(value || "");
  if (!query.trim()) {
    resetSearchState();
    return;
  }
  void searchSymbols(query);
  writeStateValue(searchOpen, false);
}

async function handleCommandSelectSymbol(payload) {
  closeCommandPalette();
  if (!payload?.ticker) return;
  await openTerminalWithTicker(payload.ticker, payload.name || payload.ticker);
}

async function handleCommandNavigate(page) {
  closeCommandPalette();
  await handleNavigate(page);
}

async function handleOpenHeatmap() {
  await applyWorkspacePage("overview", "indicators");
  await nextTick();
  marketOverviewRef.value?.focusHeatmap?.();
}

function shiftTimeframe(step) {
  const availableTimeframes = readStateValue(timeframeOptions) || [];
  const currentIndex = availableTimeframes.findIndex(
    (option) => option.tf === readStateValue(currentPeriod) && option.iv === readStateValue(currentInterval),
  );
  if (currentIndex < 0) return;
  const nextIndex = Math.max(0, Math.min(availableTimeframes.length - 1, currentIndex + step));
  if (nextIndex === currentIndex) return;
  void setTimeframe(availableTimeframes[nextIndex]);
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
    key: "k",
    ctrlOrMeta: true,
    preventDefault: true,
    handler: () => {
      if (commandPaletteOpen.value) {
        closeCommandPalette();
        return;
      }
      resetSearchState();
      openCommandPalette();
    },
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

.app-notice-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid rgba(123, 231, 255, 0.14);
  background:
    linear-gradient(90deg, rgba(7, 26, 36, 0.96), rgba(11, 20, 31, 0.96)),
    radial-gradient(circle at left, rgba(123, 231, 255, 0.16), transparent 42%);
}

.app-notice-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.app-notice-kicker {
  color: var(--text3);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.app-notice-copy strong {
  color: #f5f7fa;
  font-size: 13px;
}

.app-notice-copy span {
  color: var(--text2);
  font-size: 12px;
  line-height: 1.5;
}

.app-notice-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.app-notice-link,
.app-notice-dismiss {
  min-height: 34px;
  border-radius: 999px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
}

.app-notice-link {
  border-color: rgba(123, 231, 255, 0.26);
  color: #d7fbff;
  background: rgba(123, 231, 255, 0.1);
}

.app-notice-link:hover,
.app-notice-dismiss:hover {
  border-color: rgba(123, 231, 255, 0.34);
  color: #f5f7fa;
}

.workspace-stage {
  flex: 1;
  min-height: 0;
  min-width: 0;
}

.workspace-stage > * {
  flex: 1;
  min-width: 0;
  min-height: 0;
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

@media (max-width: 860px) {
  .app-notice-banner {
    flex-direction: column;
    align-items: flex-start;
  }

  .app-notice-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>
