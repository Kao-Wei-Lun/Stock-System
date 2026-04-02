import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import {
  DEFAULT_INDICATOR_SETTINGS,
  buildIndicatorSnapshot,
  normalizeIndicatorSettings,
} from "../utils/indicatorUtils";
import { createDashboardApi } from "../api/dashboardApi";
import { fmtMktCap, fmtPrice, fmtVol } from "../utils/formatters";
import {
  buildWorkspacePayload,
  clearLegacyWorkspacePresets,
  normalizeWorkspaceRecord,
  readLegacyWorkspacePresets,
  toWorkspaceSaveRequest,
} from "../utils/workspacePresets";

const TIMEFRAME_OPTIONS = [
  { tf: "5d", iv: "1h", label: "5D" },
  { tf: "1mo", iv: "1d", label: "1M" },
  { tf: "3mo", iv: "1d", label: "3M" },
  { tf: "1y", iv: "1d", label: "1Y" },
  { tf: "2y", iv: "1d", label: "2Y" },
  { tf: "5y", iv: "1d", label: "5Y" },
  { tf: "10y", iv: "1d", label: "10Y" },
  { tf: "max", iv: "1d", label: "MAX" },
];
const KLINE_DISPLAY_OPTIONS = [
  { key: "day", label: "日K" },
  { key: "week", label: "週K" },
  { key: "month", label: "月K" },
  { key: "quarter", label: "季K" },
];

const COMPARE_COLOR_PALETTE = ["#ffd166", "#ff8c42", "#9b6dff", "#00d4ff", "#ff4d6a"];
const DASHBOARD_PREFS_KEY = "quantvision.dashboard.prefs.v1";
const CHART_LAYOUT_OPTIONS = ["single", "double", "quad"];
const MARKET_GROUP_NAME = "全球大盤";
const WORKSPACE_TAB_OPTIONS = ["chart", "institutional", "events", "macro", "screener"];
const INSTITUTIONAL_HISTORY_OPTIONS = [10, 20, 30, 60, 90];
const FUTURES_OVERLAY_TICKER_MAP = {
  "^TWII": "臺股期貨",
  "0050.TW": "臺股期貨",
  "^TWOII": "櫃買指數期貨",
};
const FUTURES_DEFAULT_SPOT_TICKER_MAP = {
  "臺股期貨": "^TWII",
  "小型臺指期貨": "^TWII",
  "微型臺指期貨": "^TWII",
  "臺灣永續期貨": "^TWII",
  "臺灣生技期貨": "^TWII",
  "櫃買指數期貨": "^TWOII",
};
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

function resolveTimeframeInterval(period, interval) {
  return String(period || "").toLowerCase() === "5d" ? "1h" : "1d";
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

export function normalizeTicker(ticker) {
  const raw = (ticker || "").trim().toUpperCase();
  if (!raw || raw.startsWith("^") || raw.includes(".") || raw.includes("-") || raw.includes("=")) return raw;
  if (!/^[A-Z]+$/.test(raw)) return `${raw}.TW`;
  return raw;
}

function inferMarketFromTicker(ticker) {
  const normalized = normalizeTicker(ticker);
  if (normalized.endsWith(".TW") || normalized.endsWith(".TWO")) return "TW";
  if (normalized.endsWith(".HK")) return "HK";
  if (normalized.startsWith("^")) return "INDEX";
  return "US";
}

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
  return byStockCode || null;
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

export function useDashboard() {
  const apiBase = getApiBase();
  const wsUrl = `${getWsBase()}/ws`;
  const backendUrl = import.meta.env.DEV ? getBackendTarget() : window.location.origin;
  const dashboardApi = createDashboardApi({ baseUrl: apiBase });
  const storedPrefs = readDashboardPrefs();
  const storedTimeframe = TIMEFRAME_OPTIONS.find(
    (option) => option.tf === storedPrefs.currentPeriod,
  );
  const initialTool = TOOL_OPTIONS.includes(storedPrefs.activeTool) ? storedPrefs.activeTool : "cursor";
  const initialComparisonMode = storedPrefs.comparisonMode === "price" ? "price" : "percent";
  const initialChartLayout = CHART_LAYOUT_OPTIONS.includes(storedPrefs.chartLayout) ? storedPrefs.chartLayout : "single";
  const initialKlineDisplayMode = normalizeKlineDisplayMode(storedPrefs.klineDisplayMode);
  const initialWorkspaceTab = WORKSPACE_TAB_OPTIONS.includes(storedPrefs.workspaceTab) ? storedPrefs.workspaceTab : "chart";

  const timeframeOptions = TIMEFRAME_OPTIONS;
  const klineDisplayOptions = KLINE_DISPLAY_OPTIONS;
  const searchQuery = ref("");
  const searchResults = ref([]);
  const searchOpen = ref(false);
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
      })),
    ),
  );
  const watchlistLoading = ref(true);
  const watchlistError = ref(false);
  const compareSeries = computed(() =>
    rawCompareSeries.value
      .map((series) => {
        const data = filterRowsForDisplayPeriod(
          aggregateOhlcRows(series.data || [], klineDisplayMode.value),
          currentPeriod.value,
          klineDisplayMode.value,
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
  const rightTab = ref(["indicators", "alerts", "backtest", "journal", "db"].includes(storedPrefs.rightTab) ? storedPrefs.rightTab : "indicators");
  const workspaceTab = ref(initialWorkspaceTab);
  const currentTicker = ref(normalizeTicker(storedPrefs.currentTicker || "AAPL"));
  const currentName = ref("載入中...");
  const currentPeriod = ref(storedTimeframe?.tf || "1y");
  const currentInterval = ref(resolveTimeframeInterval(storedTimeframe?.tf || "1y", storedTimeframe?.iv || "1d"));
  const klineDisplayMode = ref(initialKlineDisplayMode);
  const cleanChartMode = ref(Boolean(storedPrefs.cleanChartMode));
  const chartLayout = ref(initialChartLayout);
  const chartLoading = ref(true);
  const loadingMessage = ref("正在載入資料...");
  const rawOhlcData = ref([]);
  const drawings = ref([]);
  const selectedDrawingId = ref(null);
  const workspacePresets = ref([]);
  const activeWorkspacePresetId = ref(storedPrefs.activeWorkspacePresetId || null);
  const alerts = ref([]);
  const alertTriggerLogs = ref({});
  const alertLogLoading = ref({});
  const expandedAlertLogId = ref(null);
  const localNotifications = ref([]);
  const remoteNotifications = ref([]);
  const notifications = computed(() =>
    [...localNotifications.value, ...remoteNotifications.value].sort((left, right) => {
      const leftTime = Date.parse(left?.createdAt || "") || 0;
      const rightTime = Date.parse(right?.createdAt || "") || 0;
      return rightTime - leftTime;
    }),
  );
  const wsConnected = ref(false);
  const latency = ref("—");
  const lastUpdate = ref("—");
  const clockTime = ref("—");
  const dbStats = ref(null);
  const dbStatsLoading = ref(false);
  const dbStatsError = ref("");
  const institutionalDate = ref(new Date().toISOString().slice(0, 10));
  const institutionalData = ref(null);
  const institutionalLoading = ref(false);
  const institutionalError = ref("");
  const institutionalInsights = ref(null);
  const institutionalInsightsLoading = ref(false);
  const institutionalInsightsError = ref("");
  const initialInstitutionalHistoryDays = INSTITUTIONAL_HISTORY_OPTIONS.includes(Number(storedPrefs.institutionalHistoryDays))
    ? Number(storedPrefs.institutionalHistoryDays)
    : 30;
  const institutionalFuturesCommodity = ref(storedPrefs.institutionalFuturesCommodity || "");
  const institutionalOptionsCommodity = ref(storedPrefs.institutionalOptionsCommodity || "");
  const institutionalHistoryDays = ref(initialInstitutionalHistoryDays);
  const syncingCurrent = ref(false);
  const syncingAll = ref(false);
  const alertModalOpen = ref(false);
  const activeTool = ref(initialTool);
  const backtestResult = ref(null);
  const backtestHistory = ref([]);
  const backtestLoading = ref(false);
  const journalEntries = ref([]);
  const journalStats = ref(null);
  const journalLoading = ref(false);
  const calendarEvents = ref([]);
  const tickerEvents = ref([]);
  const tickerNews = ref([]);
  const macroDashboard = ref({ items: [], summary: {}, snapshot_date: null });
  const fundamentalsDetail = ref(null);
  const fundamentalsSummary = ref(null);
  const taiwanChipDetail = ref(null);
  const taiwanChipSummary = ref(null);
  const screenerResults = ref({ items: [], total: 0, filters: {}, market_context: null, generated_at: null });
  const screenerPresets = ref([]);
  const screenerLoading = ref(false);
  const screenerFilters = reactive({
    search: "",
    market: "ALL",
    sector: "",
    min_price: "",
    max_price: "",
    min_volume_ratio: "",
    min_setup_quality: "",
    decision_verdict: "any",
    max_pe_ratio: "",
    min_dividend_yield: "",
    near_52w_high_pct: "",
    upcoming_event_days: "",
    chip_bias: "any",
    ma_alignment: "any",
    sort_by: "score",
    limit: 50,
    ...(storedPrefs.screenerFilters || {}),
  });
  const journalFilterScope = ref("ticker");
  const journalFilters = reactive({
    market: "",
    strategy_code: "",
    tag: "",
    search: "",
  });

  const quote = reactive({
    price: null,
    open: null,
    high: null,
    low: null,
    prev_close: null,
    volume: null,
    market_cap: null,
    change: 0,
    change_pct: 0,
    name: "載入中...",
    source: null,
    quote_type: null,
    is_delayed: true,
    quote_timestamp: null,
    synced_at: null,
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
  const alertForm = reactive({
    ticker: "AAPL",
    type: "price",
    cond: "大於",
    value: "",
    prefill_hint: "",
    context_tags: [],
    context_source: "",
    snapshot_price: null,
    snapshot_source: "",
    snapshot_timestamp: "",
  });
  const backtestForm = reactive({
    strategy: "MA 黃金/死亡交叉",
    start: "2022-01-01",
    end: new Date().toISOString().slice(0, 10),
    capital: 100000,
    fee: 0.1,
    slippage: 0,
    sl: 5,
    tp: 10,
  });
  const journalForm = reactive({
    id: null,
    ticker: "AAPL",
    market: inferMarketFromTicker("AAPL"),
    direction: "long",
    strategy_code: "",
    entry_time: getCurrentDateTimeInputValue(),
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
  });

  const ohlcData = computed(() => filterRowsForDisplayPeriod(
    aggregateOhlcRows(rawOhlcData.value, klineDisplayMode.value),
    currentPeriod.value,
    klineDisplayMode.value,
  ));
  const institutionalOverlay = computed(() => {
    const mappedCommodity = FUTURES_OVERLAY_TICKER_MAP[currentTicker.value];
    if (!mappedCommodity) return null;

    const insightMatch = institutionalInsights.value?.futures_commodity === mappedCommodity
      ? institutionalInsights.value
      : null;
    const dataMatch = institutionalData.value?.default_futures_commodity === mappedCommodity
      ? institutionalData.value
      : null;
    const futuresCosts = insightMatch?.cost_estimates?.futures || dataMatch?.cost_estimates?.futures || null;
    if (!futuresCosts) return null;

    const bandLow = futuresCosts.band_low == null ? Number.NaN : Number(futuresCosts.band_low);
    const bandHigh = futuresCosts.band_high == null ? Number.NaN : Number(futuresCosts.band_high);
    const institutionPrice = futuresCosts.institution_estimate?.price == null
      ? Number.NaN
      : Number(futuresCosts.institution_estimate.price);
    const retailPrice = futuresCosts.retail_estimate?.price == null
      ? Number.NaN
      : Number(futuresCosts.retail_estimate.price);
    const values = [bandLow, bandHigh, institutionPrice, retailPrice].filter((value) => Number.isFinite(value));
    if (!values.length) return null;

    const spotTicker = FUTURES_DEFAULT_SPOT_TICKER_MAP[mappedCommodity];
    const spot = (institutionalData.value?.spot_reference || []).find((item) => item.ticker === spotTicker) || null;
    const spotPrice = spot?.price == null ? Number.NaN : Number(spot.price);
    const basis = Number.isFinite(spotPrice) && Number.isFinite(institutionPrice)
      ? institutionPrice - spotPrice
      : null;

    return {
      commodity: mappedCommodity,
      label: `${mappedCommodity} 主力成本帶`,
      bandLow: Number.isFinite(bandLow) ? bandLow : null,
      bandHigh: Number.isFinite(bandHigh) ? bandHigh : null,
      institutionPrice: Number.isFinite(institutionPrice) ? institutionPrice : null,
      retailPrice: Number.isFinite(retailPrice) ? retailPrice : null,
      spotTicker: spot?.ticker || null,
      spotLabel: spot?.label || null,
      spotPrice: Number.isFinite(spotPrice) ? spotPrice : null,
      basis,
      basisPct: Number.isFinite(basis) && spotPrice
        ? (basis / spotPrice) * 100
        : null,
      resolvedDate: insightMatch?.resolved_date || dataMatch?.resolved_date || null,
    };
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

  let ws = null;
  let wsReconnectTimer = null;
  let clockTimer = null;
  let watchlistTimer = null;
  let alertPollingTimer = null;

  function pushNotification({ icon, title, msg, type = "" }) {
    const id = `${Date.now()}-${Math.random()}`;
    const createdAt = new Date().toISOString();
    localNotifications.value = [
      ...localNotifications.value,
      {
        id,
        icon,
        title,
        msg,
        type,
        level: type || "info",
        category: "session",
        read: false,
        persisted: false,
        ticker: null,
        source: "session",
        createdAt,
        time: new Date(createdAt).toLocaleTimeString("zh-TW"),
      },
    ];
    window.setTimeout(() => dismissNotification(id), 6000);
  }

  async function dismissNotification(id) {
    const remoteTarget = remoteNotifications.value.find((item) => item.id === id);
    if (remoteTarget?.remoteId != null) {
      try {
        const record = await dashboardApi.markNotificationRead(remoteTarget.remoteId);
        remoteNotifications.value = remoteNotifications.value.map((item) =>
          item.id === id ? mapRemoteNotification(record) : item,
        );
      } catch (error) {
        console.error(error);
      }
      return;
    }
    localNotifications.value = localNotifications.value.filter((item) => item.id !== id);
  }

  async function apiFetch(path, options = {}) {
    const {
      retries = 0,
      retryDelayMs = 1200,
      ...fetchOptions
    } = options;

    let attempt = 0;
    let lastError = null;
    while (attempt <= retries) {
      const start = Date.now();
      try {
        const response = await fetch(`${apiBase}${path}`, fetchOptions);
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
        const isNetworkError = error instanceof TypeError;
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

  function mapAlertRecord(alert) {
    return {
      ...alert,
      cond: alert.condition || alert.cond,
    };
  }

  function mapAlertTriggerLog(record) {
    const payload = record?.payload || {};
    const evaluation = payload.evaluation || {};
    return {
      ...record,
      trigger_value: record?.trigger_value ?? evaluation.current_value ?? null,
      threshold_value: record?.threshold_value ?? evaluation.threshold_value ?? null,
      payload,
    };
  }

  function pruneAlertArtifacts(nextAlerts) {
    const validIds = new Set((nextAlerts || []).map((item) => String(item.id)));
    alertTriggerLogs.value = Object.fromEntries(
      Object.entries(alertTriggerLogs.value).filter(([key]) => validIds.has(String(key))),
    );
    alertLogLoading.value = Object.fromEntries(
      Object.entries(alertLogLoading.value).filter(([key]) => validIds.has(String(key))),
    );
    if (expandedAlertLogId.value != null && !validIds.has(String(expandedAlertLogId.value))) {
      expandedAlertLogId.value = null;
    }
  }

  function alertRequiresNumericValue(type, condition) {
    const normalizedType = String(type || "").toLowerCase();
    const normalizedCondition = String(condition || "").toLowerCase();
    if (normalizedType === "market_risk") return false;
    if (normalizedType !== "macd") return true;
    return !["上穿", "下穿", "cross_up", "cross_down"].includes(normalizedCondition);
  }

  function defaultAlertCondition(type) {
    if (String(type || "").toLowerCase() === "market_risk") return "high";
    return String(type || "").toLowerCase() === "macd" ? "上穿" : "大於";
  }

  function resetAlertForm() {
    alertForm.ticker = currentTicker.value || "AAPL";
    alertForm.ticker = normalizeTicker(alertForm.ticker);
    alertForm.type = "price";
    alertForm.cond = "大於";
    alertForm.value = "";
    alertForm.prefill_hint = "";
    alertForm.context_tags = [];
    alertForm.context_source = "";
    alertForm.snapshot_price = null;
    alertForm.snapshot_source = "";
    alertForm.snapshot_timestamp = "";
  }

  function formatAlertConditionLabel(condition) {
    const normalizedCondition = String(condition || "").toLowerCase();
    const labels = {
      gt: "大於",
      lt: "小於",
      eq: "等於",
      "大於": "大於",
      "小於": "小於",
      "等於": "等於",
      cross_up: "黃金交叉",
      cross_down: "死亡交叉",
      上穿: "黃金交叉",
      下穿: "死亡交叉",
      high: "進入高風險",
      medium_or_high: "進入中風險以上",
      risk_off: "進入 risk-off",
      offensive: "進入偏進攻",
    };
    return labels[normalizedCondition] || labels[String(condition || "")] || String(condition || "");
  }

  function mapRemoteNotification(item) {
    const iconByCategory = {
      alert: "⚡",
      system: "ℹ",
    };
    const iconByLevel = {
      warning: "⚠️",
      error: "⛔",
      success: "✅",
      info: "ℹ",
    };
    const quote = item.payload?.quote || {};
    const rawTicker = quote.ticker || item.payload?.ticker || null;
    const isMacroNotification = String(rawTicker || "").toUpperCase() === "MARKET" || Boolean(quote.macro_summary);
    const contextTags = Array.isArray(item.payload?.context_tags) ? item.payload.context_tags.filter(Boolean).slice(0, 4) : [];
    return {
      id: `remote-${item.id}`,
      remoteId: item.id,
      icon: iconByCategory[item.category] || iconByLevel[item.level] || "ℹ",
      title: item.title,
      msg: item.message,
      type: item.level || "",
      level: item.level || "info",
      category: item.category || "system",
      read: Boolean(item.read_at),
      persisted: true,
      source: quote.source || item.payload?.source || "local_db",
      ticker: isMacroNotification ? null : rawTicker,
      workspaceTarget: isMacroNotification ? "macro" : null,
      contextSource: item.payload?.context_source || "",
      contextTags,
      triggerValue: item.payload?.trigger_value ?? null,
      thresholdValue: item.payload?.threshold_value ?? null,
      payload: item.payload || {},
      relatedEntityType: item.related_entity_type || null,
      relatedEntityId: item.related_entity_id || null,
      createdAt: item.created_at || null,
      time: formatQuoteTimestampLabel(item.created_at),
    };
  }

  function mapBacktestRun(item) {
    if (!item) return null;
    return {
      ...item,
      id: item.id,
      strategy: item.strategy || item.strategy_name || item.strategyKey || item.strategy_key,
      strategy_key: item.strategy_key || item.strategyKey || "",
      start: item.start || item.start_date || "",
      end: item.end || item.end_date || "",
      capital: Number(item.capital ?? item.initial_capital ?? 0),
      finalEquity: Number(item.finalEquity ?? item.final_equity ?? 0),
      totalReturn: Number(item.totalReturn ?? item.total_return_pct ?? 0),
      sellTrades: Number(item.sellTrades ?? item.trade_count ?? 0),
      winRate: Number(item.winRate ?? item.win_rate_pct ?? 0),
      maxDrawdown: Number(item.maxDrawdown ?? item.max_drawdown_pct ?? 0),
      sharpe: Number(item.sharpe ?? item.sharpe_ratio ?? 0),
      bars: Number(item.bars ?? item.bars_count ?? 0),
      feeRate: Number(item.feeRate ?? item.fee_rate ?? 0),
      slippageRate: Number(item.slippageRate ?? item.slippage_rate ?? 0),
      stopLoss: item.stopLoss ?? item.stop_loss_pct ?? null,
      takeProfit: item.takeProfit ?? item.take_profit_pct ?? null,
      trades: Array.isArray(item.trades) ? item.trades : [],
      equity_curve: Array.isArray(item.equity_curve) ? item.equity_curve : [],
      created_at: item.created_at || null,
    };
  }

  function mapJournalEntry(item) {
    if (!item) return null;
    return {
      ...item,
      id: item.id,
      ticker: normalizeTicker(item.ticker),
      tags: Array.isArray(item.tags) ? item.tags : [],
      attachments: Array.isArray(item.attachments) ? item.attachments : [],
      result: item.result || {},
    };
  }

  function applyJournalEntryToForm(entry = null) {
    const normalized = mapJournalEntry(entry);
    journalForm.id = normalized?.id ?? null;
    journalForm.ticker = normalized?.ticker || currentTicker.value;
    journalForm.market = normalized?.market || inferMarketFromTicker(normalized?.ticker || currentTicker.value);
    journalForm.direction = normalized?.direction || "long";
    journalForm.strategy_code = normalized?.strategy_code || "";
    journalForm.entry_time = normalized?.entry_time ? String(normalized.entry_time).slice(0, 16) : getCurrentDateTimeInputValue();
    journalForm.entry_price = normalized?.entry_price ?? quote.price ?? "";
    journalForm.exit_time = normalized?.exit_time ? String(normalized.exit_time).slice(0, 16) : "";
    journalForm.exit_price = normalized?.exit_price ?? "";
    journalForm.size = normalized?.size ?? 1;
    journalForm.stop_loss = normalized?.stop_loss ?? "";
    journalForm.take_profit = normalized?.take_profit ?? "";
    journalForm.entry_reason = normalized?.entry_reason || "";
    journalForm.exit_reason = normalized?.exit_reason || "";
    journalForm.emotion_tag = normalized?.emotion_tag || "";
    journalForm.review_notes = normalized?.review_notes || "";
    journalForm.tags_text = (normalized?.tags || []).join(", ");
    journalForm.attachment_path = "";
    journalForm.attachment_type = "";
    journalForm.attachments = Array.isArray(normalized?.attachments) ? [...normalized.attachments] : [];
  }

  function buildJournalQueryOptions() {
    return {
      ticker: journalFilterScope.value === "ticker" ? currentTicker.value : undefined,
      market: journalFilters.market || undefined,
      strategy_code: journalFilters.strategy_code || undefined,
      tag: journalFilters.tag || undefined,
      search: journalFilters.search || undefined,
      limit: 50,
    };
  }

  function buildScreenerPayload() {
    const payload = {};
    Object.entries(screenerFilters).forEach(([key, value]) => {
      if (value === "" || value == null) return;
      if (["min_price", "max_price", "min_volume_ratio", "min_setup_quality", "max_pe_ratio", "min_dividend_yield", "near_52w_high_pct", "upcoming_event_days", "limit"].includes(key)) {
        payload[key] = Number(value);
        return;
      }
      payload[key] = value;
    });
    return payload;
  }

  function applyScreenerFilters(filters = {}) {
    Object.keys(screenerFilters).forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(filters, key)) {
        screenerFilters[key] = filters[key] ?? "";
      }
    });
  }

  function normalizeMacroDashboard(payload) {
    return {
      items: Array.isArray(payload?.items) ? payload.items : [],
      summary: payload?.summary || {},
      snapshot_date: payload?.snapshot_date || null,
    };
  }

  async function loadAlerts({ silent = true } = {}) {
    try {
      const response = await dashboardApi.listAlerts();
      const nextAlerts = Array.isArray(response?.items) ? response.items.map((item) => mapAlertRecord(item)) : [];
      alerts.value = nextAlerts;
      pruneAlertArtifacts(nextAlerts);
    } catch (error) {
      console.error(error);
      if (!silent) {
        pushNotification({ icon: "⚠️", title: "警報載入失敗", msg: "請稍後再試", type: "error" });
      }
    }
  }

  async function loadNotifications({ silent = true } = {}) {
    try {
      const response = await dashboardApi.listNotifications({ unreadOnly: false, limit: 50 });
      remoteNotifications.value = Array.isArray(response?.items)
        ? response.items.map((item) => mapRemoteNotification(item))
        : [];
    } catch (error) {
      console.error(error);
      if (!silent) {
        pushNotification({ icon: "⚠️", title: "通知載入失敗", msg: "請稍後再試", type: "error" });
      }
    }
  }

  async function setNotificationRead(notificationId, read) {
    if (!notificationId) return;
    const target = remoteNotifications.value.find((item) => item.id === notificationId);
    if (!target?.remoteId) return;
    try {
      const record = await dashboardApi.setNotificationReadState(target.remoteId, read);
      remoteNotifications.value = remoteNotifications.value.map((item) =>
        item.id === notificationId ? mapRemoteNotification(record) : item,
      );
    } catch (error) {
      console.error(error);
      pushNotification({
        icon: "!",
        title: read ? "Mark read failed" : "Mark unread failed",
        msg: error.message || "Please try again later",
        type: "error",
      });
    }
  }

  async function loadBacktestHistory({ ticker = currentTicker.value, silent = true } = {}) {
    try {
      const response = await dashboardApi.listBacktestRuns({ ticker, limit: 20 });
      backtestHistory.value = Array.isArray(response?.items)
        ? response.items.map((item) => mapBacktestRun(item)).filter(Boolean)
        : [];
    } catch (error) {
      console.error(error);
      if (!silent) {
        pushNotification({ icon: "⚠️", title: "回測紀錄載入失敗", msg: "請稍後再試", type: "error" });
      }
    }
  }

  async function selectBacktestRun(runId) {
    if (!runId) return;
    backtestLoading.value = true;
    try {
      const record = await dashboardApi.getBacktestRun(runId);
      backtestResult.value = mapBacktestRun(record);
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "回測紀錄讀取失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      backtestLoading.value = false;
    }
  }

  async function loadJournalData({ silent = true } = {}) {
    journalLoading.value = !silent;
    try {
      const options = buildJournalQueryOptions();
      const [entriesResponse, statsResponse] = await Promise.all([
        dashboardApi.listJournalTrades(options),
        dashboardApi.getJournalTradeStats(options),
      ]);
      journalEntries.value = Array.isArray(entriesResponse?.items)
        ? entriesResponse.items.map((item) => mapJournalEntry(item)).filter(Boolean)
        : [];
      journalStats.value = statsResponse || null;
    } catch (error) {
      console.error(error);
      if (!silent) {
        pushNotification({ icon: "⚠️", title: "交易日誌載入失敗", msg: "請稍後再試", type: "error" });
      }
    } finally {
      journalLoading.value = false;
    }
  }

  async function loadEventCalendar(forceRefresh = false) {
    try {
      const response = await dashboardApi.listEventCalendar({ days: 30, limit: 120, refresh: forceRefresh });
      calendarEvents.value = Array.isArray(response?.items) ? response.items : [];
    } catch (error) {
      console.error(error);
      if (forceRefresh) {
        pushNotification({ icon: "⚠️", title: "事件日曆載入失敗", msg: error.message || "請稍後再試", type: "error" });
      }
    }
  }

  async function loadMacroDashboard(forceRefresh = false) {
    try {
      const response = await dashboardApi.getMacroDashboard({ refresh: forceRefresh });
      macroDashboard.value = normalizeMacroDashboard(response);
    } catch (error) {
      console.error(error);
      if (forceRefresh) {
        pushNotification({ icon: "⚠️", title: "宏觀儀表板載入失敗", msg: error.message || "請稍後再試", type: "error" });
      }
    }
  }

  async function loadTickerIntelligence(ticker = currentTicker.value, forceRefresh = false) {
    const normalizedTicker = normalizeTicker(ticker);
    try {
      const [eventsResponse, newsResponse, fundamentalsResponse, chipsResponse] = await Promise.all([
        dashboardApi.getTickerEvents(normalizedTicker, { refresh: forceRefresh }),
        dashboardApi.getTickerNews(normalizedTicker, { limit: 10, refresh: forceRefresh }),
        dashboardApi.getFundamentals(normalizedTicker, { refresh: forceRefresh }),
        dashboardApi.getTaiwanChips(normalizedTicker, { refresh: forceRefresh }).catch(() => null),
      ]);
      tickerEvents.value = Array.isArray(eventsResponse?.items) ? eventsResponse.items : [];
      tickerNews.value = Array.isArray(newsResponse?.items) ? newsResponse.items : [];
      fundamentalsDetail.value = fundamentalsResponse?.detail || null;
      fundamentalsSummary.value = fundamentalsResponse?.summary || null;
      taiwanChipDetail.value = chipsResponse?.detail || null;
      taiwanChipSummary.value = chipsResponse?.summary || null;
    } catch (error) {
      console.error(error);
      if (forceRefresh) {
        pushNotification({ icon: "⚠️", title: "標的資訊載入失敗", msg: error.message || "請稍後再試", type: "error" });
      }
    }
  }

  async function loadScreenerPresets() {
    try {
      const response = await dashboardApi.listScreenerPresets();
      screenerPresets.value = Array.isArray(response?.items) ? response.items : [];
    } catch (error) {
      console.error(error);
      screenerPresets.value = [];
    }
  }

  function updateScreenerFilter(key, value) {
    if (!Object.prototype.hasOwnProperty.call(screenerFilters, key)) return;
    screenerFilters[key] = value;
  }

  async function runScreener() {
    screenerLoading.value = true;
    try {
      const payload = await dashboardApi.runScreener({ filters: buildScreenerPayload() });
      screenerResults.value = payload || { items: [], total: 0, filters: {}, market_context: null, generated_at: null };
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "選股器執行失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      screenerLoading.value = false;
    }
  }

  async function saveScreenerPreset(name) {
    const trimmed = String(name || "").trim();
    if (!trimmed) return;
    try {
      await dashboardApi.createScreenerPreset({
        name: trimmed,
        description: "由選股器工作區儲存",
        filters: buildScreenerPayload(),
      });
      await loadScreenerPresets();
      pushNotification({ icon: "💾", title: "選股模板已儲存", msg: trimmed, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "選股模板儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  function loadScreenerPreset(preset) {
    if (!preset?.filters) return;
    applyScreenerFilters(preset.filters);
    pushNotification({ icon: "🧭", title: "已載入選股模板", msg: preset.name || "preset", type: "success" });
    void runScreener();
  }

  async function deleteScreenerPreset(presetId) {
    if (!presetId || String(presetId).startsWith("builtin-")) return;
    try {
      await dashboardApi.deleteScreenerPreset(presetId);
      await loadScreenerPresets();
      pushNotification({ icon: "🗑", title: "選股模板已刪除", msg: String(presetId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "選股模板刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
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
    quote.price = data.price ?? null;
    quote.open = data.open ?? null;
    quote.high = data.high ?? null;
    quote.low = data.low ?? null;
    quote.prev_close = data.prev_close ?? null;
    quote.volume = data.volume ?? null;
    quote.market_cap = data.market_cap ?? null;
    quote.change = data.change ?? 0;
    quote.change_pct = data.change_pct ?? 0;
    quote.name = data.name || currentName.value;
    quote.source = data.source ?? quote.source ?? null;
    quote.quote_type = data.quote_type ?? quote.quote_type ?? null;
    quote.is_delayed = data.is_delayed ?? true;
    quote.quote_timestamp = data.quote_timestamp ?? null;
    quote.synced_at = data.synced_at ?? null;
    if (data.name) currentName.value = data.name;
    lastUpdate.value = formatQuoteTimestampLabel(data.quote_timestamp || data.synced_at);
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
      name: currentName.value,
      source: null,
      quote_type: null,
      is_delayed: true,
      quote_timestamp: null,
      synced_at: null,
    });
  }

  function handleRealtimeQuote(message) {
    const data = message.data;
    if (data.ticker !== currentTicker.value && data.ticker !== normalizeTicker(currentTicker.value)) return;
    applyQuote(data);
    if (rawOhlcData.value.length > 0) {
      const last = rawOhlcData.value[rawOhlcData.value.length - 1];
      const today = new Date().toISOString().slice(0, 10);
      if (last.date === today || last.date.startsWith(today)) {
        const updated = {
          ...last,
          close: data.price,
          high: data.high && data.high > last.high ? data.high : last.high,
          low: data.low && data.low < last.low ? data.low : last.low,
        };
          rawOhlcData.value = [...rawOhlcData.value.slice(0, -1), updated];
        }
      }
    }

  function wsSend(payload) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(payload));
  }

  function connectWs() {
    if (ws && ws.readyState < 2) return;
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
      wsReconnectTimer = null;
      wsConnected.value = true;
      wsSend({ action: "subscribe", ticker: normalizeTicker(currentTicker.value) });
    };
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "quote") handleRealtimeQuote(message);
      } catch (error) {
        console.error(error);
      }
    };
    ws.onclose = () => {
      wsConnected.value = false;
      wsReconnectTimer = window.setTimeout(connectWs, 5000);
    };
    ws.onerror = () => {
      wsConnected.value = false;
    };
  }

  async function loadWatchlist() {
    watchlistLoading.value = true;
    watchlistError.value = false;
    try {
      const payload = await apiFetch("/api/watchlist", { retries: 12, retryDelayMs: 1500 });
      watchlistGroups.value = payload.groups || [];
      const currentUserGroups = watchlistGroups.value.filter((group) => group.name !== MARKET_GROUP_NAME);
      if (
        !activeWatchGroupId.value
        || !currentUserGroups.some((group) => group.id === activeWatchGroupId.value)
      ) {
        activeWatchGroupId.value = currentUserGroups[0]?.id ?? null;
      }
      const current = watchlist.value.find((item) => item.ticker === currentTicker.value);
      if (current) currentName.value = current.name || current.ticker;
    } catch (error) {
      watchlistError.value = true;
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

  async function createWatchGroup(name) {
    const trimmed = (name || "").trim();
    if (!trimmed) return;
    try {
      const group = await apiFetch("/api/watchlist/groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed }),
      });
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
    const trimmed = (name || "").trim();
    if (!groupId || !trimmed) return;
    try {
      await apiFetch(`/api/watchlist/groups/${groupId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed }),
      });
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
      await apiFetch(`/api/watchlist/groups/${groupId}`, { method: "DELETE" });
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
      const added = await apiFetch("/api/watchlist/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_id: targetGroupId, ticker: normalized, tags }),
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

  async function removeTickerFromWatchlist(itemId) {
    if (!itemId) return;
    try {
      await apiFetch(`/api/watchlist/items/${itemId}`, { method: "DELETE" });
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
      await apiFetch(`/api/watchlist/groups/${groupId}/items/order`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_ids: itemIds }),
      });
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

  async function loadComparisonSeries(targetTickers = compareTickers.value) {
    const normalizedTickers = [...new Set(
      (targetTickers || [])
        .map((ticker) => normalizeTicker(ticker))
        .filter((ticker) => ticker && ticker !== normalizeTicker(currentTicker.value)),
    )].slice(0, 5);

    compareTickers.value = normalizedTickers;

    if (!normalizedTickers.length) {
      rawCompareSeries.value = [];
      return;
    }
    const resolvedInterval = resolveTimeframeInterval(currentPeriod.value, currentInterval.value);
    const fetchPeriod = getExpandedFetchPeriod(currentPeriod.value, klineDisplayMode.value);

    const results = await Promise.allSettled(
      normalizedTickers.map(async (ticker, index) => {
        const payload = await apiFetch(
          `/api/kline/${ticker}?period=${fetchPeriod}&interval=${resolvedInterval}`,
        );
        const data = payload.data || [];
        const firstClose = data.find((row) => row.close != null)?.close ?? null;
        const lastClose = data.length ? data[data.length - 1].close : null;
        const changePct = firstClose && lastClose ? ((lastClose - firstClose) / firstClose) * 100 : 0;

        return {
          ticker,
          name: getDisplayNameForTicker(ticker),
          color: COMPARE_COLOR_PALETTE[index % COMPARE_COLOR_PALETTE.length],
          changePct,
          data,
        };
      }),
    );

    rawCompareSeries.value = results
      .filter((result) => result.status === "fulfilled" && result.value.data.length)
      .map((result) => result.value);
  }

  async function addCompareTicker(ticker) {
    const normalized = normalizeTicker(ticker);
    if (!normalized) return;
    if (normalized === normalizeTicker(currentTicker.value)) {
      pushNotification({
        icon: "ℹ",
        title: "主圖已是這檔股票",
        msg: normalized,
      });
      return;
    }
    if (compareTickers.value.includes(normalized)) return;
    if (compareTickers.value.length >= 5) {
      pushNotification({
        icon: "⚠️",
        title: "比較標的已達上限",
        msg: "最多可同時比較 5 檔股票",
        type: "error",
      });
      return;
    }
    await loadComparisonSeries([...compareTickers.value, normalized]);
  }

  async function removeCompareTicker(ticker) {
    await loadComparisonSeries(compareTickers.value.filter((item) => item !== normalizeTicker(ticker)));
  }

  function clearCompareTickers() {
    compareTickers.value = [];
    rawCompareSeries.value = [];
  }

  function setComparisonMode(mode) {
    comparisonMode.value = mode === "price" ? "price" : "percent";
  }

  async function loadQuote(ticker = currentTicker.value) {
    try {
      const data = await apiFetch(`/api/quote/${normalizeTicker(ticker)}`, { retries: 6, retryDelayMs: 1200 });
      if (data) applyQuote(data);
    } catch (error) {
      console.error(error);
    }
  }

  async function loadKline(ticker = currentTicker.value, period = currentPeriod.value, interval = currentInterval.value) {
    const normalized = normalizeTicker(ticker);
    const resolvedPeriod = (period || "1y").toLowerCase();
    const resolvedInterval = resolveTimeframeInterval(resolvedPeriod, interval);
    const fetchPeriod = getExpandedFetchPeriod(resolvedPeriod, klineDisplayMode.value);
    currentPeriod.value = resolvedPeriod;
    currentInterval.value = resolvedInterval;
    chartLoading.value = true;
    loadingMessage.value = `載入 ${normalized} K 線...`;
    try {
      const data = await apiFetch(`/api/kline/${normalized}?period=${fetchPeriod}&interval=${resolvedInterval}`, {
        retries: 12,
        retryDelayMs: 1500,
      });
      const resolvedTicker = normalizeTicker(data?.ticker || normalized);
      if (resolvedTicker !== currentTicker.value) {
        wsSend({ action: "unsubscribe", ticker: currentTicker.value });
        currentTicker.value = resolvedTicker;
        wsSend({ action: "subscribe", ticker: resolvedTicker });
      }
      rawOhlcData.value = data.data || [];
      crosshair.visible = false;
      await loadComparisonSeries(compareTickers.value);
      if (rawOhlcData.value.length > 0) await loadQuote(resolvedTicker);
      else resetQuote();
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "載入失敗", msg: `無法取得 ${normalized} 資料`, type: "error" });
    } finally {
      chartLoading.value = false;
    }
  }

  async function loadDbStats() {
    if (dbStatsLoading.value) return;
    dbStatsLoading.value = true;
    dbStatsError.value = "";
    try {
      dbStats.value = await apiFetch("/api/db/stats");
    } catch (error) {
      dbStats.value = null;
      dbStatsError.value = "無法取得 DB 統計";
    } finally {
      dbStatsLoading.value = false;
    }
  }

  async function selectTicker(ticker, name = ticker) {
    const normalized = normalizeTicker(ticker);
    wsSend({ action: "unsubscribe", ticker: normalizeTicker(currentTicker.value) });
    currentTicker.value = normalized;
    currentName.value = name || normalized;
    compareTickers.value = compareTickers.value.filter((item) => item !== normalized);
    drawings.value = [];
    selectedDrawingId.value = null;
    rawOhlcData.value = [];
    crosshair.visible = false;
    wsSend({ action: "subscribe", ticker: normalized });
    await loadKline(normalized, currentPeriod.value, currentInterval.value);
    void loadBacktestHistory({ ticker: normalized });
    void loadJournalData();
    void loadTickerIntelligence(normalized);
    void ensureInstitutionalOverlayForTicker(normalized);
  }

  function setTimeframe(timeframe) {
    currentPeriod.value = timeframe.tf;
    currentInterval.value = resolveTimeframeInterval(timeframe.tf, timeframe.iv);
    loadKline(currentTicker.value, timeframe.tf, currentInterval.value);
  }

  async function loadInstitutionalData(dateValue = institutionalDate.value, forceRefresh = false) {
    institutionalLoading.value = true;
    institutionalError.value = "";
    institutionalInsightsError.value = "";
    try {
      const params = new URLSearchParams({ date: dateValue });
      if (forceRefresh) params.set("refresh", "1");
      const payload = await apiFetch(`/api/taifex/institutional?${params.toString()}`, {
        retries: 3,
        retryDelayMs: 1200,
      });
      institutionalDate.value = dateValue;
      institutionalData.value = payload;
      const nextFuturesCommodity = (payload?.futures_commodities || []).includes(institutionalFuturesCommodity.value)
        ? institutionalFuturesCommodity.value
        : (payload?.default_futures_commodity || payload?.futures_commodities?.[0] || "");
      const nextOptionsCommodity = (payload?.options_commodities || []).includes(institutionalOptionsCommodity.value)
        ? institutionalOptionsCommodity.value
        : (payload?.default_options_commodity || payload?.options_commodities?.[0] || "");
      institutionalFuturesCommodity.value = nextFuturesCommodity;
      institutionalOptionsCommodity.value = nextOptionsCommodity;
      await loadInstitutionalInsights(
        dateValue,
        nextFuturesCommodity,
        nextOptionsCommodity,
        institutionalHistoryDays.value,
        forceRefresh,
      );
    } catch (error) {
      institutionalError.value = error.message || "無法取得期權法人資料";
    } finally {
      institutionalLoading.value = false;
    }
  }

  async function loadInstitutionalInsights(
    dateValue = institutionalDate.value,
    futuresCommodity = institutionalFuturesCommodity.value,
    optionsCommodity = institutionalOptionsCommodity.value,
    days = institutionalHistoryDays.value,
    forceRefresh = false,
  ) {
    if (!futuresCommodity && !optionsCommodity) return;
    institutionalInsightsLoading.value = true;
    institutionalInsightsError.value = "";
    try {
      const params = new URLSearchParams({
        date: dateValue,
        days: String(days),
      });
      if (futuresCommodity) params.set("futures_commodity", futuresCommodity);
      if (optionsCommodity) params.set("options_commodity", optionsCommodity);
      if (forceRefresh) params.set("refresh", "1");
      const payload = await apiFetch(`/api/taifex/institutional/insights?${params.toString()}`, {
        retries: 2,
        retryDelayMs: 1200,
      });
      institutionalInsights.value = payload;
    } catch (error) {
      institutionalInsightsError.value = error.message || "無法取得法人歷史趨勢";
    } finally {
      institutionalInsightsLoading.value = false;
    }
  }

  async function ensureInstitutionalOverlayForTicker(ticker = currentTicker.value) {
    const normalizedTicker = normalizeTicker(ticker);
    const mappedCommodity = FUTURES_OVERLAY_TICKER_MAP[normalizedTicker];
    if (!mappedCommodity) return;

    if (!institutionalData.value && !institutionalLoading.value) {
      await loadInstitutionalData(institutionalDate.value);
    }

    const hasMatchingInsights = institutionalInsights.value?.futures_commodity === mappedCommodity;
    const hasMatchingDefault = institutionalData.value?.default_futures_commodity === mappedCommodity;
    if (hasMatchingInsights || hasMatchingDefault || institutionalInsightsLoading.value) return;

    institutionalFuturesCommodity.value = mappedCommodity;
    await loadInstitutionalInsights(
      institutionalDate.value,
      mappedCommodity,
      institutionalOptionsCommodity.value || institutionalData.value?.default_options_commodity || "",
      institutionalHistoryDays.value,
    );
  }

  async function setKlineDisplayMode(mode) {
    const nextMode = normalizeKlineDisplayMode(mode);
    if (nextMode === klineDisplayMode.value) return;
    klineDisplayMode.value = nextMode;
    crosshair.visible = false;
    await loadKline(currentTicker.value, currentPeriod.value, currentInterval.value);
  }

  function setLeftTab(tab) {
    leftTab.value = tab;
  }

  function setActiveWatchGroup(groupId) {
    activeWatchGroupId.value = groupId;
  }

  async function setRightTab(tab) {
    rightTab.value = tab;
    if (tab === "db") await loadDbStats();
    if (tab === "backtest") await loadBacktestHistory({ ticker: currentTicker.value });
    if (tab === "journal") await loadJournalData({ silent: false });
  }

  async function setWorkspaceTab(tab) {
    workspaceTab.value = WORKSPACE_TAB_OPTIONS.includes(tab) ? tab : "chart";
    if (workspaceTab.value === "institutional") {
      if (!institutionalData.value && !institutionalLoading.value) {
        await loadInstitutionalData();
      } else if (!institutionalInsights.value && !institutionalInsightsLoading.value) {
        await loadInstitutionalInsights();
      }
      return;
    }
    if (workspaceTab.value === "events") {
      await Promise.all([
        loadEventCalendar(),
        loadTickerIntelligence(currentTicker.value),
      ]);
      return;
    }
    if (workspaceTab.value === "macro") {
      await loadMacroDashboard();
      return;
    }
    if (workspaceTab.value === "screener") {
      if (!screenerPresets.value.length) {
        await loadScreenerPresets();
      }
      if (!screenerResults.value.items?.length) {
        await runScreener();
      }
    }
  }

  async function setInstitutionalDate(value) {
    if (!value) return;
    await loadInstitutionalData(value);
  }

  async function setInstitutionalFuturesCommodity(value) {
    if (!value || value === institutionalFuturesCommodity.value) return;
    institutionalFuturesCommodity.value = value;
    await loadInstitutionalInsights();
  }

  async function setInstitutionalOptionsCommodity(value) {
    if (!value || value === institutionalOptionsCommodity.value) return;
    institutionalOptionsCommodity.value = value;
    await loadInstitutionalInsights();
  }

  async function setInstitutionalHistoryDays(value) {
    const nextValue = INSTITUTIONAL_HISTORY_OPTIONS.includes(Number(value)) ? Number(value) : 30;
    institutionalHistoryDays.value = nextValue;
    await loadInstitutionalInsights();
  }

  async function shiftInstitutionalDate(days) {
    const base = institutionalDate.value ? new Date(`${institutionalDate.value}T00:00:00`) : new Date();
    base.setDate(base.getDate() + Number(days || 0));
    await loadInstitutionalData(base.toISOString().slice(0, 10));
  }

  function setChartLayout(layout) {
    chartLayout.value = CHART_LAYOUT_OPTIONS.includes(layout) ? layout : "single";
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

  async function migrateLegacyWorkspacePresets() {
    if (!isBrowser()) return false;
    const legacyPresets = readLegacyWorkspacePresets(window.localStorage);
    if (!legacyPresets.length) return false;

    let migratedCount = 0;
    for (const preset of legacyPresets.slice(0, 24)) {
      const trimmedName = String(preset?.name || "").trim();
      if (!trimmedName) continue;
      try {
        await dashboardApi.createWorkspace(toWorkspaceSaveRequest(trimmedName, preset));
        migratedCount += 1;
      } catch (error) {
        console.error(error);
      }
    }

    if (migratedCount > 0) {
      clearLegacyWorkspacePresets(window.localStorage);
    }
    return migratedCount > 0;
  }

  async function loadWorkspacePresets({ allowLegacyMigration = true, silent = true } = {}) {
    try {
      const response = await dashboardApi.listWorkspaces();
      const items = Array.isArray(response?.items)
        ? response.items.map((item) => normalizeWorkspaceRecord(item))
        : [];

      if (!items.length && allowLegacyMigration) {
        const migrated = await migrateLegacyWorkspacePresets();
        if (migrated) {
          return await loadWorkspacePresets({ allowLegacyMigration: false, silent });
        }
      }

      workspacePresets.value = items;
      if (
        activeWorkspacePresetId.value != null
        && !items.some((item) => sameWorkspaceId(item.id, activeWorkspacePresetId.value))
      ) {
        activeWorkspacePresetId.value = null;
      }
      return items;
    } catch (error) {
      console.error(error);
      workspacePresets.value = [];
      if (!silent) {
        pushNotification({ icon: "⚠️", title: "工作區載入失敗", msg: "請稍後再試", type: "error" });
      }
      return [];
    }
  }

  function buildWorkspaceSnapshot(name) {
    return {
      name,
      savedAt: new Date().toISOString(),
      ...buildWorkspacePayload({
        currentTicker: currentTicker.value,
        currentName: currentName.value,
        currentPeriod: currentPeriod.value,
        currentInterval: currentInterval.value,
        klineDisplayMode: klineDisplayMode.value,
        cleanChartMode: cleanChartMode.value,
        chartLayout: chartLayout.value,
        compareTickers: compareTickers.value,
        comparisonMode: comparisonMode.value,
        activeTool: activeTool.value,
        leftTab: leftTab.value,
        rightTab: rightTab.value,
        workspaceTab: workspaceTab.value,
        screenerFilters,
        activeInd,
        activePanels,
        indicatorSettings,
        drawings: drawings.value,
      }),
    };
  }

  async function saveWorkspacePreset(name) {
    const trimmed = (name || "").trim();
    if (!trimmed) return;

    const existing = workspacePresets.value.find((item) => item.name.toLowerCase() === trimmed.toLowerCase());
    const snapshot = buildWorkspaceSnapshot(trimmed);

    try {
      const persisted = existing
        ? await dashboardApi.updateWorkspace(existing.id, toWorkspaceSaveRequest(trimmed, snapshot))
        : await dashboardApi.createWorkspace(toWorkspaceSaveRequest(trimmed, snapshot));
      const normalized = normalizeWorkspaceRecord(persisted);
      workspacePresets.value = existing
        ? workspacePresets.value.map((item) => (sameWorkspaceId(item.id, existing.id) ? normalized : item))
        : [normalized, ...workspacePresets.value].slice(0, 24);
      activeWorkspacePresetId.value = normalized.id;
      pushNotification({
        icon: existing ? "↻" : "💾",
        title: existing ? "工作區已更新" : "工作區已儲存",
        msg: trimmed,
        type: "success",
      });
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "工作區儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function loadWorkspacePreset(presetId) {
    let preset = workspacePresets.value.find((item) => sameWorkspaceId(item.id, presetId));
    if (!preset) {
      try {
        preset = normalizeWorkspaceRecord(await dashboardApi.getWorkspace(presetId));
      } catch (error) {
        pushNotification({ icon: "⚠️", title: "工作區載入失敗", msg: error.message || "請稍後再試", type: "error" });
        return;
      }
    }
    const normalizedTicker = normalizeTicker(preset.currentTicker || currentTicker.value);
    wsSend({ action: "unsubscribe", ticker: normalizeTicker(currentTicker.value) });
    currentTicker.value = normalizedTicker;
    currentName.value = preset.currentName || normalizedTicker;
    currentPeriod.value = preset.currentPeriod || currentPeriod.value;
    currentInterval.value = resolveTimeframeInterval(currentPeriod.value, preset.currentInterval || currentInterval.value);
    klineDisplayMode.value = normalizeKlineDisplayMode(preset.klineDisplayMode);
    cleanChartMode.value = Boolean(preset.cleanChartMode);
    chartLayout.value = CHART_LAYOUT_OPTIONS.includes(preset.chartLayout) ? preset.chartLayout : "single";
    comparisonMode.value = preset.comparisonMode === "price" ? "price" : "percent";
    activeTool.value = TOOL_OPTIONS.includes(preset.activeTool) ? preset.activeTool : "cursor";
    leftTab.value = preset.leftTab === "market" ? "market" : "watch";
    rightTab.value = ["indicators", "alerts", "backtest", "journal", "db"].includes(preset.rightTab) ? preset.rightTab : "indicators";
    workspaceTab.value = WORKSPACE_TAB_OPTIONS.includes(preset.workspaceTab) ? preset.workspaceTab : "chart";
    compareTickers.value = (preset.compareTickers || [])
      .map((ticker) => normalizeTicker(ticker))
      .filter((ticker) => ticker && ticker !== normalizedTicker);
    applyScreenerFilters(preset.screenerFilters || {});
    Object.keys(DEFAULT_ACTIVE_IND).forEach((key) => {
      activeInd[key] = preset.activeInd?.[key] ?? DEFAULT_ACTIVE_IND[key];
    });
    Object.keys(DEFAULT_ACTIVE_PANELS).forEach((key) => {
      activePanels[key] = preset.activePanels?.[key] ?? DEFAULT_ACTIVE_PANELS[key];
    });
    Object.assign(
      indicatorSettings,
      normalizeIndicatorSettings(preset.indicatorSettings || indicatorSettings),
    );
    drawings.value = (preset.drawings || []).map((drawing) => createDrawingEntry(drawing));
    selectedDrawingId.value = null;
    activeWorkspacePresetId.value = preset.id;
    rawOhlcData.value = [];
    crosshair.visible = false;
    if (rightTab.value === "db") {
      await loadDbStats();
    }
    wsSend({ action: "subscribe", ticker: normalizedTicker });
    await loadKline(normalizedTicker, currentPeriod.value, currentInterval.value);
    if (workspaceTab.value === "events") {
      await loadEventCalendar();
      await loadTickerIntelligence(normalizedTicker);
    } else if (workspaceTab.value === "macro") {
      await loadMacroDashboard();
    } else if (workspaceTab.value === "screener") {
      await runScreener();
    } else {
      void loadTickerIntelligence(normalizedTicker);
    }
    pushNotification({ icon: "📂", title: "工作區已載入", msg: preset.name, type: "success" });
  }

  async function deleteWorkspacePreset(presetId) {
    const target = workspacePresets.value.find((item) => sameWorkspaceId(item.id, presetId));
    if (!target) return;
    try {
      await dashboardApi.deleteWorkspace(presetId);
      workspacePresets.value = workspacePresets.value.filter((item) => !sameWorkspaceId(item.id, presetId));
      if (sameWorkspaceId(activeWorkspacePresetId.value, presetId)) {
        activeWorkspacePresetId.value = null;
      }
      pushNotification({ icon: "🗑", title: "工作區已刪除", msg: target.name, type: "success" });
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "工作區刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
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

  async function syncCurrentTicker() {
    syncingCurrent.value = true;
    try {
      const result = await apiFetch(`/api/sync/${normalizeTicker(currentTicker.value)}`, { method: "POST" });
      pushNotification({
        icon: "✅",
        title: "同步完成",
        msg: `${currentTicker.value} 已同步 ${result.synced} 筆`,
        type: "success",
      });
      await loadKline(currentTicker.value, currentPeriod.value, currentInterval.value);
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "同步失敗", msg: "請檢查網路連線", type: "error" });
    } finally {
      syncingCurrent.value = false;
    }
  }

  async function syncAll() {
    syncingAll.value = true;
    pushNotification({ icon: "📥", title: "全量同步開始", msg: "正在同步股票與大盤最新資料，這可能需要幾分鐘" });
    try {
      const result = await apiFetch("/api/sync/all?period=1y&interval=1d", {
        method: "POST",
        retries: 1,
        retryDelayMs: 1200,
      });
      await Promise.all([
        loadWatchlist(),
        loadDbStats(),
        loadKline(currentTicker.value, currentPeriod.value, currentInterval.value),
        loadEventCalendar(true),
        loadMacroDashboard(true),
        loadTickerIntelligence(currentTicker.value, true),
      ]);
      pushNotification({
        icon: result.failure_count ? "⚠️" : "✅",
        title: result.failure_count ? "同步部分完成" : "同步完成",
        msg: `已同步 ${result.success_count} 檔，失敗 ${result.failure_count} 檔，共更新 ${Number(result.total_rows || 0).toLocaleString()} 筆資料`,
        type: result.failure_count ? "warning" : "success",
      });
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "全量同步失敗",
        msg: error.message || "請稍後再試",
        type: "error",
      });
    } finally {
      syncingAll.value = false;
    }
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
      const results = await apiFetch(`/api/search?q=${encodeURIComponent(trimmed)}`);
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

  function openAlertModal(ticker = currentTicker.value, overrides = {}) {
    const options = ticker && typeof ticker === "object" && !Array.isArray(ticker)
      ? ticker
      : { ticker, ...overrides };
    resetAlertForm();
    alertForm.ticker = normalizeTicker(options.ticker || currentTicker.value || "AAPL");
    if (options.type) {
      updateAlertField("type", options.type);
    }
    if (options.condition) {
      updateAlertField("cond", options.condition);
    }
    if ("value" in options) {
      alertForm.value = options.value == null ? "" : String(options.value);
    }
    alertForm.prefill_hint = options.prefill_hint || "";
    alertForm.context_tags = Array.isArray(options.context_tags) ? options.context_tags.filter(Boolean) : [];
    alertForm.context_source = options.context_source || "";
    alertForm.snapshot_price = options.snapshot_price ?? null;
    alertForm.snapshot_source = options.snapshot_source || "";
    alertForm.snapshot_timestamp = options.snapshot_timestamp || "";
    alertModalOpen.value = true;
  }

  function closeAlertModal() {
    alertModalOpen.value = false;
  }

  function updateAlertField(key, value) {
    if (key === "type") {
      const previousType = String(alertForm.type || "").toLowerCase();
      const nextType = String(value || "").toLowerCase();
      alertForm.type = value;
      alertForm.cond = defaultAlertCondition(value);
      if (nextType === "market_risk") {
        alertForm.ticker = "MARKET";
      } else if (
        previousType === "market_risk"
        && (!alertForm.ticker || String(alertForm.ticker).toUpperCase() === "MARKET")
      ) {
        alertForm.ticker = normalizeTicker(currentTicker.value || "AAPL");
      }
      if (!alertRequiresNumericValue(value, alertForm.cond)) {
        alertForm.value = "";
      }
      return;
    }
    if (key === "cond") {
      alertForm.cond = value;
      if (!alertRequiresNumericValue(alertForm.type, value)) {
        alertForm.value = "";
      }
      return;
    }
    alertForm[key] = value;
  }

  async function saveAlert() {
    const requiresNumericValue = alertRequiresNumericValue(alertForm.type, alertForm.cond);
    const numericValue = requiresNumericValue ? Number(alertForm.value) : null;
    const normalizedTicker = String(alertForm.type || "").toLowerCase() === "market_risk"
      ? "MARKET"
      : normalizeTicker(alertForm.ticker || currentTicker.value);
    if (!normalizedTicker || (requiresNumericValue && Number.isNaN(numericValue))) {
      pushNotification({ icon: "⚠️", title: "警報設定失敗", msg: "請完整填寫股票代號與數值", type: "error" });
      return;
    }
    const payload = {
      ticker: normalizedTicker,
      type: alertForm.type,
      condition: alertForm.cond,
      value: numericValue,
      timeframe: "1d",
      condition_payload: {
        operator: alertForm.cond,
        metric: alertForm.type === "volume" ? "volume_ratio" : null,
        context_source: alertForm.context_source || null,
        context_tags: alertForm.context_tags.length ? alertForm.context_tags : null,
        snapshot_price: alertForm.snapshot_price ?? null,
        snapshot_source: alertForm.snapshot_source || null,
        snapshot_timestamp: alertForm.snapshot_timestamp || null,
        prefill_hint: alertForm.prefill_hint || null,
      },
      active: true,
    };
    try {
      const record = await dashboardApi.createAlert(payload);
      alerts.value = [mapAlertRecord(record), ...alerts.value];
      alertModalOpen.value = false;
      resetAlertForm();
      const displayValue = record.value == null ? "" : ` ${record.value}`;
      const targetLabel = String(record.type || "").toLowerCase() === "market_risk" ? "市場" : record.ticker;
      const conditionLabel = formatAlertConditionLabel(record.condition);
      pushNotification({ icon: "🔔", title: "警報已設定", msg: `${targetLabel} ${conditionLabel}${displayValue}`.trim(), type: "success" });
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "警報設定失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function loadAlertTriggerLogs(alertId, { force = false } = {}) {
    const cacheKey = String(alertId);
    if (!force && Array.isArray(alertTriggerLogs.value[cacheKey])) {
      return alertTriggerLogs.value[cacheKey];
    }

    alertLogLoading.value = {
      ...alertLogLoading.value,
      [cacheKey]: true,
    };
    try {
      const response = await dashboardApi.listAlertTriggers(alertId, { limit: 20 });
      const logs = Array.isArray(response?.items)
        ? response.items.map((item) => mapAlertTriggerLog(item))
        : [];
      alertTriggerLogs.value = {
        ...alertTriggerLogs.value,
        [cacheKey]: logs,
      };
      return logs;
    } catch (error) {
      pushNotification({
        icon: "!",
        title: "Alert log load failed",
        msg: error.message || "Please try again later",
        type: "error",
      });
      return [];
    } finally {
      alertLogLoading.value = {
        ...alertLogLoading.value,
        [cacheKey]: false,
      };
    }
  }

  async function toggleAlertLog(alertId) {
    if (alertId == null) return;
    if (String(expandedAlertLogId.value) === String(alertId)) {
      expandedAlertLogId.value = null;
      return;
    }
    expandedAlertLogId.value = alertId;
    await loadAlertTriggerLogs(alertId);
  }

  async function toggleAlertActive(alertId) {
    if (alertId == null) return;
    const target = alerts.value.find((item) => String(item.id) === String(alertId));
    if (!target) return;

    const nextActive = !target.active;
    const payload = nextActive
      ? { active: true, triggered: false, triggered_at: null }
      : { active: false };

    try {
      const record = await dashboardApi.updateAlert(alertId, payload);
      alerts.value = alerts.value.map((item) =>
        String(item.id) === String(alertId) ? mapAlertRecord(record) : item,
      );
      pushNotification({
        icon: nextActive ? ">" : "||",
        title: nextActive ? "Alert resumed" : "Alert paused",
        msg: `${record.ticker} ${record.condition || record.cond}`,
        type: "success",
      });
    } catch (error) {
      pushNotification({
        icon: "!",
        title: nextActive ? "Resume alert failed" : "Pause alert failed",
        msg: error.message || "Please try again later",
        type: "error",
      });
    }
  }

  async function deleteAlert(alertId) {
    if (alertId == null) return;
    const target = alerts.value.find((item) => String(item.id) === String(alertId));
    try {
      await dashboardApi.deleteAlert(alertId);
      alerts.value = alerts.value.filter((item) => String(item.id) !== String(alertId));
      pruneAlertArtifacts(alerts.value);
      pushNotification({
        icon: "🗑",
        title: "警報已刪除",
        msg: target ? `${target.ticker} ${target.condition || target.cond}` : "已移除警報",
        type: "success",
      });
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "警報刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
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

  onMounted(async () => {
    updateClock();
    clockTimer = window.setInterval(updateClock, 1000);
    connectWs();
    await loadWorkspacePresets();
    await loadAlerts();
    await loadNotifications();
    await loadBacktestHistory({ ticker: currentTicker.value });
    applyJournalEntryToForm();
    await loadJournalData();
    await loadScreenerPresets();
    await loadWatchlist();
    if (rightTab.value === "db") {
      await loadDbStats();
    }
    if (workspaceTab.value === "institutional") {
      await loadInstitutionalData();
    }
    if (workspaceTab.value === "events") {
      await loadEventCalendar();
    }
    if (workspaceTab.value === "macro") {
      await loadMacroDashboard();
    }
    if (workspaceTab.value === "screener") {
      await runScreener();
    }
    await loadKline(currentTicker.value, currentPeriod.value, currentInterval.value);
    void loadTickerIntelligence(currentTicker.value);
    void ensureInstitutionalOverlayForTicker(currentTicker.value);
    watchlistTimer = window.setInterval(loadWatchlist, 60000);
    alertPollingTimer = window.setInterval(() => {
      void loadAlerts();
      void loadNotifications();
    }, 30000);
  });

  onBeforeUnmount(() => {
    if (clockTimer) clearInterval(clockTimer);
    if (watchlistTimer) clearInterval(watchlistTimer);
    if (alertPollingTimer) clearInterval(alertPollingTimer);
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
    if (ws && ws.readyState < 2) ws.close();
  });

  return {
    timeframeOptions,
    klineDisplayOptions,
    searchQuery,
    searchResults,
    searchOpen,
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
    fundamentalsDetail,
    fundamentalsSummary,
    taiwanChipDetail,
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
    saveJournalEntry,
    deleteJournalEntry,
    selectJournalEntry,
    resetJournalForm,
    updateJournalFilter,
    addJournalAttachment,
    removeJournalAttachment,
    startJournalEntry,
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
