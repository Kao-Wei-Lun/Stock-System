import { computed, isRef, reactive, shallowRef } from "vue";

function unwrap(value) {
  return isRef(value) ? value.value : value;
}

function createForwardingObject(controller, key, fallback) {
  return reactive(new Proxy(fallback, {
    get(target, property) {
      return controller.value?.[key]?.[property] ?? target[property];
    },
    set(target, property, value) {
      if (controller.value?.[key]) {
        controller.value[key][property] = value;
      } else {
        target[property] = value;
      }
      return true;
    },
    ownKeys(target) {
      return Reflect.ownKeys(controller.value?.[key] || target);
    },
    getOwnPropertyDescriptor(target, property) {
      return Object.getOwnPropertyDescriptor(controller.value?.[key] || target, property)
        || { configurable: true, enumerable: true, writable: true, value: undefined };
    },
    has(target, property) {
      return property in (controller.value?.[key] || target);
    },
  }));
}

function createLazyController(options, loadModule, factoryName, { initialize } = {}) {
  const controller = shallowRef(null);
  let loadPromise = null;

  const ensure = async () => {
    if (controller.value) return controller.value;
    if (!loadPromise) {
      loadPromise = loadModule()
        .then((module) => {
          controller.value = module[factoryName](options);
          initialize?.(controller.value);
          return controller.value;
        })
        .catch((error) => {
          loadPromise = null;
          throw error;
        });
    }
    return loadPromise;
  };

  const state = (key, fallback) => computed({
    get: () => {
      const value = unwrap(controller.value?.[key]);
      return value === undefined ? fallback : value;
    },
    set: (value) => {
      const target = controller.value?.[key];
      if (isRef(target)) target.value = value;
    },
  });
  const action = (key) => async (...args) => (await ensure())[key](...args);

  return { controller, ensure, state, action };
}

const DEFAULT_SCREENER_FILTERS = {
  search: "",
  market: "ALL",
  sector: "",
  setup_type: "any",
  min_price: "",
  max_price: "",
  min_volume_ratio: "",
  min_setup_quality: "",
  min_accumulation_score: "",
  decision_verdict: "any",
  max_pe_ratio: "",
  min_dividend_yield: "",
  near_52w_high_pct: "",
  upcoming_event_days: "",
  chip_bias: "any",
  ma_alignment: "any",
  sort_by: "score",
  limit: 50,
};

export function createLazyDashboardScreener(
  options,
  loadModule = () => import("./dashboardScreener"),
) {
  const lazy = createLazyController(options, loadModule, "createDashboardScreener");
  const facade = {
    screenerResults: lazy.state(
      "screenerResults",
      { items: [], total: 0, filters: {}, market_context: null, generated_at: null },
    ),
    screenerPresets: lazy.state("screenerPresets", []),
    screenerLoading: lazy.state("screenerLoading", false),
    screenerFilters: createForwardingObject(
      lazy.controller,
      "screenerFilters",
      { ...DEFAULT_SCREENER_FILTERS, ...(options?.storedPrefs?.screenerFilters || {}) },
    ),
  };
  for (const key of [
    "applyScreenerFilters",
    "updateScreenerFilter",
    "loadScreenerPresets",
    "runScreener",
    "saveScreenerPreset",
    "loadScreenerPreset",
    "deleteScreenerPreset",
  ]) {
    facade[key] = lazy.action(key);
  }
  return facade;
}

const DEFAULT_BACKTEST_FORM = {
  strategy: "MA 黃金/死亡交叉",
  start: "2022-01-01",
  end: new Date().toISOString().slice(0, 10),
  capital: 100000,
  positionSizing: "full_equity",
  fee: 0.1,
  slippage: 0,
  sl: 5,
  tp: 10,
};

const DEFAULT_JOURNAL_FORM = {
  id: null,
  ticker: "",
  market: "",
  direction: "long",
  strategy_code: "",
  entry_time: "",
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
};

export function createLazyDashboardTradeWorkbench(
  options,
  loadModule = () => import("./dashboardTradeWorkbench"),
) {
  const lazy = createLazyController(options, loadModule, "createDashboardTradeWorkbench", {
    initialize: (controller) => controller.resetJournalForm(),
  });
  const facade = {
    backtestForm: createForwardingObject(lazy.controller, "backtestForm", { ...DEFAULT_BACKTEST_FORM }),
    backtestResult: lazy.state("backtestResult", null),
    backtestHistory: lazy.state("backtestHistory", []),
    backtestCompareIds: lazy.state("backtestCompareIds", []),
    backtestCompareRuns: lazy.state("backtestCompareRuns", []),
    backtestLoading: lazy.state("backtestLoading", false),
    journalForm: createForwardingObject(lazy.controller, "journalForm", { ...DEFAULT_JOURNAL_FORM }),
    journalEntries: lazy.state("journalEntries", []),
    journalStats: lazy.state("journalStats", null),
    journalLoading: lazy.state("journalLoading", false),
    journalFilterPresets: lazy.state("journalFilterPresets", []),
    journalFilterScope: lazy.state("journalFilterScope", "ticker"),
    journalFilters: createForwardingObject(
      lazy.controller,
      "journalFilters",
      { market: "", strategy_code: "", tag: "", search: "" },
    ),
  };
  for (const key of [
    "loadBacktestHistory",
    "selectBacktestRun",
    "toggleBacktestCompare",
    "clearBacktestCompare",
    "loadJournalData",
    "loadJournalFilterPresets",
    "updateJournalField",
    "updateJournalFilter",
    "applyJournalFilterPreset",
    "saveJournalFilterPreset",
    "loadJournalFilterPreset",
    "deleteJournalFilterPreset",
    "resetJournalForm",
    "addJournalAttachment",
    "removeJournalAttachment",
    "startJournalEntry",
    "selectJournalEntry",
    "saveJournalEntry",
    "deleteJournalEntry",
    "updateBacktestField",
    "runBacktest",
  ]) {
    facade[key] = lazy.action(key);
  }
  return facade;
}

export function createLazyDashboardMarketIntel(
  options,
  loadModule = () => import("./dashboardMarketIntel"),
) {
  const lazy = createLazyController(options, loadModule, "createDashboardMarketIntel");
  const today = new Date().toISOString().slice(0, 10);
  const defaults = {
    calendarEvents: [],
    tickerEvents: [],
    tickerNews: [],
    macroDashboard: { items: [], summary: {}, snapshot_date: null },
    fundamentalsDetail: null,
    fundamentalsSummary: null,
    taiwanChipDetail: null,
    taiwanChipSummary: null,
    taiwanChipHistory: null,
    taiwanChipRangeDays: Number(options?.storedPrefs?.taiwanChipRangeDays) || 20,
    taiwanChipHistoryLoading: false,
    taiwanChipHistoryError: "",
    institutionalDate: today,
    institutionalData: null,
    institutionalLoading: false,
    institutionalError: "",
    institutionalInsights: null,
    institutionalInsightsLoading: false,
    institutionalInsightsError: "",
    institutionalFuturesCommodity: options?.storedPrefs?.institutionalFuturesCommodity || "",
    institutionalOptionsCommodity: options?.storedPrefs?.institutionalOptionsCommodity || "",
    institutionalHistoryDays: Number(options?.storedPrefs?.institutionalHistoryDays) || 30,
    taifexStructuredSection: "futures",
    taifexStructuredDateMode: "range",
    taifexStructuredExactDate: "",
    taifexStructuredStartDate: "",
    taifexStructuredEndDate: "",
    taifexStructuredCommodity: "",
    taifexStructuredInstitution: "",
    taifexStructuredOptionSide: "",
    taifexStructuredLimit: 300,
    taifexStructuredAutoSync: true,
    taifexStructuredData: { section: "futures", count: 0, filters: {}, items: [] },
    taifexStructuredLoading: false,
    taifexStructuredError: "",
    institutionalOverlay: null,
  };
  const facade = {};
  for (const [key, fallback] of Object.entries(defaults)) {
    facade[key] = lazy.state(key, fallback);
  }
  for (const key of [
    "loadEventCalendar",
    "loadMacroDashboard",
    "loadTickerIntelligence",
    "loadTaiwanChipHistory",
    "loadInstitutionalData",
    "loadInstitutionalInsights",
    "loadTaifexStructuredData",
    "ensureInstitutionalOverlayForTicker",
    "setInstitutionalDate",
    "setInstitutionalFuturesCommodity",
    "setInstitutionalOptionsCommodity",
    "setInstitutionalHistoryDays",
    "setTaiwanChipRangeDays",
    "shiftInstitutionalDate",
    "updateTaifexStructuredQuery",
    "resetTaifexStructuredQuery",
  ]) {
    facade[key] = lazy.action(key);
  }
  return facade;
}

export function createLazyDashboardAlerting(
  options,
  loadModule = () => import("./dashboardAlerting"),
) {
  const lazy = createLazyController(options, loadModule, "createDashboardAlerting");
  const facade = {
    alerts: lazy.state("alerts", []),
    alertTriggerLogs: lazy.state("alertTriggerLogs", {}),
    alertLogLoading: lazy.state("alertLogLoading", {}),
    expandedAlertLogId: lazy.state("expandedAlertLogId", null),
    alertModalOpen: lazy.state("alertModalOpen", false),
    alertForm: createForwardingObject(lazy.controller, "alertForm", {
      ticker: "",
      type: "price",
      cond: "大於",
      value: "",
      metric: "",
      futures_commodity: "",
      options_commodity: "",
      event_type: "",
      event_title: "",
      importance: "",
      event_scope: "",
      target_label: "",
      prefill_hint: "",
      context_tags: [],
      context_source: "",
      context_group_name: "",
      snapshot_price: null,
      snapshot_source: "",
      snapshot_timestamp: "",
    }),
  };
  for (const key of [
    "loadAlerts",
    "openAlertModal",
    "closeAlertModal",
    "updateAlertField",
    "saveAlert",
    "createAlertsBatch",
    "toggleAlertLog",
    "toggleAlertActive",
    "deleteAlert",
  ]) {
    facade[key] = lazy.action(key);
  }
  return facade;
}

export function createLazyDashboardMarketSnapshots(
  options,
  loadModule = () => import("./dashboardMarketSnapshots"),
) {
  const lazy = createLazyController(options, loadModule, "createDashboardMarketSnapshots");
  const facade = {
    marketSnapshots: lazy.state("marketSnapshots", []),
    marketStrongMovers: lazy.state("marketStrongMovers", []),
    marketWeakMovers: lazy.state("marketWeakMovers", []),
    marketActiveLeaders: lazy.state("marketActiveLeaders", []),
    marketSnapshotLoading: lazy.state("marketSnapshotLoading", false),
    marketSnapshotError: lazy.state("marketSnapshotError", ""),
    marketBreadthCards: lazy.state("marketBreadthCards", []),
    loadMarketSnapshots: lazy.action("loadMarketSnapshots"),
  };
  return facade;
}
