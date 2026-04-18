import { flushPromises, shallowMount } from "@vue/test-utils";
import { ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

const noop = vi.fn();

const dashboardMock = {
  timeframeOptions: [],
  searchQuery: "",
  searchResults: [],
  searchOpen: false,
  watchlistGroups: [],
  userWatchGroups: [],
  marketWatchItems: [],
  activeWatchGroupId: null,
  workspacePresets: [],
  activeWorkspacePresetId: null,
  compareSeries: [],
  comparisonMode: "percent",
  watchlist: [],
  watchlistLoading: false,
  watchlistError: false,
  leftTab: "watch",
  rightTab: "indicators",
  workspaceTab: "chart",
  currentTicker: "AAPL",
  currentName: "Apple",
  currentPeriod: "1y",
  currentInterval: "1d",
  klineDisplayMode: "day",
  cleanChartMode: false,
  chartLayout: "single",
  chartLoading: false,
  loadingMessage: "",
  ohlcData: [],
  drawings: [],
  selectedDrawingId: null,
  alerts: [],
  notifications: [],
  wsConnected: false,
  latency: "0ms",
  lastUpdate: "—",
  clockTime: "—",
  dbStats: null,
  dbStatsLoading: false,
  dbStatsError: "",
  institutionalDate: "2026-03-29",
  institutionalData: null,
  institutionalLoading: false,
  institutionalError: "",
  institutionalInsights: null,
  institutionalInsightsLoading: false,
  institutionalInsightsError: "",
  institutionalFuturesCommodity: "",
  institutionalOptionsCommodity: "",
  institutionalHistoryDays: 30,
  taifexStructuredSection: "futures",
  taifexStructuredDateMode: "range",
  taifexStructuredExactDate: "2026-03-29",
  taifexStructuredStartDate: "2026-02-27",
  taifexStructuredEndDate: "2026-03-29",
  taifexStructuredCommodity: "",
  taifexStructuredInstitution: "",
  taifexStructuredOptionSide: "",
  taifexStructuredLimit: 300,
  taifexStructuredAutoSync: true,
  taifexStructuredData: { section: "futures", count: 0, filters: {}, items: [] },
  taifexStructuredLoading: false,
  taifexStructuredError: "",
  calendarEvents: [],
  tickerEvents: [],
  tickerNews: [],
  macroDashboard: { items: [], summary: {}, snapshot_date: null },
  fundamentalsSummary: null,
  taiwanChipSummary: null,
  taiwanChipHistory: null,
  taiwanChipRangeDays: 20,
  taiwanChipHistoryLoading: false,
  taiwanChipHistoryError: "",
  screenerFilters: {
    market: "ALL",
    search: "",
    sector: "",
    min_price: "",
    min_volume_ratio: "",
    max_pe_ratio: "",
    min_dividend_yield: "",
    near_52w_high_pct: "",
    upcoming_event_days: "",
    chip_bias: "any",
    ma_alignment: "any",
    sort_by: "score",
    limit: 50,
  },
  screenerResults: { items: [], total: 0, filters: {}, generated_at: null },
  screenerPresets: [],
  screenerLoading: false,
  syncingCurrent: false,
  syncingAll: false,
  quote: {
    price: null,
    open: null,
    high: null,
    low: null,
    volume: null,
    market_cap: null,
    change: 0,
    change_pct: 0,
    name: "Apple",
  },
  marketStatus: {
    nyseOpen: false,
    nasdaqOpen: false,
    tseOpen: false,
    hkOpen: false,
  },
  activeInd: {},
  activePanels: {},
  indicatorSettings: {},
  activeTool: "cursor",
  crosshair: {
    visible: false,
    absoluteIndex: null,
    canvasX: null,
    canvasY: null,
    hoverPrice: "—",
    change: "—",
    changePct: "—",
    date: "—",
    open: "—",
    high: "—",
    low: "—",
    close: "—",
    volume: "—",
  },
  alertModalOpen: false,
  alertForm: {
    ticker: "AAPL",
    type: "price",
    cond: "大於",
    value: "",
  },
  backtestForm: {
    strategy: "MA 黃金/死亡交叉",
    start: "2022-01-01",
    end: "2026-03-29",
    capital: 100000,
    positionSizing: "full_equity",
    fee: 0.1,
    slippage: 0,
    sl: 5,
    tp: 10,
  },
  backtestResult: null,
  backtestHistory: [],
  backtestCompareIds: [],
  backtestCompareRuns: [],
  backtestLoading: false,
  journalForm: {
    id: null,
    ticker: "AAPL",
    market: "US",
    direction: "long",
    strategy_code: "",
    entry_time: "2026-04-01T09:00",
    entry_price: "",
    exit_time: "",
    exit_price: "",
    size: 1,
    stop_loss: "",
    take_profit: "",
    entry_reason: "",
    exit_reason: "",
    emotion_tag: "",
    review_notes: "",
    tags_text: "",
    attachment_path: "",
    attachment_type: "",
    attachments: [],
  },
  journalEntries: [],
  journalStats: null,
  journalLoading: false,
  journalFilterPresets: [],
  journalFilterScope: "ticker",
  journalFilters: {
    market: "",
    strategy_code: "",
    tag: "",
    search: "",
  },
  assetLoading: false,
  assetAccounts: [],
  assetCashEntries: [],
  assetTradeEntries: [],
  assetReconciliationEntries: [],
  assetBaseCurrency: "TWD",
  assetSummary: {},
  assetAccountsSummary: [],
  assetHoldings: [],
  assetWarnings: [],
  assetQuoteGaps: [],
  assetReconciliation: { items: [], summary: {} },
  assetAccountAllocation: [],
  assetMarketAllocation: [],
  assetContributors: { top_gainers: [], top_losers: [] },
  assetAccountForm: {
    id: null,
    name: "",
    institution: "",
    account_type: "brokerage",
    base_currency: "TWD",
    include_in_total: true,
    sort_order: 0,
    notes: "",
  },
  assetCashForm: {
    id: null,
    account_id: "",
    flow_date: "2026-04-18T09:00",
    flow_type: "deposit",
    amount: "",
    currency: "TWD",
    fx_rate_to_base: 1,
    counterparty: "",
    note: "",
  },
  assetTradeForm: {
    id: null,
    account_id: "",
    trade_date: "2026-04-18T09:00",
    ticker: "AAPL",
    display_name: "Apple",
    market: "US",
    asset_type: "stock",
    currency: "USD",
    side: "buy",
    quantity: "",
    price: "",
    fee_amount: 0,
    tax_amount: 0,
    fx_rate_to_base: 32,
    source: "manual",
    note: "",
  },
  assetReconciliationForm: {
    account_id: "",
    snapshot_date: "2026-04-18T09:00",
    cash_actual: "",
    market_value_actual: "",
    note: "",
  },
  indicatorSnapshot: {
    techSummaryHtml: "",
  },
  institutionalOverlay: null,
  backendUrl: "http://127.0.0.1:8001",
  searchSymbols: noop,
  closeSearch: noop,
  submitSearch: noop,
  selectSearchResult: noop,
  createWatchGroup: noop,
  renameWatchGroup: noop,
  deleteWatchGroup: noop,
  addTickerToWatchlist: noop,
  addTickersToWatchlistBatch: noop,
  removeTickerFromWatchlist: noop,
  reorderWatchlistItems: noop,
  addCompareTicker: noop,
  removeCompareTicker: noop,
  clearCompareTickers: noop,
  setComparisonMode: noop,
  setTimeframe: noop,
  setKlineDisplayMode: noop,
  setLeftTab: noop,
  setActiveWatchGroup: noop,
  setRightTab: noop,
  setWorkspaceTab: noop,
  setInstitutionalDate: noop,
  setInstitutionalFuturesCommodity: noop,
  setInstitutionalOptionsCommodity: noop,
  setInstitutionalHistoryDays: noop,
  setTaiwanChipRangeDays: noop,
  shiftInstitutionalDate: noop,
  loadTaifexStructuredData: noop,
  updateTaifexStructuredQuery: noop,
  resetTaifexStructuredQuery: noop,
  loadInstitutionalData: noop,
  loadInstitutionalInsights: noop,
  loadEventCalendar: noop,
  loadMacroDashboard: noop,
  loadTickerIntelligence: noop,
  setChartLayout: noop,
  selectTicker: noop,
  toggleIndicator: noop,
  togglePanel: noop,
  updateIndicatorSetting: noop,
  applyIndicatorPreset: noop,
  clearIndicators: noop,
  setTool: noop,
  addSignal: noop,
  clearDrawings: noop,
  addHorizontalLine: noop,
  addDrawing: noop,
  removeLastDrawing: noop,
  selectDrawing: noop,
  removeDrawing: noop,
  updateDrawing: noop,
  toggleDrawingVisibility: noop,
  toggleDrawingLock: noop,
  saveWorkspacePreset: noop,
  loadWorkspacePreset: noop,
  deleteWorkspacePreset: noop,
  updateCrosshair: noop,
  hideCrosshair: noop,
  focusTickerEvent: noop,
  syncCurrentTicker: noop,
  syncAll: noop,
  dismissNotification: noop,
  setNotificationRead: noop,
  openAlertModal: noop,
  closeAlertModal: noop,
  updateAlertField: noop,
  saveAlert: noop,
  createAlertsBatch: noop,
  deleteAlert: noop,
  updateBacktestField: noop,
  runBacktest: noop,
  selectBacktestRun: noop,
  toggleBacktestCompare: noop,
  clearBacktestCompare: noop,
  updateJournalField: noop,
  updateJournalFilter: noop,
  applyJournalFilterPreset: noop,
  saveJournalFilterPreset: noop,
  loadJournalFilterPreset: noop,
  deleteJournalFilterPreset: noop,
  saveJournalEntry: noop,
  deleteJournalEntry: noop,
  selectJournalEntry: noop,
  resetJournalForm: noop,
  addJournalAttachment: noop,
  removeJournalAttachment: noop,
  startJournalEntry: noop,
  loadAssetTrackingData: noop,
  updateAssetAccountField: noop,
  updateAssetCashField: noop,
  updateAssetTradeField: noop,
  updateAssetReconciliationField: noop,
  editAssetAccount: noop,
  editAssetCashEntry: noop,
  editAssetTradeEntry: noop,
  resetAssetAccountForm: noop,
  resetAssetCashForm: noop,
  resetAssetTradeForm: noop,
  resetAssetReconciliationForm: noop,
  saveAssetAccount: noop,
  saveAssetCashEntry: noop,
  saveAssetTradeEntry: noop,
  saveAssetReconciliation: noop,
  deleteAssetAccount: noop,
  deleteAssetCashEntry: noop,
  deleteAssetTradeEntry: noop,
  deleteAssetReconciliation: noop,
  updateScreenerFilter: noop,
  runScreener: noop,
  saveScreenerPreset: noop,
  loadScreenerPreset: noop,
  deleteScreenerPreset: noop,
};

const fubonWorkspaceStatusMock = {
  fubonStatus: ref("unconfigured"),
  showFubonOnboardingBanner: ref(false),
  dismissFubonOnboardingBanner: noop,
};

vi.mock("./composables/useDashboard", () => ({
  useDashboard: () => dashboardMock,
}));

vi.mock("./composables/useFubonWorkspaceStatus", () => ({
  useFubonWorkspaceStatus: () => fubonWorkspaceStatusMock,
}));

import App from "./App.vue";

describe("App", () => {
  beforeEach(() => {
    fubonWorkspaceStatusMock.fubonStatus.value = "unconfigured";
    fubonWorkspaceStatusMock.showFubonOnboardingBanner.value = false;
    fubonWorkspaceStatusMock.dismissFubonOnboardingBanner = vi.fn();
  });

  it("creates a dedicated watch group from journal result shortcuts", async () => {
    dashboardMock.userWatchGroups = ref([{ id: 1, name: "警報通知模板 命中池" }]);
    dashboardMock.setLeftTab = vi.fn();
    dashboardMock.createWatchGroup = vi.fn().mockImplementation(async (name) => {
      dashboardMock.userWatchGroups.value = [
        ...dashboardMock.userWatchGroups.value,
        { id: 88, name },
      ];
    });
    dashboardMock.addTickersToWatchlistBatch = vi.fn().mockResolvedValue({ added: 2, failed: 0 });

    const wrapper = shallowMount(App, {
      props: {
        routeWorkspaceTab: "review",
        routeRightTab: "journal",
      },
      global: {
        stubs: {
          ReviewWorkspace: {
            name: "ReviewWorkspace",
            template: `
              <button
                data-testid="review-watch-group-trigger"
                @click="$emit('create-watch-group', {
                  name: '警報通知模板 命中池',
                  items: [{ ticker: 'AAPL' }, { ticker: 'MSFT' }],
                })"
              />
            `,
          },
          StatusBar: true,
          ToastStack: true,
          NotificationPanel: true,
          AlertModal: true,
        },
      },
    });

    await flushPromises();
    await wrapper.get('[data-testid="review-watch-group-trigger"]').trigger("click");
    await flushPromises();

    expect(dashboardMock.setLeftTab).toHaveBeenCalledWith("watch");
    expect(dashboardMock.createWatchGroup).toHaveBeenCalledWith("警報通知模板 命中池 (2)");
    expect(dashboardMock.addTickersToWatchlistBatch).toHaveBeenCalledWith(
      [{ ticker: "AAPL" }, { ticker: "MSFT" }],
      88,
    );
  });

  it("routes watchlist batch alerts to the alert helper", async () => {
    dashboardMock.setRightTab = vi.fn();
    dashboardMock.createAlertsBatch = vi.fn().mockResolvedValue({ created: 2, skipped: 0, invalid: 0, failed: 0 });

    const wrapper = shallowMount(App, {
      global: {
        stubs: {
          MarketOverviewWorkspace: {
            name: "MarketOverviewWorkspace",
            template: `
              <button
                data-testid="overview-batch-alerts-trigger"
                @click="$emit('create-alerts-batch', [
                  { ticker: 'AAPL', type: 'price', condition: '大於', value: 210.5 },
                  { ticker: 'MSFT', type: 'price', condition: '大於', value: 410.2 },
                ])"
              />
            `,
          },
          StatusBar: true,
          ToastStack: true,
          NotificationPanel: true,
          AlertModal: true,
        },
      },
    });

    await flushPromises();
    await wrapper.get('[data-testid="overview-batch-alerts-trigger"]').trigger("click");
    await flushPromises();

    expect(dashboardMock.setRightTab).toHaveBeenCalledWith("alerts");
    expect(dashboardMock.createAlertsBatch).toHaveBeenCalledWith([
      { ticker: "AAPL", type: "price", condition: "大於", value: 210.5 },
      { ticker: "MSFT", type: "price", condition: "大於", value: 410.2 },
    ]);
  });
  it("routes watch-group notifications back to the matching watchlist group", async () => {
    dashboardMock.userWatchGroups = ref([
      { id: 7, name: "Journal Flow" },
      { id: 8, name: "Momentum Board" },
    ]);
    dashboardMock.setLeftTab = vi.fn();
    dashboardMock.setActiveWatchGroup = vi.fn();

    const wrapper = shallowMount(App, {
      global: {
        stubs: {
          StatusBar: true,
          ToastStack: true,
          NotificationPanel: {
            name: "NotificationPanel",
            template: `
              <button
                data-testid="notification-watch-group-trigger"
                @click="$emit('open-watch-group', { groupName: 'Journal Flow', ticker: 'AAPL' })"
              />
            `,
          },
          AlertModal: true,
        },
      },
    });

    await flushPromises();
    await wrapper.get('[data-testid="notification-watch-group-trigger"]').trigger("click");
    await flushPromises();

    expect(dashboardMock.setLeftTab).toHaveBeenCalledWith("watch");
    expect(dashboardMock.setActiveWatchGroup).toHaveBeenCalledWith(7);
  });

  it("routes alert-center watch-group shortcuts back to the matching watchlist group", async () => {
    dashboardMock.userWatchGroups = ref([
      { id: 7, name: "Journal Flow" },
      { id: 8, name: "Momentum Board" },
    ]);
    dashboardMock.setLeftTab = vi.fn();
    dashboardMock.setActiveWatchGroup = vi.fn();

    const wrapper = shallowMount(App, {
      props: {
        routeWorkspaceTab: "terminal",
        routeRightTab: "alerts",
      },
      global: {
        stubs: {
          ProChartTerminalWorkspace: {
            name: "ProChartTerminalWorkspace",
            template: `
              <button
                data-testid="terminal-watch-group-trigger"
                @click="$emit('open-watch-group', { groupName: 'Journal Flow', ticker: 'AAPL' })"
              />
            `,
          },
          StatusBar: true,
          ToastStack: true,
          NotificationPanel: true,
          AlertModal: true,
        },
      },
    });

    await flushPromises();
    await wrapper.get('[data-testid="terminal-watch-group-trigger"]').trigger("click");
    await flushPromises();

    expect(dashboardMock.setLeftTab).toHaveBeenCalledWith("watch");
    expect(dashboardMock.setActiveWatchGroup).toHaveBeenCalledWith(7);
  });

  it("shows the onboarding banner when no fubon account is configured", () => {
    fubonWorkspaceStatusMock.showFubonOnboardingBanner.value = true;

    const wrapper = shallowMount(App, {
      props: {
        routeWorkspaceTab: "overview",
        routeRightTab: "indicators",
      },
      global: {
        stubs: {
          AppNavbar: true,
          MarketOverviewWorkspace: true,
          InstitutionalAnalysisWorkspace: true,
          SettingsWorkspace: true,
          ReviewWorkspace: true,
          ProChartTerminalWorkspace: true,
          GlobalSearchCommand: true,
          StatusBar: true,
          ToastStack: true,
          NotificationPanel: true,
          AlertModal: true,
        },
      },
    });

    expect(wrapper.text()).toContain("尚未設定富邦 API 帳號");
    expect(wrapper.text()).toContain("前往設定");
  });

  it("dismisses the onboarding banner from the shell action", async () => {
    fubonWorkspaceStatusMock.showFubonOnboardingBanner.value = true;

    const wrapper = shallowMount(App, {
      props: {
        routeWorkspaceTab: "overview",
        routeRightTab: "indicators",
      },
      global: {
        stubs: {
          AppNavbar: true,
          MarketOverviewWorkspace: true,
          InstitutionalAnalysisWorkspace: true,
          SettingsWorkspace: true,
          ReviewWorkspace: true,
          ProChartTerminalWorkspace: true,
          GlobalSearchCommand: true,
          StatusBar: true,
          ToastStack: true,
          NotificationPanel: true,
          AlertModal: true,
        },
      },
    });

    await wrapper.get(".app-notice-dismiss").trigger("click");

    expect(fubonWorkspaceStatusMock.dismissFubonOnboardingBanner).toHaveBeenCalledTimes(1);
  });
});
