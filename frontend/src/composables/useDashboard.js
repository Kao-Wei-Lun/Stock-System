import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowReactive, watch } from "vue";

import {
  DEFAULT_INDICATOR_SETTINGS,
  buildIndicatorSnapshot,
  normalizeIndicatorSettings,
} from "../utils/indicatorUtils";
import { createDashboardApi } from "../api/dashboardApi";
import { createTerminalCache } from "../services/terminalCache";
import { fetchWithPolicy } from "../utils/requestPolicy";
import { fmtMktCap, fmtPrice, fmtVol } from "../utils/formatters";
import { upsertRealtimeOhlcFromCandle, upsertRealtimeOhlcFromQuote } from "../utils/realtimeOhlc";
import { mergeBookLevels, mergeRealtimeQuote } from "../utils/realtimeQuote";
import { DEFAULT_OHLC_BUFFER_LIMIT, mergeOhlcBuffer } from "../utils/ohlcBuffer";
import { createVisibilityPoller } from "../utils/visibilityPoller";
import {
  FUTOPT_REST_POLL_MS,
  TIMEFRAME_OPTIONS,
  getTimeframeOptionsForTicker,
  inferMarketFromTicker,
  isFutoptTicker,
  isIntradayInterval,
  normalizeTicker,
  resolveDashboardTimeframeForTicker,
  resolveFutoptInterval,
  resolveFutoptPeriod,
  resolveTimeframeInterval,
  shouldPollFutoptRestFallback,
} from "../utils/marketSymbols";
import { filterRenderableOhlcRows, isRenderableOhlcRow } from "../utils/chartOhlc";
import { markQuantVisionPerformance, QV_PERFORMANCE_MARKS } from "../utils/performanceMarks";
import { createRealtimeUiBatcher } from "../utils/realtimeUiBatcher";
import { createDashboardBootstrap } from "./dashboard/dashboardBootstrap";
import { createDashboardComparison } from "./dashboard/dashboardComparison";
import { createDashboardMarketSync } from "./dashboard/dashboardMarketSync";
import { createDashboardNotifications } from "./dashboard/dashboardNotifications";
import { createLazyDashboardAssetTracking } from "./dashboard/lazyDashboardAssetTracking";
import { createDashboardRealtime } from "./dashboard/dashboardRealtime";
import { createDashboardRouteControllers } from "./dashboard/dashboardRouteControllers";
import { createDashboardTerminalState } from "./dashboard/dashboardTerminalState";
import { createLazyDashboardWorkspacePersistence } from "./dashboard/lazyDashboardWorkspacePersistence";
import {
  createLazyDashboardAlerting,
  createLazyDashboardScreener,
  createLazyDashboardMarketIntel,
  createLazyDashboardMarketSnapshots,
  createLazyDashboardTradeWorkbench,
} from "./dashboard/lazyDashboardSecondaryControllers";

const KLINE_DISPLAY_OPTIONS = [
  { key: "day", label: "日K" },
  { key: "week", label: "週K" },
  { key: "month", label: "月K" },
  { key: "quarter", label: "季K" },
];

const DASHBOARD_PREFS_KEY = "quantvision.dashboard.prefs.v1";
const RECENT_TICKERS_KEY = "quantvision.recent.tickers.v1";
const RECENT_TICKERS_LIMIT = 10;
const INITIAL_OHLC_REQUEST_LIMIT = 400;
const INITIAL_OHLC_WARMUP_BARS = 250;
const FUTOPT_HISTORY_BUFFER_LIMIT = 5000;
const CHART_LAYOUT_OPTIONS = ["single", "double", "quad"];
const DASHBOARD_RIGHT_TAB_OPTIONS = ["indicators", "alerts", "assets", "backtest", "journal"];
const MARKET_GROUP_NAME = "全球大盤";
const REALTIME_UI_BATCHING_ENABLED = String(
  import.meta.env.VITE_REALTIME_BATCHING_ENABLED ?? "true",
).toLowerCase() !== "false";
export const WATCHLIST_COLOR_OPTIONS = [
  "#7be7ff",
  "#00d9a3",
  "#ffd166",
  "#ff8c42",
  "#9b6dff",
  "#ff4d6a",
];
const WORKSPACE_TAB_OPTIONS = ["chart", "institutional", "events", "macro", "screener"];
const DEFAULT_ACTIVE_IND = {
  cycleMa: true,
  ma20: true,
  ma50: true,
  ma200: false,
  ema12: true,
  bb: false,
  psar: false,
  keltner: false,
  donchian: false,
  vwap: false,
  ichimoku: false,
  supertrend: false,
};
const DEFAULT_ACTIVE_PANELS = {
  rsi: true,
  aroon: false,
  trix: false,
  williamsr: false,
  mfi: false,
  roc: false,
  bbPercent: false,
  bbWidth: false,
  macd: true,
  stoch: true,
  atr: false,
  cci: false,
  obv: false,
  adx: false,
  cmf: false,
};
const TOOL_OPTIONS = ["cursor", "hline", "vline", "tline", "arrow", "fib", "rect", "measure", "note", "boxzoom"];
const EXCHANGE_SCHEDULES = {
  nyse: { timeZone: "America/New_York", sessions: [[9 * 60 + 30, 16 * 60]] },
  nasdaq: { timeZone: "America/New_York", sessions: [[9 * 60 + 30, 16 * 60]] },
  tse: { timeZone: "Asia/Taipei", sessions: [[9 * 60, 13 * 60 + 30]] },
  hkex: { timeZone: "Asia/Hong_Kong", sessions: [[9 * 60 + 30, 12 * 60], [13 * 60, 16 * 60]] },
};
let drawingIdSeed = 1;

export function normalizeDashboardRightTab(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return DASHBOARD_RIGHT_TAB_OPTIONS.includes(normalized) ? normalized : "indicators";
}

function isBrowser() {
  return typeof window !== "undefined";
}

function readDashboardPrefs() {
  if (!isBrowser()) return {};
  try {
    return JSON.parse(window.localStorage.getItem(DASHBOARD_PREFS_KEY) || "{}");
  } catch (error) {
    return {};
  }
}

function writeDashboardPrefs(value) {
  if (!isBrowser()) return;
  window.localStorage.setItem(DASHBOARD_PREFS_KEY, JSON.stringify(value));
}

function readRecentTickers() {
  if (!isBrowser()) return [];
  try {
    const value = JSON.parse(window.localStorage.getItem(RECENT_TICKERS_KEY) || "[]");
    return Array.isArray(value) ? value.filter(Boolean) : [];
  } catch (error) {
    return [];
  }
}

function writeRecentTickers(items) {
  if (!isBrowser()) return;
  window.localStorage.setItem(RECENT_TICKERS_KEY, JSON.stringify(items));
}

function getDrawingDefaults(type) {
  const defaults = {
    color: "#00d4ff",
    lineWidth: 1.5,
    lineStyle: "solid",
    label: "",
    fillOpacity: 0.12,
    text: "註記",
  };

  const byType = {
    buy: { color: "#00d9a3", lineWidth: 2 },
    sell: { color: "#ff4d6a", lineWidth: 2 },
    hline: { color: "#f5a623", lineWidth: 1.2, lineStyle: "dash" },
    vline: { color: "#ff8c42", lineWidth: 1.2, lineStyle: "dash" },
    trendline: { color: "#00d4ff", lineWidth: 1.5 },
    arrow: { color: "#7be7ff", lineWidth: 1.6 },
    fib: { color: "#ffd166", lineWidth: 1.2, lineStyle: "dash" },
    rect: { color: "#9b6dff", lineWidth: 1.2, lineStyle: "dash", fillOpacity: 0.12 },
    measure: { color: "#00d4ff", lineWidth: 1.1, lineStyle: "dash" },
    note: { color: "#ffd166", lineWidth: 1, lineStyle: "solid", fillOpacity: 0.88, text: "註記" },
  };

  return { ...defaults, ...(byType[type] || {}) };
}
function createDrawingEntry(drawing) {
  const defaults = getDrawingDefaults(drawing.type);
  return {
    ...defaults,
    ...drawing,
    id: drawing.id || `drawing-${Date.now()}-${drawingIdSeed++}`,
    hidden: Boolean(drawing.hidden),
    locked: Boolean(drawing.locked),
  };
}

function getBackendTarget() {
  return (import.meta.env.VITE_BACKEND_TARGET || "http://127.0.0.1:8001").replace(/\/$/, "");
}

function getApiBase() {
  if (import.meta.env.DEV) {
    return "";
  }
  return window.location.origin;
}

function getWsBase() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  if (import.meta.env.DEV) {
    return `${protocol}//${window.location.host}`;
  }
  return `${protocol}//${window.location.host}`;
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function normalizeKlineDisplayMode(mode) {
  return ["day", "week", "month", "quarter"].includes(mode) ? mode : "day";
}

function normalizeChartEngineMode(mode) {
  return mode === "lwc" ? "lwc" : "legacy";
}

function parseChartDate(value) {
  if (!value) return null;
  const normalized = typeof value === "string" && value.includes(" ") ? value.replace(" ", "T") : value;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatQuoteTimestampLabel(value) {
  const parsed = parseChartDate(value);
  if (!parsed) return "—";
  return parsed.toLocaleString("zh-TW", { hour12: false });
}

function sameWorkspaceId(left, right) {
  if (left == null || right == null) return false;
  return String(left) === String(right);
}

function formatDateOnly(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getWeekStart(date) {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  const weekday = (result.getDay() + 6) % 7;
  result.setDate(result.getDate() - weekday);
  return result;
}

function getBucketStart(date, mode) {
  if (mode === "week") return getWeekStart(date);
  if (mode === "month") return new Date(date.getFullYear(), date.getMonth(), 1);
  if (mode === "quarter") return new Date(date.getFullYear(), Math.floor(date.getMonth() / 3) * 3, 1);
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function getPeriodStartDate(period) {
  if (!period || period === "max") return null;
  const base = new Date();
  base.setHours(0, 0, 0, 0);

  const directMap = {
    "5d": () => base.setDate(base.getDate() - 5),
    "1mo": () => base.setMonth(base.getMonth() - 1),
    "3mo": () => base.setMonth(base.getMonth() - 3),
    "6mo": () => base.setMonth(base.getMonth() - 6),
    "1y": () => base.setFullYear(base.getFullYear() - 1),
    "2y": () => base.setFullYear(base.getFullYear() - 2),
    "5y": () => base.setFullYear(base.getFullYear() - 5),
    "10y": () => base.setFullYear(base.getFullYear() - 10),
  };

  if (directMap[period]) {
    directMap[period]();
    return base;
  }

  const match = String(period).match(/^(\d+)(d|mo|y)$/);
  if (!match) return null;
  const amount = Number(match[1]);
  const unit = match[2];
  if (unit === "d") base.setDate(base.getDate() - amount);
  if (unit === "mo") base.setMonth(base.getMonth() - amount);
  if (unit === "y") base.setFullYear(base.getFullYear() - amount);
  return base;
}

function getExpandedFetchPeriod(period, mode) {
  if (mode === "day" || period === "max") return period;

  const weekMap = {
    "5d": "1mo",
    "1mo": "3mo",
    "3mo": "6mo",
    "6mo": "1y",
    "1y": "2y",
    "2y": "5y",
    "5y": "10y",
    "10y": "max",
  };
  const monthMap = {
    "5d": "3mo",
    "1mo": "6mo",
    "3mo": "1y",
    "6mo": "2y",
    "1y": "2y",
    "2y": "5y",
    "5y": "10y",
    "10y": "max",
  };
  const quarterMap = {
    "5d": "1y",
    "1mo": "1y",
    "3mo": "2y",
    "6mo": "2y",
    "1y": "5y",
    "2y": "10y",
    "5y": "max",
    "10y": "max",
  };

  const mapByMode = {
    week: weekMap,
    month: monthMap,
    quarter: quarterMap,
  };

  return mapByMode[mode]?.[period] || "max";
}

function getEffectiveKlineDisplayMode(mode, interval) {
  return isIntradayInterval(interval) ? "day" : normalizeKlineDisplayMode(mode);
}

function resolveOhlcDisplayPeriod(ticker, period, interval) {
  // Futures intraday APIs use period to bound the upstream repair request,
  // while the returned rows are already bounded by limit. Reapplying the
  // calendar period in the browser would hide Friday bars on Monday.
  if (isFutoptTicker(ticker) && isIntradayInterval(interval)) return "max";
  return period;
}

function resolveOhlcBufferLimit(ticker, interval) {
  // A TXF/TMF session contains both regular and after-hours minutes, so the
  // generic 500-row terminal buffer can cover less than one trading day.
  return isFutoptTicker(ticker) && isIntradayInterval(interval)
    ? FUTOPT_HISTORY_BUFFER_LIMIT
    : DEFAULT_OHLC_BUFFER_LIMIT;
}

function filterRowsForDisplayPeriod(rows, period, mode) {
  if (!Array.isArray(rows) || !rows.length || !period || period === "max") return Array.isArray(rows) ? rows : [];
  const since = getPeriodStartDate(period);
  if (!since) return rows;
  const boundary = mode === "day" ? since : getBucketStart(since, mode);
  const boundaryTime = boundary.getTime();
  return rows.filter((row) => {
    const date = parseChartDate(row.date);
    if (!date) return false;
    const current = mode === "day" ? date : getBucketStart(date, mode);
    return current.getTime() >= boundaryTime;
  });
}

function aggregateOhlcRows(rows, mode) {
  if (!Array.isArray(rows) || !rows.length || mode === "day") return Array.isArray(rows) ? rows : [];

  const buckets = [];
  let current = null;

  rows.forEach((row) => {
    if (!isRenderableOhlcRow(row)) return;
    const date = parseChartDate(row.date);
    if (!date) return;
    const bucketStart = getBucketStart(date, mode);
    const bucketKey = formatDateOnly(bucketStart);

    if (!current || current.bucketKey !== bucketKey) {
      current = {
        bucketKey,
        date: bucketKey,
        open: Number(row.open ?? row.close ?? 0),
        high: Number(row.high ?? row.close ?? 0),
        low: Number(row.low ?? row.close ?? 0),
        close: Number(row.close ?? row.open ?? 0),
        volume: Number(row.volume ?? 0),
        adj_close: Number(row.adj_close ?? row.close ?? row.open ?? 0),
      };
      buckets.push(current);
      return;
    }

    current.high = Math.max(current.high, Number(row.high ?? row.close ?? current.high));
    current.low = Math.min(current.low, Number(row.low ?? row.close ?? current.low));
    current.close = Number(row.close ?? current.close);
    current.adj_close = Number(row.adj_close ?? row.close ?? current.adj_close);
    current.volume += Number(row.volume ?? 0);
  });

  return buckets;
}

export {
  getTimeframeOptionsForTicker,
  normalizeTicker,
  resolveOhlcBufferLimit,
  resolveOhlcDisplayPeriod,
  resolveDashboardTimeframeForTicker,
  shouldPollFutoptRestFallback,
};

function getCurrentDateTimeInputValue() {
  const now = new Date();
  const timezoneOffset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - timezoneOffset).toISOString().slice(0, 16);
}

function resolveSearchInputTicker(rawInput, searchResults) {
  const raw = (rawInput || "").trim().toUpperCase();
  if (!raw) return null;
  const exact = searchResults.find((item) => item?.ticker?.toUpperCase() === raw);
  if (exact) return exact;
  const byStockCode = searchResults.find((item) => item?.ticker?.toUpperCase().startsWith(`${raw}.`));
  return byStockCode || searchResults[0] || null;
}

function getExchangeClockParts(date, timeZone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const parsed = {};
  parts.forEach((part) => {
    if (part.type !== "literal") {
      parsed[part.type] = part.value;
    }
  });
  const weekdayMap = {
    Sun: 0,
    Mon: 1,
    Tue: 2,
    Wed: 3,
    Thu: 4,
    Fri: 5,
    Sat: 6,
  };
  return {
    weekday: weekdayMap[parsed.weekday] ?? 0,
    minutesOfDay: Number(parsed.hour || 0) * 60 + Number(parsed.minute || 0),
  };
}

function isExchangeOpen(date, schedule) {
  const { weekday, minutesOfDay } = getExchangeClockParts(date, schedule.timeZone);
  if (weekday < 1 || weekday > 5) return false;
  return schedule.sessions.some(([start, end]) => minutesOfDay >= start && minutesOfDay < end);
}

export function useDashboard({ initialWorkspacePage = "overview", initialTicker: routeTicker = "", initialRightTab = "indicators" } = {}) {
  const apiBase = getApiBase();
  const wsUrl = `${getWsBase()}/ws`;
  const backendUrl = import.meta.env.DEV ? getBackendTarget() : window.location.origin;
  const dashboardApi = createDashboardApi({ baseUrl: apiBase });
  const terminalCache = createTerminalCache();
  const storedPrefs = readDashboardPrefs();
  const initialTicker = normalizeTicker(routeTicker || storedPrefs.currentTicker || "AAPL");
  const storedTimeframe = TIMEFRAME_OPTIONS.find(
    (option) => option.tf === storedPrefs.currentPeriod && option.iv === storedPrefs.currentInterval,
  );
  const initialTool = TOOL_OPTIONS.includes(storedPrefs.activeTool) ? storedPrefs.activeTool : "cursor";
  const initialComparisonMode = storedPrefs.comparisonMode === "price" ? "price" : "percent";
  const initialChartLayout = CHART_LAYOUT_OPTIONS.includes(storedPrefs.chartLayout) ? storedPrefs.chartLayout : "single";
  const initialKlineDisplayMode = normalizeKlineDisplayMode(storedPrefs.klineDisplayMode);
  const initialChartEngineMode = normalizeChartEngineMode(storedPrefs.chartEngineMode);
  const initialWorkspaceTab = WORKSPACE_TAB_OPTIONS.includes(storedPrefs.workspaceTab) ? storedPrefs.workspaceTab : "chart";
  const initialResolvedTimeframe = resolveDashboardTimeframeForTicker(
    initialTicker,
    storedPrefs.currentPeriod || storedTimeframe?.tf || "1y",
    storedPrefs.currentInterval || storedTimeframe?.iv || "1d",
  );
  const initialPeriod = initialResolvedTimeframe.period;
  const initialInterval = initialResolvedTimeframe.interval;
  const activeBootstrapPage = ref(String(initialWorkspacePage || "overview").toLowerCase());
  const dashboardBootstrap = createDashboardBootstrap();
  const {
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
    futoptRefreshStatus,
    futoptDataStale,
    rawOhlcData,
    klineDataOrigin,
    klineCacheSavedAt,
    drawings,
    selectedDrawingId,
    syncingCurrent,
    syncingAll,
  } = createDashboardTerminalState({
    ticker: initialTicker,
    period: initialPeriod,
    interval: initialInterval,
    klineDisplayMode: getEffectiveKlineDisplayMode(initialKlineDisplayMode, initialInterval),
    chartEngineMode: initialChartEngineMode,
    cleanChartMode: storedPrefs.cleanChartMode,
    chartLayout: initialChartLayout,
  });

  const klineDisplayOptions = KLINE_DISPLAY_OPTIONS;
  const searchQuery = ref("");
  const searchResults = ref([]);
  const searchOpen = ref(false);
  const recentTickers = ref(readRecentTickers());
  const watchlistGroups = ref([]);
  const userWatchGroups = computed(() =>
    watchlistGroups.value.filter((group) => group.name !== MARKET_GROUP_NAME),
  );
  const marketWatchGroup = computed(() =>
    watchlistGroups.value.find((group) => group.name === MARKET_GROUP_NAME) || null,
  );
  const marketWatchItems = computed(() => marketWatchGroup.value?.items || []);
  const activeWatchGroupId = ref(Number.isFinite(storedPrefs.activeWatchGroupId) ? storedPrefs.activeWatchGroupId : null);
  const compareTickers = ref(
    Array.isArray(storedPrefs.compareTickers)
      ? storedPrefs.compareTickers.map((ticker) => normalizeTicker(ticker)).filter(Boolean)
      : [],
  );
  const rawCompareSeries = ref([]);
  const comparisonMode = ref(initialComparisonMode);
  const watchlist = computed(() =>
    watchlistGroups.value.flatMap((group) =>
      (group.items || []).map((item) => ({
        ...item,
        group_id: item.group_id ?? group.id,
        group_name: item.group_name ?? group.name,
        group_color: item.group_color ?? group.color ?? null,
      })),
    ),
  );
  const watchlistLoading = ref(true);
  const watchlistError = ref(false);
  const compareSeries = computed(() =>
    rawCompareSeries.value
      .map((series) => {
        const displayMode = getEffectiveKlineDisplayMode(klineDisplayMode.value, currentInterval.value);
        const data = filterRowsForDisplayPeriod(
          aggregateOhlcRows(series.data || [], displayMode),
          resolveOhlcDisplayPeriod(
            series.ticker,
            currentPeriod.value,
            currentInterval.value,
          ),
          displayMode,
        );
        const firstClose = data.find((row) => row.close != null)?.close ?? null;
        const lastClose = data.length ? data[data.length - 1].close : null;
        const changePct = firstClose && lastClose ? ((lastClose - firstClose) / firstClose) * 100 : 0;
        return {
          ...series,
          data,
          changePct,
        };
      })
      .filter((series) => (series.data || []).length),
  );
  const leftTab = ref(storedPrefs.leftTab === "market" ? "market" : "watch");
  const rightTab = ref(normalizeDashboardRightTab(storedPrefs.rightTab));
  const workspaceTab = ref(initialWorkspaceTab);
  const timeframeOptions = computed(() => getTimeframeOptionsForTicker(currentTicker.value));
  const workspacePresets = ref([]);
  const activeWorkspacePresetId = ref(storedPrefs.activeWorkspacePresetId || null);
  const localNotifications = ref([]);
  const remoteNotifications = ref([]);
  const notifications = computed(() =>
    [...localNotifications.value, ...remoteNotifications.value].sort((left, right) => {
      const leftTime = Date.parse(left?.createdAt || "") || 0;
      const rightTime = Date.parse(right?.createdAt || "") || 0;
      return rightTime - leftTime;
    }),
  );
  const {
    dismissNotification,
    loadNotifications,
    pushNotification,
    setNotificationRead,
  } = createDashboardNotifications({
    dashboardApi,
    localNotifications,
    remoteNotifications,
    formatTimestamp: formatQuoteTimestampLabel,
  });
  const latency = ref("—");
  const lastUpdate = ref("—");
  const clockTime = ref("—");
  const activeTool = ref(initialTool);
  const realtimeUiBatcher = createRealtimeUiBatcher({
    enabled: REALTIME_UI_BATCHING_ENABLED,
    getActiveTicker: () => currentTicker.value,
    onQuote: handleRealtimeQuote,
    onBooks: handleRealtimeBook,
    onCandle: handleRealtimeCandle,
  });
  const dashboardRealtime = createDashboardRealtime({
    wsUrl,
    onMessage: realtimeUiBatcher.push,
  });
  const wsConnected = dashboardRealtime.wsConnected;
  const {
    calendarEvents,
    tickerEvents,
    tickerNews,
    macroDashboard,
    fundamentalsDetail,
    fundamentalsSummary,
    taiwanChipDetail,
    taiwanChipSummary,
    taiwanChipHistory,
    taiwanChipRangeDays,
    taiwanChipHistoryLoading,
    taiwanChipHistoryError,
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
    institutionalOverlay,
    loadEventCalendar: loadEventCalendarAction,
    loadMacroDashboard: loadMacroDashboardAction,
    loadTickerIntelligence: loadTickerIntelligenceAction,
    loadTaiwanChipHistory: loadTaiwanChipHistoryAction,
    loadInstitutionalData: loadInstitutionalDataAction,
    loadInstitutionalInsights: loadInstitutionalInsightsAction,
    loadTaifexStructuredData: loadTaifexStructuredDataAction,
    ensureInstitutionalOverlayForTicker: ensureInstitutionalOverlayForTickerAction,
    setInstitutionalDate: setInstitutionalDateAction,
    setInstitutionalFuturesCommodity: setInstitutionalFuturesCommodityAction,
    setInstitutionalOptionsCommodity: setInstitutionalOptionsCommodityAction,
    setInstitutionalHistoryDays: setInstitutionalHistoryDaysAction,
    setTaiwanChipRangeDays: setTaiwanChipRangeDaysAction,
    shiftInstitutionalDate: shiftInstitutionalDateAction,
    updateTaifexStructuredQuery: updateTaifexStructuredQueryAction,
    resetTaifexStructuredQuery: resetTaifexStructuredQueryAction,
  } = createLazyDashboardMarketIntel({
    storedPrefs,
    currentTicker,
    dashboardApi,
    apiFetch,
    pushNotification,
    normalizeTicker,
    isFutoptTicker,
  });
  const {
    marketSnapshots,
    marketStrongMovers,
    marketWeakMovers,
    marketActiveLeaders,
    marketSnapshotLoading,
    marketSnapshotError,
    marketBreadthCards,
    loadMarketSnapshots,
  } = createLazyDashboardMarketSnapshots({
    dashboardApi,
    pushNotification,
  });
  const {
    screenerResults,
    screenerPresets,
    screenerLoading,
    screenerFilters,
    applyScreenerFilters: applyScreenerFiltersAction,
    updateScreenerFilter: updateScreenerFilterAction,
    loadScreenerPresets: loadScreenerPresetsAction,
    runScreener: runScreenerAction,
    saveScreenerPreset: saveScreenerPresetAction,
    loadScreenerPreset: loadScreenerPresetAction,
    deleteScreenerPreset: deleteScreenerPresetAction,
  } = createLazyDashboardScreener({
    storedPrefs,
    dashboardApi,
    pushNotification,
  });

  const quote = shallowReactive({
    price: null,
    open: null,
    high: null,
    low: null,
    prev_close: null,
    volume: null,
    market_cap: null,
    change: 0,
    change_pct: 0,
    resolved_symbol: null,
    market: null,
    exchange: null,
    name: "載入中...",
    source: null,
    quote_type: null,
    is_delayed: true,
    bid: null,
    ask: null,
    bid_size: null,
    ask_size: null,
    bids: [],
    asks: [],
    quote_timestamp: null,
    synced_at: null,
    freshness_status: null,
    is_stale: null,
    market_is_open: null,
    stale_reason: null,
    refresh_status: null,
    refresh_provider: null,
    next_refresh: null,
    backoff_until: null,
    last_refresh_error_category: null,
    provider_degraded: false,
  });

  const marketStatus = reactive({
    nyseOpen: false,
    nasdaqOpen: false,
    tseOpen: false,
    hkOpen: false,
  });
  const activeInd = reactive({ ...DEFAULT_ACTIVE_IND, ...(storedPrefs.activeInd || {}) });
  const activePanels = reactive({ ...DEFAULT_ACTIVE_PANELS, ...(storedPrefs.activePanels || {}) });
  const indicatorSettings = reactive(normalizeIndicatorSettings(storedPrefs.indicatorSettings || {}));
  const crosshair = reactive({
    visible: false,
    absoluteIndex: null,
    canvasX: null,
    canvasY: null,
    hoverPrice: "-",
    change: "-",
    changePct: "-",
    date: "—",
    open: "—",
    high: "—",
    low: "—",
    close: "—",
    volume: "—",
  });

  const ohlcData = computed(() => {
    const displayMode = getEffectiveKlineDisplayMode(klineDisplayMode.value, currentInterval.value);
    return filterRenderableOhlcRows(
      filterRowsForDisplayPeriod(
        aggregateOhlcRows(rawOhlcData.value, displayMode),
        resolveOhlcDisplayPeriod(
          currentTicker.value,
          currentPeriod.value,
          currentInterval.value,
        ),
        displayMode,
      ),
    );
  });
  const {
    alerts,
    alertTriggerLogs,
    alertLogLoading,
    expandedAlertLogId,
    alertModalOpen,
    alertForm,
    loadAlerts,
    openAlertModal,
    closeAlertModal,
    updateAlertField,
    saveAlert,
    createAlertsBatch,
    toggleAlertLog,
    toggleAlertActive,
    deleteAlert,
  } = createLazyDashboardAlerting({
    dashboardApi,
    currentTicker,
    institutionalFuturesCommodity,
    institutionalOptionsCommodity,
    institutionalHistoryDays,
    institutionalOverlay,
    pushNotification,
    normalizeTicker,
  });
  const {
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
    loadBacktestHistory,
    selectBacktestRun,
    toggleBacktestCompare,
    clearBacktestCompare,
    loadJournalData,
    loadJournalFilterPresets,
    updateJournalField: updateJournalFieldAction,
    updateJournalFilter: updateJournalFilterAction,
    applyJournalFilterPreset: applyJournalFilterPresetAction,
    saveJournalFilterPreset: saveJournalFilterPresetAction,
    loadJournalFilterPreset: loadJournalFilterPresetAction,
    deleteJournalFilterPreset: deleteJournalFilterPresetAction,
    resetJournalForm: resetJournalFormAction,
    addJournalAttachment: addJournalAttachmentAction,
    removeJournalAttachment: removeJournalAttachmentAction,
    startJournalEntry: startJournalEntryAction,
    selectJournalEntry: selectJournalEntryAction,
    saveJournalEntry: saveJournalEntryAction,
    deleteJournalEntry: deleteJournalEntryAction,
    updateBacktestField: updateBacktestFieldAction,
    runBacktest: runBacktestAction,
  } = createLazyDashboardTradeWorkbench({
    dashboardApi,
    currentTicker,
    currentInterval,
    quote,
    rightTab,
    pushNotification,
    normalizeTicker,
    inferMarketFromTicker,
    getCurrentDateTimeInputValue,
    compareLimit: 3,
  });
  const {
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
    assetImportBatches,
    assetPortfolio,
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
    assetPortfolioCalculationMetadata,
    assetPortfolioDataQualitySummary,
    assetAccountAllocation,
    assetMarketAllocation,
    assetCurrencyAllocation,
    assetContributors,
    assetPerformanceSummary,
    assetPerformanceCalculationMetadata,
    assetPerformanceDataQualitySummary,
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
    rollbackAssetImportBatch,
    previewAssetJournalImport,
    importAssetJournalEntries,
    recomputeAssetTracking,
  } = createLazyDashboardAssetTracking({
    dashboardApi,
    currentTicker,
    currentName,
    quote,
    pushNotification,
    normalizeTicker,
    inferMarketFromTicker,
    getCurrentDateTimeInputValue,
  });
  const indicatorSnapshot = computed(() => buildIndicatorSnapshot(ohlcData.value, indicatorSettings));
  const activeWatchGroup = computed(
    () => userWatchGroups.value.find((group) => group.id === activeWatchGroupId.value) || null,
  );
  const activeWorkspacePreset = computed(
    () => workspacePresets.value.find((item) => sameWorkspaceId(item.id, activeWorkspacePresetId.value)) || null,
  );

  if (storedPrefs.currentName) {
    currentName.value = storedPrefs.currentName;
  }

  let clockTimer = null;
  const watchlistPoller = createVisibilityPoller(
    () => {
      if (activeBootstrapPage.value === "overview") {
        return Promise.allSettled([loadWatchlist(), loadMarketSnapshots()]);
      }
      if (activeBootstrapPage.value === "terminal") return loadWatchlist({ compact: true });
      return Promise.resolve();
    },
    { intervalMs: 60_000 },
  );
  const alertPoller = createVisibilityPoller(
    () => Promise.allSettled([
      dashboardBootstrap.getResourceState("alerts").status === "ready" ? loadAlerts() : Promise.resolve(),
      loadNotifications(),
    ]),
    { intervalMs: 30_000 },
  );
  const futoptFallbackPoller = createVisibilityPoller(
    () => activeBootstrapPage.value === "terminal" ? refreshFutoptRealtimeFallback() : Promise.resolve(),
    { intervalMs: FUTOPT_REST_POLL_MS },
  );
  const activateRealtime = () => {
    dashboardRealtime.connect();
    dashboardRealtime.subscribeTicker(normalizeTicker(currentTicker.value));
  };
  const deactivateRealtime = () => dashboardRealtime.disconnect();
  const routeControllers = createDashboardRouteControllers({
    terminal: {
      activate: () => {
        activateRealtime();
        watchlistPoller.start();
        futoptFallbackPoller.start();
      },
      deactivate: () => {
        watchlistPoller.stop();
        futoptFallbackPoller.stop();
      },
    },
    overview: {
      activate: () => {
        activateRealtime();
        watchlistPoller.start();
      },
      deactivate: () => watchlistPoller.stop(),
    },
    institutional: {
      activate: activateRealtime,
    },
    review: {
      activate: deactivateRealtime,
    },
    assets: {
      activate: deactivateRealtime,
    },
    settings: {
      activate: deactivateRealtime,
    },
  });
  let futoptFallbackInFlight = false;
  let lastFutoptQuoteOrCandleAt = 0;
  let terminalCacheWriteTimer = null;
  let klineRequestSequence = 0;
  let klineAbortController = null;
  const {
    addCompareTicker,
    clearCompareTickers,
    loadComparisonSeries,
    removeCompareTicker,
    setComparisonMode,
  } = createDashboardComparison({
    dashboardApi,
    compareTickers,
    rawCompareSeries,
    comparisonMode,
    currentTicker,
    currentPeriod,
    currentInterval,
    klineDisplayMode,
    normalizeTicker,
    isFutoptTicker,
    resolveFutoptInterval,
    resolveFutoptPeriod,
    resolveTimeframeInterval,
    getEffectiveKlineDisplayMode,
    getExpandedFetchPeriod,
    getDisplayNameForTicker,
    getRequestSequence: () => klineRequestSequence,
    pushNotification,
  });
  const {
    deleteWorkspacePreset,
    loadWorkspacePreset,
    loadWorkspacePresets,
    saveWorkspacePreset,
  } = createLazyDashboardWorkspacePersistence({
    dashboardApi,
    isBrowser,
    workspacePresets,
    activeWorkspacePresetId,
    currentTicker,
    currentName,
    currentPeriod,
    currentInterval,
    klineDisplayMode,
    chartEngineMode,
    cleanChartMode,
    chartLayout,
    compareTickers,
    comparisonMode,
    activeTool,
    leftTab,
    rightTab,
    workspaceTab,
    screenerFilters,
    activeInd,
    activePanels,
    indicatorSettings,
    drawings,
    selectedDrawingId,
    rawOhlcData,
    crosshair,
    defaultActiveInd: DEFAULT_ACTIVE_IND,
    defaultActivePanels: DEFAULT_ACTIVE_PANELS,
    chartLayoutOptions: CHART_LAYOUT_OPTIONS,
    toolOptions: TOOL_OPTIONS,
    workspaceTabOptions: WORKSPACE_TAB_OPTIONS,
    normalizeTicker,
    resolveDashboardTimeframeForTicker,
    getEffectiveKlineDisplayMode,
    normalizeChartEngineMode,
    normalizeDashboardRightTab,
    createDrawingEntry,
    applyScreenerFilters,
    clearRealtimeTicker: (ticker) => realtimeUiBatcher.clearTicker(ticker),
    unsubscribeTicker: (ticker) => dashboardRealtime.unsubscribeTicker(ticker),
    subscribeTicker: (ticker) => dashboardRealtime.subscribeTicker(ticker),
    rememberRecentTicker,
    ensureKline,
    loadEventCalendar,
    loadTickerIntelligence,
    loadMacroDashboard,
    runScreener,
    pushNotification,
  });
  const {
    syncAll,
    syncCurrentTicker,
  } = createDashboardMarketSync({
    dashboardApi,
    apiFetch,
    currentTicker,
    currentPeriod,
    currentInterval,
    syncingCurrent,
    syncingAll,
    normalizeTicker,
    isFutoptTicker,
    applyQuote,
    ensureKline,
    loadWatchlist,
    loadEventCalendar,
    loadMarketSnapshots,
    loadMacroDashboard,
    loadTickerIntelligence,
    pushNotification,
  });

  function ensureKline(
    ticker = currentTicker.value,
    period = currentPeriod.value,
    interval = currentInterval.value,
    { force = false } = {},
  ) {
    const normalized = normalizeTicker(ticker);
    const resolved = resolveDashboardTimeframeForTicker(normalized, period, interval);
    const queryKey = `${normalized}:${resolved.period}:${resolved.interval}`;
    return dashboardBootstrap.ensure(
      "kline",
      () => loadKline(normalized, resolved.period, resolved.interval),
      { queryKey, force },
    );
  }

  async function apiFetch(path, options = {}) {
    const {
      retries = 0,
      retryDelayMs = 1200,
      timeoutMs = 15_000,
      ...fetchOptions
    } = options;

    let attempt = 0;
    let lastError = null;
    while (attempt <= retries) {
      const start = Date.now();
      try {
        const response = await fetchWithPolicy(`${apiBase}${path}`, fetchOptions, { timeoutMs });
        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json") ? await response.json() : null;
        latency.value = `${Date.now() - start}ms`;
        if (!response.ok) {
          const error = new Error(payload?.detail || `HTTP ${response.status}`);
          error.status = response.status;
          throw error;
        }
        return payload;
      } catch (error) {
        lastError = error;
        const isNetworkError = error instanceof TypeError || error?.code === "QV_API_TIMEOUT";
        const isRetryableHttp = [502, 503, 504].includes(error?.status);
        if (attempt >= retries || (!isNetworkError && !isRetryableHttp)) {
          throw error;
        }
        await sleep(retryDelayMs);
      }
      attempt += 1;
    }
    throw lastError;
  }

  function applyScreenerFilters(filters = {}) {
    applyScreenerFiltersAction(filters);
  }

  async function loadEventCalendar(forceRefresh = false) {
    await loadEventCalendarAction(forceRefresh);
  }

  async function loadMacroDashboard(forceRefresh = false) {
    await loadMacroDashboardAction(forceRefresh);
  }

  async function loadTickerIntelligence(ticker = currentTicker.value, forceRefresh = false) {
    await loadTickerIntelligenceAction(ticker, forceRefresh);
  }

  async function loadScreenerPresets() {
    await loadScreenerPresetsAction();
  }

  function updateScreenerFilter(key, value) {
    updateScreenerFilterAction(key, value);
  }

  async function runScreener() {
    await runScreenerAction();
  }

  async function saveScreenerPreset(name) {
    await saveScreenerPresetAction(name);
  }

  function loadScreenerPreset(preset) {
    loadScreenerPresetAction(preset);
  }

  async function deleteScreenerPreset(presetId) {
    await deleteScreenerPresetAction(presetId);
  }

  function updateJournalField(key, value) {
    journalForm[key] = ["entry_price", "exit_price", "size", "stop_loss", "take_profit"].includes(key)
      ? (value === "" ? "" : Number(value))
      : value;
    if (key === "ticker" && value) {
      journalForm.market = inferMarketFromTicker(value);
    }
  }

  async function updateJournalFilter(key, value) {
    if (key === "scope") {
      journalFilterScope.value = value === "all" ? "all" : "ticker";
    } else if (Object.prototype.hasOwnProperty.call(journalFilters, key)) {
      journalFilters[key] = value;
    }
    await loadJournalData();
  }

  function buildJournalFilterPresetPayload() {
    return {
      scope: journalFilterScope.value === "all" ? "all" : "ticker",
      filters: {
        market: journalFilters.market || "",
        strategy_code: journalFilters.strategy_code || "",
        tag: journalFilters.tag || "",
        search: journalFilters.search || "",
      },
    };
  }

  function normalizeJournalFilterPresetDraft(input) {
    if (input && typeof input === "object" && !Array.isArray(input)) {
      const filters = input.filters && typeof input.filters === "object" ? input.filters : {};
      return {
        id: input.id ?? null,
        name: String(input.name || "").trim(),
        description: input.description || "由交易日誌工作區儲存",
        scope: input.scope === "all" ? "all" : "ticker",
        filters: {
          market: filters.market || "",
          strategy_code: filters.strategy_code || "",
          tag: filters.tag || "",
          search: filters.search || "",
        },
      };
    }

    const name = String(input || "").trim();
    return {
      id: null,
      name,
      description: "由交易日誌工作區儲存",
      ...buildJournalFilterPresetPayload(),
    };
  }

  async function applyJournalFilterPreset(preset = {}) {
    const source = preset && typeof preset === "object" ? preset : {};
    const filters = source.filters && typeof source.filters === "object" ? source.filters : source;
    if (Object.prototype.hasOwnProperty.call(source, "scope")) {
      journalFilterScope.value = source.scope === "all" ? "all" : "ticker";
    }
    for (const key of ["market", "strategy_code", "tag", "search"]) {
      if (Object.prototype.hasOwnProperty.call(filters, key)) {
        journalFilters[key] = filters[key] || "";
      }
    }
    await loadJournalData();
  }

  async function saveJournalFilterPreset(name) {
    const draft = normalizeJournalFilterPresetDraft(name);
    if (!draft.name) return;
    try {
      const existing = draft.id
        ? journalFilterPresets.value.find((item) => String(item?.id) === String(draft.id))
        : journalFilterPresets.value.find((item) => String(item?.name || "").trim() === draft.name);
      if (existing?.id || draft.id) {
        await dashboardApi.updateJournalFilterPreset(draft.id || existing.id, {
          name: draft.name,
          description: draft.description,
          scope: draft.scope,
          filters: draft.filters,
        });
      } else {
        await dashboardApi.createJournalFilterPreset({
          name: draft.name,
          description: draft.description,
          scope: draft.scope,
          filters: draft.filters,
        });
      }
      await loadJournalFilterPresets();
      pushNotification({
        icon: existing?.id || draft.id ? "♻️" : "💾",
        title: existing?.id || draft.id ? "日誌篩選模板已更新" : "日誌篩選模板已儲存",
        msg: draft.name,
        type: "success",
      });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "日誌篩選模板儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function loadJournalFilterPreset(preset) {
    if (!preset) return;
    let nextPreset = preset;
    if (preset.id) {
      try {
        const updated = await dashboardApi.markJournalFilterPresetUsed(preset.id);
        if (updated) {
          nextPreset = updated;
          journalFilterPresets.value = journalFilterPresets.value.map((item) =>
            String(item?.id) === String(updated.id) ? updated : item,
          );
        }
      } catch (error) {
        console.error(error);
      }
    }
    await applyJournalFilterPreset(nextPreset);
    pushNotification({ icon: "🧭", title: "已載入日誌篩選模板", msg: preset.name || "preset", type: "success" });
  }

  async function deleteJournalFilterPreset(presetId) {
    if (!presetId) return;
    try {
      await dashboardApi.deleteJournalFilterPreset(presetId);
      await loadJournalFilterPresets();
      pushNotification({ icon: "🗑", title: "日誌篩選模板已刪除", msg: String(presetId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "日誌篩選模板刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  function resetJournalForm() {
    applyJournalEntryToForm({
      ticker: currentTicker.value,
      market: inferMarketFromTicker(currentTicker.value),
      entry_price: quote.price ?? "",
      size: 1,
    });
  }

  function addJournalAttachment() {
    if (!journalForm.attachment_path) return;
    journalForm.attachments = [
      ...journalForm.attachments,
      {
        file_path: journalForm.attachment_path,
        file_type: journalForm.attachment_type || null,
      },
    ];
    journalForm.attachment_path = "";
    journalForm.attachment_type = "";
  }

  function removeJournalAttachment(index) {
    journalForm.attachments = journalForm.attachments.filter((_, itemIndex) => itemIndex !== index);
  }

  function startJournalEntry(seed = {}) {
    rightTab.value = "journal";
    applyJournalEntryToForm({
      ticker: seed.ticker || currentTicker.value,
      market: seed.market || inferMarketFromTicker(seed.ticker || currentTicker.value),
      entry_price: seed.entry_price ?? quote.price ?? "",
      strategy_code: seed.strategy_code || backtestResult.value?.strategy_key || "",
      entry_reason: seed.entry_reason || "",
      review_notes: seed.review_notes || "",
      tags: Array.isArray(seed.tags) ? seed.tags : [],
      size: 1,
    });
    void loadJournalData();
  }

  async function selectJournalEntry(entryId) {
    if (!entryId) return;
    journalLoading.value = true;
    try {
      const entry = await dashboardApi.getJournalTrade(entryId);
      applyJournalEntryToForm(entry);
      rightTab.value = "journal";
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易紀錄讀取失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      journalLoading.value = false;
    }
  }

  async function saveJournalEntry() {
    journalLoading.value = true;
    try {
      const isEditing = Boolean(journalForm.id);
      const payload = {
        ticker: normalizeTicker(journalForm.ticker),
        market: journalForm.market || inferMarketFromTicker(journalForm.ticker),
        direction: journalForm.direction,
        strategy_code: journalForm.strategy_code || null,
        entry_time: journalForm.entry_time,
        entry_price: Number(journalForm.entry_price),
        exit_time: journalForm.exit_time || null,
        exit_price: journalForm.exit_price === "" ? null : Number(journalForm.exit_price),
        size: Number(journalForm.size),
        stop_loss: journalForm.stop_loss === "" ? null : Number(journalForm.stop_loss),
        take_profit: journalForm.take_profit === "" ? null : Number(journalForm.take_profit),
        entry_reason: journalForm.entry_reason || null,
        exit_reason: journalForm.exit_reason || null,
        emotion_tag: journalForm.emotion_tag || null,
        review_notes: journalForm.review_notes || null,
        tags: journalForm.tags_text
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        attachments: journalForm.attachments.map((item) => ({
          file_path: item.file_path,
          file_type: item.file_type || null,
        })),
      };
      const record = journalForm.id
        ? await dashboardApi.updateJournalTrade(journalForm.id, payload)
        : await dashboardApi.createJournalTrade(payload);
      applyJournalEntryToForm(record);
      await loadJournalData();
      pushNotification({
        icon: "📝",
        title: isEditing ? "交易日誌已更新" : "交易日誌已建立",
        msg: `${record.ticker} · ${record.direction}`,
        type: "success",
      });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易日誌儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      journalLoading.value = false;
    }
  }

  async function deleteJournalEntry(entryId = journalForm.id) {
    if (!entryId) return;
    journalLoading.value = true;
    try {
      await dashboardApi.deleteJournalTrade(entryId);
      if (journalForm.id === entryId) {
        resetJournalForm();
      }
      await loadJournalData();
      pushNotification({ icon: "🗑", title: "交易紀錄已刪除", msg: String(entryId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易紀錄刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      journalLoading.value = false;
    }
  }

  function applyQuote(data) {
    const previousTotalVolume = Number.isFinite(Number(quote.volume)) ? Number(quote.volume) : null;
    const merged = mergeRealtimeQuote(quote, data, currentName.value);
    Object.entries(merged).forEach(([key, value]) => {
      if (quote[key] !== value) quote[key] = value;
    });
    if (merged.name) currentName.value = merged.name;
    lastUpdate.value = formatQuoteTimestampLabel(quote.quote_timestamp || quote.synced_at);
    return {
      ...merged,
      previous_total_volume: previousTotalVolume,
    };
  }

  function resetQuote() {
    applyQuote({
      price: null,
      open: null,
      high: null,
      low: null,
      prev_close: null,
      volume: null,
      market_cap: null,
      change: 0,
      change_pct: 0,
      resolved_symbol: null,
      market: null,
      exchange: null,
      name: currentName.value,
      source: null,
      quote_type: null,
      is_delayed: true,
      bid: null,
      ask: null,
      bid_size: null,
      ask_size: null,
      bids: [],
      asks: [],
      quote_timestamp: null,
      synced_at: null,
      freshness_status: null,
      is_stale: null,
      market_is_open: null,
      stale_reason: null,
      refresh_status: null,
      refresh_provider: null,
      next_refresh: null,
      backoff_until: null,
      last_refresh_error_category: null,
      provider_degraded: false,
    });
  }

  function updateCurrentCandleFromQuote(data) {
    if (!rawOhlcData.value.length || data.price == null) return;
    rawOhlcData.value = upsertRealtimeOhlcFromQuote(
      rawOhlcData.value,
      data,
      currentInterval.value,
    ).slice(-resolveOhlcBufferLimit(currentTicker.value, currentInterval.value));
  }

  function upsertRealtimeCandleRow(data) {
    if (!data?.date || !isIntradayInterval(currentInterval.value)) return;
    rawOhlcData.value = upsertRealtimeOhlcFromCandle(
      rawOhlcData.value,
      data,
      currentInterval.value,
    ).slice(-resolveOhlcBufferLimit(currentTicker.value, currentInterval.value));
  }

  function scheduleTerminalSnapshotCacheWrite() {
    if (terminalCacheWriteTimer != null) window.clearTimeout(terminalCacheWriteTimer);
    terminalCacheWriteTimer = window.setTimeout(() => {
      terminalCacheWriteTimer = null;
      const savedAt = Date.now();
      klineCacheSavedAt.value = savedAt;
      void terminalCache.writeOhlc({
        ticker: currentTicker.value,
        interval: currentInterval.value,
        rows: rawOhlcData.value,
      });
    }, 1500);
  }

  function handleRealtimeQuote(message) {
    const data = message.data;
    if (data.ticker !== currentTicker.value && data.ticker !== normalizeTicker(currentTicker.value)) return;
    if (isFutoptTicker(data.ticker)) {
      lastFutoptQuoteOrCandleAt = Date.now();
      futoptRefreshStatus.value = "realtime";
      futoptDataStale.value = false;
    }
    const mergedQuote = applyQuote(data);
    updateCurrentCandleFromQuote(mergedQuote);
    klineDataOrigin.value = "realtime";
    scheduleTerminalSnapshotCacheWrite();
  }

  function handleRealtimeBook(message) {
    const data = message.data || {};
    const hasField = (key) => Object.prototype.hasOwnProperty.call(data, key);
    const toFiniteNumberOrNull = (value) => {
      const numeric = Number(value);
      return Number.isFinite(numeric) ? numeric : null;
    };
    const toPositiveQuoteValue = (value) => {
      const numeric = toFiniteNumberOrNull(value);
      return numeric != null && numeric > 0 ? numeric : null;
    };
    if (message.ticker !== currentTicker.value && message.ticker !== normalizeTicker(currentTicker.value)) return;
    quote.bid = hasField("bid")
      ? (data.bid == null || data.bid === "" ? null : (toPositiveQuoteValue(data.bid) ?? quote.bid ?? null))
      : (quote.bid ?? null);
    quote.ask = hasField("ask")
      ? (data.ask == null || data.ask === "" ? null : (toPositiveQuoteValue(data.ask) ?? quote.ask ?? null))
      : (quote.ask ?? null);
    quote.bid_size = data.bid_size ?? quote.bid_size ?? null;
    quote.ask_size = data.ask_size ?? quote.ask_size ?? null;
    quote.bids = mergeBookLevels(
      quote.bids,
      data.bids,
      hasField("bid") || hasField("bid_size") ? { price: quote.bid, size: quote.bid_size } : null,
    );
    quote.asks = mergeBookLevels(
      quote.asks,
      data.asks,
      hasField("ask") || hasField("ask_size") ? { price: quote.ask, size: quote.ask_size } : null,
    );
    if (data.quote_timestamp) {
      quote.quote_timestamp = data.quote_timestamp;
      lastUpdate.value = formatQuoteTimestampLabel(data.quote_timestamp);
    }
  }

  function handleRealtimeCandle(message) {
    const data = message.data;
    if (message.ticker !== currentTicker.value && message.ticker !== normalizeTicker(currentTicker.value)) return;
    if (isFutoptTicker(message.ticker || data?.ticker)) {
      lastFutoptQuoteOrCandleAt = Date.now();
      futoptRefreshStatus.value = "realtime";
      futoptDataStale.value = false;
    }
    upsertRealtimeCandleRow(data);
    klineDataOrigin.value = "realtime";
    scheduleTerminalSnapshotCacheWrite();
  }

  function applyWatchlistPayload(payload) {
    watchlistGroups.value = payload?.groups || [];
    const currentUserGroups = watchlistGroups.value.filter((group) => group.name !== MARKET_GROUP_NAME);
    if (
      !activeWatchGroupId.value
      || !currentUserGroups.some((group) => group.id === activeWatchGroupId.value)
    ) {
      activeWatchGroupId.value = currentUserGroups[0]?.id ?? null;
    }
    const current = watchlist.value.find((item) => item.ticker === currentTicker.value);
    if (current) currentName.value = current.name || current.ticker;
  }

  async function loadWatchlist({ compact = activeBootstrapPage.value === "terminal" } = {}) {
    watchlistLoading.value = true;
    watchlistError.value = false;
    let cacheApplied = false;
    try {
      const remoteRequest = compact
        ? dashboardApi.listWatchlistMetadata()
        : dashboardApi.listWatchlist();
      if (compact) {
        const cached = await terminalCache.readWatchlistMetadata();
        if (cached?.payload) {
          applyWatchlistPayload(cached.payload);
          cacheApplied = true;
        }
      }
      const payload = await remoteRequest;
      applyWatchlistPayload(payload);
      if (compact) void terminalCache.writeWatchlistMetadata(payload);
    } catch (error) {
      watchlistError.value = !cacheApplied;
    } finally {
      watchlistLoading.value = false;
    }
  }

  function getDisplayNameForTicker(ticker) {
    const normalized = normalizeTicker(ticker);
    return (
      watchlist.value.find((item) => item.ticker === normalized)?.name
      || searchResults.value.find((item) => item.ticker === normalized)?.name
      || normalized
    );
  }

  function rememberRecentTicker(ticker, name = ticker) {
    const normalized = normalizeTicker(ticker);
    if (!normalized) return;
    recentTickers.value = [
      { ticker: normalized, name: name || normalized, viewedAt: new Date().toISOString() },
      ...recentTickers.value.filter((item) => normalizeTicker(item?.ticker) !== normalized),
    ].slice(0, RECENT_TICKERS_LIMIT);
    writeRecentTickers(recentTickers.value);
  }

  async function createWatchGroup(name) {
    const payload = name && typeof name === "object" ? name : { name };
    const trimmed = String(payload?.name || "").trim();
    const color = WATCHLIST_COLOR_OPTIONS.includes(payload?.color) ? payload.color : null;
    if (!trimmed) return;
    try {
      const group = await dashboardApi.createWatchlistGroup({ name: trimmed, color });
      await loadWatchlist();
      activeWatchGroupId.value = group.id;
      pushNotification({
        icon: "🗂",
        title: "觀察群組已建立",
        msg: trimmed,
        type: "success",
      });
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "建立群組失敗",
        msg: error.message || "請稍後再試",
        type: "error",
      });
    }
  }

  async function renameWatchGroup(groupId, name) {
    const payload = name && typeof name === "object" ? name : { name };
    const trimmed = String(payload?.name || "").trim();
    const color = WATCHLIST_COLOR_OPTIONS.includes(payload?.color) ? payload.color : null;
    if (!groupId || !trimmed) return;
    try {
      await dashboardApi.updateWatchlistGroup(groupId, { name: trimmed, color });
      await loadWatchlist();
      pushNotification({
        icon: "✎",
        title: "群組已重新命名",
        msg: trimmed,
        type: "success",
      });
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "重新命名失敗",
        msg: error.message || "請稍後再試",
        type: "error",
      });
    }
  }

  async function deleteWatchGroup(groupId) {
    if (!groupId) return;
    try {
      await dashboardApi.deleteWatchlistGroup(groupId);
      if (activeWatchGroupId.value === groupId) {
        activeWatchGroupId.value = userWatchGroups.value.find((group) => group.id !== groupId)?.id ?? null;
      }
      await loadWatchlist();
      pushNotification({
        icon: "🗑",
        title: "群組已刪除",
        msg: "觀察群組已移除",
        type: "success",
      });
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "刪除群組失敗",
        msg: error.message || "請稍後再試",
        type: "error",
      });
    }
  }

  async function addTickerToWatchlist(input, groupId = activeWatchGroupId.value) {
    const request = input && typeof input === "object" && !Array.isArray(input)
      ? input
      : { ticker: input, groupId };
    const normalized = normalizeTicker(request.ticker);
    const targetGroupId = request.groupId || groupId;
    const tags = Array.isArray(request.tags)
      ? request.tags.map((item) => String(item || "").trim()).filter(Boolean).slice(0, 6)
      : [];
    if (!normalized || !targetGroupId) return;
    try {
      const added = await dashboardApi.createWatchlistItem({
        group_id: targetGroupId,
        ticker: normalized,
        tags,
      });
      await loadWatchlist();
      pushNotification({
        icon: "⭐",
        title: "已加入自選股",
        msg: `${added.ticker} → ${added.group_name}${tags.length ? ` · ${tags[0]}` : ""}`,
        type: "success",
      });
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "加入自選股失敗",
        msg: error.message || "請確認群組與代號是否正確",
        type: "error",
      });
    }
  }

  async function addTickersToWatchlistBatch(inputs, groupId = activeWatchGroupId.value) {
    const requests = (Array.isArray(inputs) ? inputs : [inputs])
      .map((item) => (item && typeof item === "object" && !Array.isArray(item) ? item : { ticker: item, groupId }))
      .filter(Boolean);
    const targetGroupId = requests.find((item) => item.groupId)?.groupId || groupId;
    if (!targetGroupId) {
      pushNotification({
        icon: "⚠️",
        title: "加入自選股失敗",
        msg: "請先選擇觀察群組",
        type: "error",
      });
      return { added: 0, failed: 0 };
    }

    const seen = new Set();
    const normalizedRequests = requests.reduce((items, request) => {
      const ticker = normalizeTicker(request.ticker);
      if (!ticker || seen.has(ticker)) return items;
      seen.add(ticker);
      items.push({
        ticker,
        tags: Array.isArray(request.tags)
          ? request.tags.map((item) => String(item || "").trim()).filter(Boolean).slice(0, 6)
          : [],
      });
      return items;
    }, []);

    if (!normalizedRequests.length) {
      return { added: 0, failed: 0 };
    }

    let addedCount = 0;
    let failedCount = 0;
    let groupName = activeWatchGroup.value?.name || "";

    for (const request of normalizedRequests) {
      try {
        const added = await dashboardApi.createWatchlistItem({
          group_id: targetGroupId,
          ticker: request.ticker,
          tags: request.tags,
        });
        addedCount += 1;
        groupName = added.group_name || groupName;
      } catch (error) {
        failedCount += 1;
        console.error(error);
      }
    }

    if (addedCount > 0) {
      await loadWatchlist();
      pushNotification({
        icon: failedCount > 0 ? "⚠️" : "⭐",
        title: "已加入自選股",
        msg: `已加入 ${addedCount} 檔${groupName ? ` → ${groupName}` : ""}${failedCount > 0 ? `，略過 ${failedCount} 檔` : ""}`,
        type: failedCount > 0 ? "warning" : "success",
      });
      return { added: addedCount, failed: failedCount };
    }

    pushNotification({
      icon: "⚠️",
      title: "加入自選股失敗",
      msg: "請確認觀察群組與代號設定",
      type: "error",
    });
    return { added: 0, failed: failedCount };
  }

  async function removeTickerFromWatchlist(itemId) {
    if (!itemId) return;
    try {
      await dashboardApi.deleteWatchlistItem(itemId);
      await loadWatchlist();
      pushNotification({
        icon: "🗑",
        title: "已移除自選股",
        msg: "標的已從群組中移除",
        type: "success",
      });
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "移除失敗",
        msg: error.message || "請稍後再試",
        type: "error",
      });
    }
  }

  async function reorderWatchlistItems(groupId, itemIds) {
    if (!groupId || !Array.isArray(itemIds) || !itemIds.length) return;
    try {
      await dashboardApi.reorderWatchlistItems(groupId, itemIds);
      await loadWatchlist();
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "排序更新失敗",
        msg: error.message || "請稍後再試",
        type: "error",
      });
    }
  }

  async function refreshFutoptRealtimeFallback({ force = false } = {}) {
    const requestedTicker = normalizeTicker(currentTicker.value);
    const requestedPeriod = currentPeriod.value;
    const requestedInterval = currentInterval.value;
    if (
      futoptFallbackInFlight
      || (!force && !shouldPollFutoptRestFallback({
        ticker: requestedTicker,
        interval: requestedInterval,
        lastRealtimeAt: lastFutoptQuoteOrCandleAt,
      }))
    ) {
      return;
    }

    futoptFallbackInFlight = true;
    try {
      const [ohlcResult, quoteResult] = await Promise.allSettled([
        dashboardApi.getFutoptOhlc(requestedTicker, {
          period: requestedPeriod,
          interval: requestedInterval,
          refreshMode: "blocking",
          since: rawOhlcData.value.at(-1)?.date || null,
          limit: 100,
        }),
        dashboardApi.getFutoptQuote(requestedTicker),
      ]);

      const ohlcPayload = ohlcResult.status === "fulfilled" ? ohlcResult.value : null;
      const quotePayload = quoteResult.status === "fulfilled" ? quoteResult.value : null;
      const resolvedTicker = normalizeTicker(ohlcPayload?.ticker || quotePayload?.ticker || requestedTicker);
      const activeTicker = normalizeTicker(currentTicker.value);
      if (![requestedTicker, resolvedTicker].includes(activeTicker)) return;

      if (resolvedTicker && resolvedTicker !== activeTicker) {
        realtimeUiBatcher.clearTicker(activeTicker);
        dashboardRealtime.unsubscribeTicker(activeTicker);
        currentTicker.value = resolvedTicker;
        dashboardRealtime.subscribeTicker(resolvedTicker);
      }

      if (Array.isArray(ohlcPayload?.data) && ohlcPayload.data.length) {
        rawOhlcData.value = mergeOhlcBuffer(
          rawOhlcData.value,
          ohlcPayload.data,
          resolveOhlcBufferLimit(requestedTicker, requestedInterval),
        );
        klineDataOrigin.value = "database";
        futoptRefreshStatus.value = ohlcPayload.refresh_status || "refreshed";
        futoptDataStale.value = Boolean(ohlcPayload.is_stale);
      }
      if (quotePayload) {
        const mergedQuote = applyQuote(quotePayload);
        updateCurrentCandleFromQuote(mergedQuote);
      }
      if (ohlcPayload || quotePayload) {
        lastFutoptQuoteOrCandleAt = Date.now();
      }
    } catch (error) {
      console.debug("Futopt realtime REST fallback skipped", error);
    } finally {
      futoptFallbackInFlight = false;
    }
  }

  async function loadQuote(ticker = currentTicker.value, { requestToken = null } = {}) {
    try {
      const normalized = normalizeTicker(ticker);
      const data = isFutoptTicker(normalized)
        ? await dashboardApi.getFutoptQuote(normalized)
        : await apiFetch(`/api/quote/${normalized}`, { retries: 6, retryDelayMs: 1200 });
      if (requestToken != null && requestToken !== klineRequestSequence) return;
      const resolved = normalizeTicker(data?.ticker || data?.resolved_symbol || normalized);
      if (![normalized, resolved].includes(normalizeTicker(currentTicker.value))) return;
      if (data) applyQuote(data);
    } catch (error) {
      console.error(error);
    }
  }

  async function hydrateFutoptHistory({
    ticker,
    resolvedTicker,
    period,
    interval,
    requestToken,
    signal,
    initialRowCount,
  }) {
    if (initialRowCount < INITIAL_OHLC_REQUEST_LIMIT) return;
    try {
      const payload = await dashboardApi.getFutoptOhlc(ticker, {
        period,
        interval,
        refreshMode: "none",
        limit: FUTOPT_HISTORY_BUFFER_LIMIT,
        warmup: INITIAL_OHLC_WARMUP_BARS,
        signal,
      });
      if (requestToken !== klineRequestSequence) return;
      const activeTicker = normalizeTicker(currentTicker.value);
      const responseTicker = normalizeTicker(payload?.ticker || resolvedTicker || ticker);
      if (![normalizeTicker(ticker), normalizeTicker(resolvedTicker), responseTicker].includes(activeTicker)) return;

      const mergedRows = mergeOhlcBuffer(
        rawOhlcData.value,
        payload?.data || [],
        resolveOhlcBufferLimit(activeTicker, interval),
      );
      const historyExpanded = mergedRows.length > rawOhlcData.value.length
        || mergedRows.at(0)?.date !== rawOhlcData.value.at(0)?.date;
      if (!historyExpanded) return;

      rawOhlcData.value = mergedRows;
      klineDataOrigin.value = "database";
      klineCacheSavedAt.value = Date.now();
      void terminalCache.writeOhlc({
        ticker: activeTicker,
        interval,
        rows: mergedRows,
      });
    } catch (error) {
      if (error?.name !== "AbortError") {
        console.debug("Futopt history hydration skipped", error);
      }
    }
  }

  async function loadKline(ticker = currentTicker.value, period = currentPeriod.value, interval = currentInterval.value) {
    const requestToken = ++klineRequestSequence;
    if (klineAbortController) klineAbortController.abort();
    klineAbortController = typeof AbortController === "function" ? new AbortController() : null;
    const requestSignal = klineAbortController?.signal;
    const normalized = normalizeTicker(ticker);
    const isFutopt = isFutoptTicker(normalized);
    const { period: resolvedPeriod, interval: resolvedInterval } = resolveDashboardTimeframeForTicker(
      normalized,
      period,
      interval,
    );
    const displayMode = getEffectiveKlineDisplayMode(klineDisplayMode.value, resolvedInterval);
    const fetchPeriod = isFutopt ? resolvedPeriod : getExpandedFetchPeriod(resolvedPeriod, displayMode);
    currentPeriod.value = resolvedPeriod;
    currentInterval.value = resolvedInterval;
    if (isIntradayInterval(resolvedInterval)) {
      klineDisplayMode.value = "day";
    }
    chartLoading.value = true;
    klineDataOrigin.value = "loading";
    loadingMessage.value = `載入 ${normalized} K 線...`;
    let cacheApplied = false;
    try {
      const remoteRequest = isFutopt
        ? dashboardApi.getFutoptOhlc(normalized, {
          period: fetchPeriod,
          interval: resolvedInterval,
          refreshMode: "background",
          limit: INITIAL_OHLC_REQUEST_LIMIT,
          warmup: INITIAL_OHLC_WARMUP_BARS,
          signal: requestSignal,
        })
        : dashboardApi.getOhlc(normalized, {
          period: fetchPeriod,
          interval: resolvedInterval,
          limit: INITIAL_OHLC_REQUEST_LIMIT,
          warmup: INITIAL_OHLC_WARMUP_BARS,
          signal: requestSignal,
        });
      const cached = await terminalCache.readOhlc({ ticker: normalized, interval: resolvedInterval });
      if (cached?.rows?.length && requestToken === klineRequestSequence) {
        rawOhlcData.value = mergeOhlcBuffer(
          [],
          cached.rows,
          resolveOhlcBufferLimit(normalized, resolvedInterval),
        );
        klineDataOrigin.value = "cache";
        klineCacheSavedAt.value = cached.savedAt;
        cacheApplied = true;
        chartLoading.value = false;
        markQuantVisionPerformance(QV_PERFORMANCE_MARKS.chartDataReady, {
          ticker: normalized,
          interval: resolvedInterval,
          rows: rawOhlcData.value.length,
          origin: "cache",
        });
      }
      const data = await remoteRequest;
      if (requestToken !== klineRequestSequence) return;
      const resolvedTicker = normalizeTicker(data?.ticker || normalized);
      if (resolvedTicker !== currentTicker.value) {
        realtimeUiBatcher.clearTicker(currentTicker.value);
        dashboardRealtime.unsubscribeTicker(currentTicker.value);
        currentTicker.value = resolvedTicker;
      }
      dashboardRealtime.subscribeTicker(resolvedTicker);
      rawOhlcData.value = mergeOhlcBuffer(
        [],
        data.data || [],
        resolveOhlcBufferLimit(resolvedTicker, resolvedInterval),
      );
      klineDataOrigin.value = "database";
      klineCacheSavedAt.value = Date.now();
      void terminalCache.writeOhlc({
        ticker: resolvedTicker,
        interval: resolvedInterval,
        rows: rawOhlcData.value,
      });
      if (isFutopt) {
        futoptRefreshStatus.value = data.refresh_status || "idle";
        futoptDataStale.value = Boolean(data.is_stale);
      } else {
        futoptRefreshStatus.value = "idle";
        futoptDataStale.value = false;
      }
      markQuantVisionPerformance(QV_PERFORMANCE_MARKS.chartDataReady, {
        ticker: resolvedTicker,
        interval: resolvedInterval,
        rows: rawOhlcData.value.length,
        origin: "database",
      });
      // The persisted snapshot is already drawable; quote and comparison hydration must not keep the chart covered.
      chartLoading.value = false;
      crosshair.visible = false;
      if (isFutopt) {
        void hydrateFutoptHistory({
          ticker: normalized,
          resolvedTicker,
          period: fetchPeriod,
          interval: resolvedInterval,
          requestToken,
          signal: requestSignal,
          initialRowCount: Array.isArray(data.data) ? data.data.length : 0,
        });
      }
      await loadComparisonSeries(compareTickers.value, { requestToken });
      if (requestToken !== klineRequestSequence) return;
      if (rawOhlcData.value.length > 0) await loadQuote(resolvedTicker, { requestToken });
      else resetQuote();
    } catch (error) {
      if (error?.name === "AbortError" || requestToken !== klineRequestSequence) return;
      pushNotification({
        icon: "⚠️",
        title: cacheApplied ? "後端更新失敗，暫用快取" : "載入失敗",
        msg: `無法取得 ${normalized} 資料`,
        type: "error",
      });
    } finally {
      if (requestToken === klineRequestSequence) chartLoading.value = false;
    }
  }

  async function selectTicker(ticker, name = ticker) {
    const normalized = normalizeTicker(ticker);
    realtimeUiBatcher.clearTicker(currentTicker.value);
    dashboardRealtime.unsubscribeTicker(normalizeTicker(currentTicker.value));
    currentTicker.value = normalized;
    currentName.value = name || normalized;
    compareTickers.value = compareTickers.value.filter((item) => item !== normalized);
    drawings.value = [];
    selectedDrawingId.value = null;
    rawOhlcData.value = [];
    crosshair.visible = false;
    rememberRecentTicker(normalized, name || normalized);
    await ensureKline(normalized, currentPeriod.value, currentInterval.value, { force: true });
    if (activeBootstrapPage.value === "overview") {
      void loadTickerIntelligence(normalized);
    } else if (activeBootstrapPage.value === "institutional") {
      void ensureInstitutionalOverlayForTicker(normalized);
    } else if (activeBootstrapPage.value === "review") {
      if (rightTab.value === "backtest") void loadBacktestHistory({ ticker: normalized });
      if (rightTab.value === "journal") void loadJournalData();
    }
  }

  function setTimeframe(timeframe) {
    const nextPeriod = timeframe?.tf || currentPeriod.value;
    const { period: resolvedPeriod, interval: resolvedInterval } = resolveDashboardTimeframeForTicker(
      currentTicker.value,
      nextPeriod,
      timeframe?.iv || currentInterval.value,
    );
    if (isIntradayInterval(resolvedInterval)) {
      klineDisplayMode.value = "day";
    }
    currentPeriod.value = resolvedPeriod;
    currentInterval.value = resolvedInterval;
    void ensureKline(currentTicker.value, resolvedPeriod, resolvedInterval);
  }

  async function loadInstitutionalData(dateValue = institutionalDate.value, forceRefresh = false) {
    await loadInstitutionalDataAction(dateValue, forceRefresh);
  }

  async function loadInstitutionalInsights(
    dateValue = institutionalDate.value,
    futuresCommodity = institutionalFuturesCommodity.value,
    optionsCommodity = institutionalOptionsCommodity.value,
    days = institutionalHistoryDays.value,
    forceRefresh = false,
  ) {
    await loadInstitutionalInsightsAction(
      dateValue,
      futuresCommodity,
      optionsCommodity,
      days,
      forceRefresh,
    );
  }

  async function ensureInstitutionalOverlayForTicker(ticker = currentTicker.value) {
    await ensureInstitutionalOverlayForTickerAction(ticker);
  }

  async function setInstitutionalDate(value) {
    await setInstitutionalDateAction(value);
  }

  async function setInstitutionalFuturesCommodity(value) {
    await setInstitutionalFuturesCommodityAction(value);
  }

  async function setInstitutionalOptionsCommodity(value) {
    await setInstitutionalOptionsCommodityAction(value);
  }

  async function setInstitutionalHistoryDays(value) {
    await setInstitutionalHistoryDaysAction(value);
  }

  async function shiftInstitutionalDate(days) {
    await shiftInstitutionalDateAction(days);
  }

  async function loadTaifexStructuredData() {
    await loadTaifexStructuredDataAction();
  }

  function updateTaifexStructuredQuery(patch) {
    updateTaifexStructuredQueryAction(patch);
  }

  async function resetTaifexStructuredQuery() {
    await resetTaifexStructuredQueryAction();
  }

  async function setKlineDisplayMode(mode) {
    if (isIntradayInterval(currentInterval.value)) {
      klineDisplayMode.value = "day";
      return;
    }
    const nextMode = normalizeKlineDisplayMode(mode);
    if (nextMode === klineDisplayMode.value) return;
    klineDisplayMode.value = nextMode;
    crosshair.visible = false;
    await ensureKline(currentTicker.value, currentPeriod.value, currentInterval.value);
  }

  function setLeftTab(tab) {
    leftTab.value = tab;
  }

  function setActiveWatchGroup(groupId) {
    activeWatchGroupId.value = groupId;
  }

  async function setRightTab(tab) {
    const normalizedTab = normalizeDashboardRightTab(tab);
    rightTab.value = normalizedTab;
    if (normalizedTab === "alerts") {
      await dashboardBootstrap.ensure("alerts", () => loadAlerts({ silent: false }));
    }
    if (normalizedTab === "assets") {
      await dashboardBootstrap.ensure("assets", () => loadAssetTrackingData({ refresh: true, silent: false }));
    }
    if (normalizedTab === "backtest") {
      await dashboardBootstrap.ensure(
        "backtest",
        () => loadBacktestHistory({ ticker: currentTicker.value }),
        { queryKey: normalizeTicker(currentTicker.value) },
      );
    }
    if (normalizedTab === "journal") {
      await Promise.allSettled([
        dashboardBootstrap.ensure("journal-presets", loadJournalFilterPresets),
        dashboardBootstrap.ensure(
          "journal",
          () => loadJournalData({ silent: false }),
          { queryKey: normalizeTicker(currentTicker.value) },
        ),
      ]);
    }
  }

  async function setWorkspaceTab(tab) {
    workspaceTab.value = WORKSPACE_TAB_OPTIONS.includes(tab) ? tab : "chart";
    if (workspaceTab.value === "institutional") {
      if (!institutionalData.value && !institutionalLoading.value) {
        await dashboardBootstrap.ensure("institutional", loadInstitutionalData);
      } else if (!institutionalInsights.value && !institutionalInsightsLoading.value) {
        await dashboardBootstrap.ensure("institutional-insights", loadInstitutionalInsights);
      }
      return;
    }
    if (workspaceTab.value === "events") {
      await Promise.allSettled([
        dashboardBootstrap.ensure("events", () => loadEventCalendar()),
        dashboardBootstrap.ensure(
          "ticker-intelligence",
          () => loadTickerIntelligence(currentTicker.value),
          { queryKey: normalizeTicker(currentTicker.value) },
        ),
      ]);
      return;
    }
    if (workspaceTab.value === "macro") {
      await dashboardBootstrap.ensure("macro", () => loadMacroDashboard());
      return;
    }
    if (workspaceTab.value === "screener") {
      if (!screenerPresets.value.length) {
        await dashboardBootstrap.ensure("screener-presets", loadScreenerPresets);
      }
      if (!screenerResults.value.items?.length) {
        await dashboardBootstrap.ensure("screener", runScreener);
      }
    }
  }

  async function bootstrapWorkspace(page = activeBootstrapPage.value, secondaryTab = initialRightTab) {
    const rawPage = String(page || "").toLowerCase();
    const normalizedPage = ["terminal", "overview", "institutional", "review", "assets", "settings"].includes(rawPage)
      ? rawPage
      : "overview";
    activeBootstrapPage.value = normalizedPage;

    await routeControllers.activate(
      ["journal", "backtest", "review"].includes(normalizedPage) ? "review" : normalizedPage,
    );
    alertPoller.start();
    dashboardBootstrap.defer("notifications", () => loadNotifications({ silent: true }));

    if (normalizedPage === "terminal") {
      workspaceTab.value = "chart";
      return Promise.allSettled([
        ensureKline(currentTicker.value, currentPeriod.value, currentInterval.value),
        dashboardBootstrap.ensure("workspaces", loadWorkspacePresets),
        dashboardBootstrap.ensure("watchlist", () => loadWatchlist({ compact: true }), { queryKey: "compact" }),
      ]);
    }

    if (normalizedPage === "overview") {
      workspaceTab.value = "screener";
      return Promise.allSettled([
        dashboardBootstrap.ensure("watchlist", () => loadWatchlist({ compact: false }), { queryKey: "full" }),
        dashboardBootstrap.ensure("market-snapshots", () => loadMarketSnapshots(false)),
        dashboardBootstrap.ensure("macro", () => loadMacroDashboard(false)),
        dashboardBootstrap.ensure("events", () => loadEventCalendar(false)),
        dashboardBootstrap.ensure("screener-presets", loadScreenerPresets),
        dashboardBootstrap.ensure("screener", runScreener),
        dashboardBootstrap.ensure(
          "ticker-intelligence",
          () => loadTickerIntelligence(currentTicker.value, false),
          { queryKey: normalizeTicker(currentTicker.value) },
        ),
      ]);
    }

    if (normalizedPage === "institutional") {
      workspaceTab.value = "institutional";
      return Promise.allSettled([
        dashboardBootstrap.ensure("institutional", loadInstitutionalData),
        dashboardBootstrap.ensure("institutional-insights", loadInstitutionalInsights),
      ]);
    }

    if (normalizedPage === "assets") {
      rightTab.value = "assets";
      return Promise.allSettled([
        dashboardBootstrap.ensure("assets", () => loadAssetTrackingData({ refresh: true, silent: false })),
      ]);
    }

    if (normalizedPage === "review") {
      return Promise.allSettled([setRightTab(secondaryTab === "backtest" ? "backtest" : "journal")]);
    }

    return [];
  }

  function setChartLayout(layout) {
    chartLayout.value = CHART_LAYOUT_OPTIONS.includes(layout) ? layout : "single";
  }

  function setChartEngineMode(mode) {
    chartEngineMode.value = normalizeChartEngineMode(mode);
  }

  function toggleIndicator(name) {
    cleanChartMode.value = false;
    activeInd[name] = !activeInd[name];
  }

  function togglePanel(name) {
    cleanChartMode.value = false;
    activePanels[name] = !activePanels[name];
  }

  function updateIndicatorSetting(key, value) {
    if (!(key in DEFAULT_INDICATOR_SETTINGS)) return;
    const rawValue = typeof value === "string" ? value.trim() : value;
    const nextSettings = normalizeIndicatorSettings({
      ...indicatorSettings,
      [key]: rawValue === "" ? DEFAULT_INDICATOR_SETTINGS[key] : Number(rawValue),
    });
    Object.assign(indicatorSettings, nextSettings);
  }

  function applyIndicatorPreset(presetName) {
    cleanChartMode.value = false;
    const presets = {
      trend: {
        label: "趨勢模板",
        indicators: {
          ma20: true,
          ma50: true,
          ma200: true,
          ema12: false,
          bb: false,
          psar: true,
          keltner: true,
          donchian: true,
          vwap: false,
          ichimoku: true,
          supertrend: true,
        },
        panels: {
          rsi: false,
          aroon: true,
          trix: true,
          williamsr: false,
          mfi: false,
          roc: false,
          bbPercent: false,
          bbWidth: false,
          macd: false,
          stoch: false,
          atr: true,
          cci: false,
          obv: false,
          adx: true,
          cmf: false,
        },
        settings: {
          ma20Period: 20,
          ma50Period: 60,
          ma200Period: 200,
          emaPeriod: 21,
          psarStep: 0.02,
          psarMax: 0.2,
          kcPeriod: 20,
          kcMultiplier: 2,
          donchianPeriod: 20,
          aroonPeriod: 25,
          trixPeriod: 15,
          trixSignal: 9,
          atrPeriod: 14,
          adxPeriod: 14,
          ichimokuConversion: 9,
          ichimokuBase: 26,
          ichimokuSpanB: 52,
          ichimokuDisplacement: 26,
          supertrendPeriod: 10,
          supertrendMultiplier: 3,
        },
      },
      swing: {
        label: "擺盪模板",
        indicators: {
          ma20: true,
          ma50: false,
          ma200: false,
          ema12: true,
          bb: true,
          psar: false,
          keltner: false,
          donchian: true,
          vwap: false,
          ichimoku: false,
          supertrend: false,
        },
        panels: {
          rsi: true,
          aroon: false,
          trix: true,
          williamsr: true,
          mfi: false,
          roc: true,
          bbPercent: true,
          bbWidth: true,
          macd: true,
          stoch: true,
          atr: false,
          cci: true,
          obv: false,
          adx: true,
          cmf: false,
        },
        settings: {
          ma20Period: 10,
          ma50Period: 30,
          emaPeriod: 12,
          bbPeriod: 20,
          bbMultiplier: 2,
          psarStep: 0.02,
          psarMax: 0.2,
          rsiPeriod: 14,
          trixPeriod: 15,
          trixSignal: 9,
          williamsrPeriod: 14,
          rocPeriod: 12,
          donchianPeriod: 20,
          macdFast: 12,
          macdSlow: 26,
          macdSignal: 9,
          stochK: 14,
          stochD: 3,
          cciPeriod: 20,
          adxPeriod: 14,
        },
      },
      volume: {
        label: "量價模板",
        indicators: {
          ma20: true,
          ma50: false,
          ma200: false,
          ema12: false,
          bb: false,
          psar: false,
          keltner: true,
          donchian: false,
          vwap: true,
          ichimoku: false,
          supertrend: true,
        },
        panels: {
          rsi: false,
          aroon: true,
          trix: false,
          williamsr: false,
          mfi: true,
          roc: false,
          bbPercent: false,
          bbWidth: true,
          macd: false,
          stoch: false,
          atr: true,
          cci: false,
          obv: true,
          adx: false,
          cmf: true,
        },
        settings: {
          ma20Period: 20,
          emaPeriod: 21,
          volumeMaPeriod: 20,
          aroonPeriod: 25,
          kcPeriod: 20,
          kcMultiplier: 2,
          atrPeriod: 14,
          mfiPeriod: 14,
          cmfPeriod: 20,
          supertrendPeriod: 10,
          supertrendMultiplier: 2.5,
        },
      },
      clean: {
        label: "清爽模板",
        indicators: { ...DEFAULT_ACTIVE_IND },
        panels: { ...DEFAULT_ACTIVE_PANELS },
        settings: { ...DEFAULT_INDICATOR_SETTINGS },
      },
    };

    const preset = presets[presetName];
    if (!preset) return;

    Object.entries(DEFAULT_ACTIVE_IND).forEach(([key, defaultValue]) => {
      activeInd[key] = preset.indicators?.[key] ?? defaultValue;
    });
    Object.entries(DEFAULT_ACTIVE_PANELS).forEach(([key, defaultValue]) => {
      activePanels[key] = preset.panels?.[key] ?? defaultValue;
    });
    Object.assign(
      indicatorSettings,
      normalizeIndicatorSettings({
        ...indicatorSettings,
        ...(preset.settings || {}),
      }),
    );

    pushNotification({
      icon: "🧩",
      title: "指標模板已套用",
      msg: `${preset.label} / 參數已更新`,
      type: "success",
    });
  }

  function clearIndicators() {
    Object.keys(DEFAULT_ACTIVE_IND).forEach((key) => {
      activeInd[key] = false;
    });
    activeInd.cycleMa = true;
    Object.keys(DEFAULT_ACTIVE_PANELS).forEach((key) => {
      activePanels[key] = false;
    });
    cleanChartMode.value = true;
    pushNotification({
      icon: "🧼",
      title: "已清除指標",
      msg: "目前僅保留周線、月線、季線、年線",
      type: "success",
    });
  }

  function setTool(tool) {
    activeTool.value = tool;
  }

  function addSignal(type) {
    if (!ohlcData.value.length) return;
    const index = Math.min(ohlcData.value.length - 1, Math.floor(ohlcData.value.length * 0.9));
    const drawing = createDrawingEntry({ type, index });
    drawings.value = [...drawings.value, drawing];
    selectedDrawingId.value = drawing.id;
    pushNotification({
      icon: type === "buy" ? "▲" : "▼",
      title: type === "buy" ? "買入標記" : "賣出標記",
      msg: "已標記在最近 K 線",
    });
  }

  function clearDrawings() {
    drawings.value = [];
    selectedDrawingId.value = null;
  }

  function addHorizontalLine(price) {
    const drawing = createDrawingEntry({ type: "hline", price });
    drawings.value = [...drawings.value, drawing];
    selectedDrawingId.value = drawing.id;
    pushNotification({ icon: "─", title: "水平線已加", msg: `@${price.toFixed(2)}` });
  }

  function addDrawing(drawing) {
    const nextDrawing = createDrawingEntry(drawing);
    drawings.value = [...drawings.value, nextDrawing];
    selectedDrawingId.value = nextDrawing.id;

    if (nextDrawing.type === "vline") {
      pushNotification({ icon: "│", title: "垂直線已加", msg: "已標記關鍵事件時間" });
      return;
    }

    if (nextDrawing.type === "trendline") {
      pushNotification({ icon: "╱", title: "趨勢線已加", msg: "已加入分析線段" });
      return;
    }

    if (nextDrawing.type === "arrow") {
      pushNotification({ icon: "↗", title: "箭頭線已加", msg: "已標記趨勢方向" });
      return;
    }

    if (nextDrawing.type === "fib") {
      pushNotification({ icon: "⋮", title: "費波那契已加", msg: "已加入回撤分析" });
      return;
    }

    if (nextDrawing.type === "rect") {
      pushNotification({ icon: "▭", title: "區間框已加", msg: "已標記壓力／支撐區間" });
      return;
    }

    if (nextDrawing.type === "measure") {
      pushNotification({ icon: "⊕", title: "測距尺已加", msg: "已記錄價差與時間距離" });
    }
    if (nextDrawing.type === "note") {
      pushNotification({ icon: "✎", title: "註記已加", msg: "可在屬性面板補上文字與標籤" });
    }
  }

  function focusTickerEvent(eventItem) {
    if (!eventItem?.event_date || !ohlcData.value.length) return;
    const targetDate = String(eventItem.event_date).slice(0, 10);
    const exactIndex = ohlcData.value.findIndex((row) => String(row?.date || "").slice(0, 10) === targetDate);
    const fallbackIndex = ohlcData.value.findLastIndex((row) => String(row?.date || "").slice(0, 10) <= targetDate);
    const targetIndex = exactIndex >= 0 ? exactIndex : fallbackIndex;
    if (targetIndex < 0) return;
    addDrawing({
      type: "vline",
      index: targetIndex,
      label: eventItem.title || eventItem.event_type || "event",
    });
  }

  function removeLastDrawing() {
    if (!drawings.value.length) return;
    const nextDrawings = drawings.value.slice(0, -1);
    drawings.value = nextDrawings;
    selectedDrawingId.value = nextDrawings.at(-1)?.id ?? null;
    pushNotification({ icon: "↶", title: "已復原", msg: "已移除最後一筆繪圖" });
  }

  function selectDrawing(drawingId) {
    selectedDrawingId.value = drawingId || null;
  }

  function removeDrawing(drawingId) {
    if (!drawingId) return;
    const target = drawings.value.find((item) => item.id === drawingId);
    if (!target) return;
    const nextDrawings = drawings.value.filter((item) => item.id !== drawingId);
    drawings.value = nextDrawings;
    selectedDrawingId.value = nextDrawings.at(-1)?.id ?? null;
    pushNotification({ icon: "✕", title: "已移除繪圖", msg: `已刪除 ${target.type}` });
  }

  function updateDrawing(drawingId, patch) {
    if (!drawingId) return;
    drawings.value = drawings.value.map((item) => {
      if (item.id !== drawingId) return item;
      return {
        ...item,
        ...(typeof patch === "function" ? patch(item) : patch),
      };
    });
    selectedDrawingId.value = drawingId;
  }

  function toggleDrawingVisibility(drawingId) {
    if (!drawingId) return;
    drawings.value = drawings.value.map((item) => (
      item.id === drawingId
        ? { ...item, hidden: !item.hidden }
        : item
    ));
    selectedDrawingId.value = drawingId;
  }

  function toggleDrawingLock(drawingId) {
    if (!drawingId) return;
    drawings.value = drawings.value.map((item) => (
      item.id === drawingId
        ? { ...item, locked: !item.locked }
        : item
    ));
    selectedDrawingId.value = drawingId;
  }

  function updateCrosshair(payload) {
    Object.assign(crosshair, payload);
  }

  function hideCrosshair() {
    crosshair.visible = false;
    crosshair.absoluteIndex = null;
    crosshair.canvasX = null;
    crosshair.canvasY = null;
  }

  async function searchSymbols(query) {
    searchQuery.value = query;
    const trimmed = query.trim();
    if (!trimmed) {
      searchResults.value = [];
      searchOpen.value = false;
      return;
    }
    try {
      const results = await dashboardApi.searchSymbols(trimmed);
      searchResults.value = results;
      searchOpen.value = results.length > 0;
    } catch (error) {
      searchResults.value = [];
      searchOpen.value = false;
    }
  }

  function closeSearch() {
    searchOpen.value = false;
  }

  async function submitSearch() {
    const matched = resolveSearchInputTicker(searchQuery.value, searchResults.value);
    const ticker = matched?.ticker || normalizeTicker(searchQuery.value);
    if (!ticker) return;
    searchQuery.value = "";
    searchOpen.value = false;
    await selectTicker(ticker, matched?.name || ticker);
  }

  async function selectSearchResult(result) {
    searchQuery.value = "";
    searchOpen.value = false;
    await selectTicker(result.ticker, result.name || result.ticker);
  }

  function updateBacktestField(key, value) {
    backtestForm[key] = ["capital", "fee", "slippage", "sl", "tp"].includes(key) ? Number(value) : value;
  }

  async function runBacktest() {
    backtestLoading.value = true;
    try {
      const result = await dashboardApi.createBacktestRun({
        ticker: currentTicker.value,
        strategy: backtestForm.strategy,
        start: backtestForm.start,
        end: backtestForm.end,
        interval: currentInterval.value,
        capital: Number(backtestForm.capital),
        position_sizing: backtestForm.positionSizing,
        fee: Number(backtestForm.fee),
        slippage: Number(backtestForm.slippage),
        sl: Number(backtestForm.sl),
        tp: Number(backtestForm.tp),
      });
      backtestResult.value = mapBacktestRun(result);
      await loadBacktestHistory({ ticker: currentTicker.value });
      pushNotification({
        icon: "📊",
        title: "回測完成",
        msg: `${backtestResult.value.strategy} — ${backtestResult.value.totalReturn >= 0 ? "+" : ""}${backtestResult.value.totalReturn.toFixed(2)}%`,
        type: "success",
      });
    } catch (error) {
      backtestResult.value = null;
      pushNotification({ icon: "⚠️", title: "回測失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      backtestLoading.value = false;
    }
  }

  function updateClock() {
    const now = new Date();
    clockTime.value = now.toLocaleString("zh-TW", { hour12: false });
    marketStatus.nyseOpen = isExchangeOpen(now, EXCHANGE_SCHEDULES.nyse);
    marketStatus.nasdaqOpen = isExchangeOpen(now, EXCHANGE_SCHEDULES.nasdaq);
    marketStatus.tseOpen = isExchangeOpen(now, EXCHANGE_SCHEDULES.tse);
    marketStatus.hkOpen = isExchangeOpen(now, EXCHANGE_SCHEDULES.hkex);
  }

  const persistedDashboardState = computed(() => ({
    currentTicker: currentTicker.value,
    currentName: currentName.value,
    currentPeriod: currentPeriod.value,
    currentInterval: currentInterval.value,
    klineDisplayMode: klineDisplayMode.value,
    chartEngineMode: chartEngineMode.value,
    cleanChartMode: cleanChartMode.value,
    activeWatchGroupId: activeWatchGroupId.value,
    activeWorkspacePresetId: activeWorkspacePresetId.value,
    compareTickers: compareTickers.value,
    comparisonMode: comparisonMode.value,
    leftTab: leftTab.value,
    rightTab: rightTab.value,
    workspaceTab: workspaceTab.value,
    institutionalFuturesCommodity: institutionalFuturesCommodity.value,
    institutionalOptionsCommodity: institutionalOptionsCommodity.value,
    institutionalHistoryDays: institutionalHistoryDays.value,
    taiwanChipRangeDays: taiwanChipRangeDays.value,
    activeTool: activeTool.value,
    chartLayout: chartLayout.value,
    screenerFilters: { ...screenerFilters },
    activeInd: { ...activeInd },
    activePanels: { ...activePanels },
    indicatorSettings: { ...indicatorSettings },
  }));

  watch(
    persistedDashboardState,
    (value) => writeDashboardPrefs(value),
    { deep: true },
  );

  onMounted(() => {
    updateClock();
    clockTimer = window.setInterval(updateClock, 1000);
    void bootstrapWorkspace(activeBootstrapPage.value, initialRightTab);
  });

  onBeforeUnmount(() => {
    if (clockTimer) clearInterval(clockTimer);
    if (terminalCacheWriteTimer != null) window.clearTimeout(terminalCacheWriteTimer);
    watchlistPoller.stop();
    alertPoller.stop();
    futoptFallbackPoller.stop();
    dashboardBootstrap.cancelDeferred();
    if (klineAbortController) klineAbortController.abort();
    realtimeUiBatcher.destroy();
    void routeControllers.dispose();
    dashboardRealtime.disconnect();
  });

  return {
    timeframeOptions,
    klineDisplayOptions,
    searchQuery,
    searchResults,
    searchOpen,
    recentTickers,
    watchlistGroups,
    userWatchGroups,
    marketWatchItems,
    activeWatchGroup,
    activeWatchGroupId,
    workspacePresets,
    activeWorkspacePreset,
    activeWorkspacePresetId,
    compareTickers,
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
    chartEngineMode,
    cleanChartMode,
    chartLayout,
    chartLoading,
    loadingMessage,
    futoptRefreshStatus,
    futoptDataStale,
    klineDataOrigin,
    klineCacheSavedAt,
    clearTerminalCache: terminalCache.clear,
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
    calendarEvents,
    tickerEvents,
    tickerNews,
    macroDashboard,
    marketSnapshots,
    marketStrongMovers,
    marketWeakMovers,
    marketActiveLeaders,
    marketSnapshotLoading,
    marketSnapshotError,
    marketBreadthCards,
    fundamentalsDetail,
    fundamentalsSummary,
    taiwanChipDetail,
    taiwanChipSummary,
    taiwanChipHistory,
    taiwanChipRangeDays,
    taiwanChipHistoryLoading,
    taiwanChipHistoryError,
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
    assetLoading,
    assetError,
    assetPerformanceRange,
    assetAccounts,
    assetCashEntries,
    assetTradeEntries,
    assetReconciliationEntries,
    assetPortfolio,
    assetPriceOverrides,
    assetFxRates,
    assetAdjustments,
    assetImportBatches,
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
    assetPortfolioCalculationMetadata,
    assetPortfolioDataQualitySummary,
    assetAccountAllocation,
    assetMarketAllocation,
    assetCurrencyAllocation,
    assetContributors,
    assetPerformanceSummary,
    assetPerformanceCalculationMetadata,
    assetPerformanceDataQualitySummary,
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
    indicatorSnapshot,
    institutionalOverlay,
    backendUrl,
    bootstrapResources: dashboardBootstrap.resources,
    bootstrapWorkspace,
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
    setLeftTab,
    setActiveWatchGroup,
    setRightTab,
    setWorkspaceTab,
    setInstitutionalDate,
    setInstitutionalFuturesCommodity,
    setInstitutionalOptionsCommodity,
    setInstitutionalHistoryDays,
    setTaiwanChipRangeDays: setTaiwanChipRangeDaysAction,
    shiftInstitutionalDate,
    loadInstitutionalData,
    loadInstitutionalInsights,
    loadTaifexStructuredData,
    updateTaifexStructuredQuery,
    resetTaifexStructuredQuery,
    loadEventCalendar,
    loadMacroDashboard,
    loadMarketSnapshots,
    loadTickerIntelligence,
    loadTaiwanChipHistory: loadTaiwanChipHistoryAction,
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
    focusTickerEvent,
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
    createAlertsBatch,
    toggleAlertLog,
    toggleAlertActive,
    deleteAlert,
    updateBacktestField: updateBacktestFieldAction,
    runBacktest: runBacktestAction,
    selectBacktestRun,
    toggleBacktestCompare,
    clearBacktestCompare,
    updateJournalField: updateJournalFieldAction,
    saveJournalEntry: saveJournalEntryAction,
    deleteJournalEntry: deleteJournalEntryAction,
    selectJournalEntry: selectJournalEntryAction,
    resetJournalForm: resetJournalFormAction,
    updateJournalFilter: updateJournalFilterAction,
    applyJournalFilterPreset: applyJournalFilterPresetAction,
    saveJournalFilterPreset: saveJournalFilterPresetAction,
    loadJournalFilterPreset: loadJournalFilterPresetAction,
    deleteJournalFilterPreset: deleteJournalFilterPresetAction,
    addJournalAttachment: addJournalAttachmentAction,
    removeJournalAttachment: removeJournalAttachmentAction,
    startJournalEntry: startJournalEntryAction,
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
    rollbackAssetImportBatch,
    previewAssetJournalImport,
    importAssetJournalEntries,
    recomputeAssetTracking,
    updateScreenerFilter,
    runScreener,
    saveScreenerPreset,
    loadScreenerPreset,
    deleteScreenerPreset,
    fmtPrice,
    fmtVol,
    fmtMktCap,
  };
}

