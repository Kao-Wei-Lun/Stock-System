import { ref, shallowRef } from "vue";

export function createDashboardTerminalState({
  ticker,
  period,
  interval,
  klineDisplayMode,
  chartEngineMode,
  cleanChartMode = false,
  chartLayout = "single",
} = {}) {
  return {
    currentTicker: ref(ticker || ""),
    currentName: ref("載入中..."),
    currentPeriod: ref(period || "1y"),
    currentInterval: ref(interval || "1d"),
    klineDisplayMode: ref(klineDisplayMode || "day"),
    chartEngineMode: ref(chartEngineMode || "legacy"),
    cleanChartMode: ref(Boolean(cleanChartMode)),
    chartLayout: ref(chartLayout || "single"),
    chartLoading: ref(true),
    loadingMessage: ref("正在載入資料..."),
    futoptRefreshStatus: ref("idle"),
    futoptDataStale: ref(false),
    rawOhlcData: shallowRef([]),
    klineDataOrigin: ref("loading"),
    klineCacheSavedAt: ref(null),
    drawings: ref([]),
    selectedDrawingId: ref(null),
    syncingCurrent: ref(false),
    syncingAll: ref(false),
  };
}
