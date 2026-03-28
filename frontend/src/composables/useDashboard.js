import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { buildIndicatorSnapshot, runBacktestSimulation } from "../utils/indicatorUtils";
import { fmtMktCap, fmtPrice, fmtVol } from "../utils/formatters";

const TIMEFRAME_OPTIONS = [
  { tf: "5d", iv: "1h", label: "5D" },
  { tf: "1mo", iv: "1d", label: "1M" },
  { tf: "3mo", iv: "1d", label: "3M" },
  { tf: "1y", iv: "1d", label: "1Y" },
  { tf: "2y", iv: "1wk", label: "2Y" },
  { tf: "5y", iv: "1mo", label: "5Y" },
];

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

export function normalizeTicker(ticker) {
  const raw = (ticker || "").trim().toUpperCase();
  if (!raw || raw.startsWith("^") || raw.includes(".") || raw.includes("-")) return raw;
  if (!/^[A-Z]+$/.test(raw)) return `${raw}.TW`;
  return raw;
}

export function useDashboard() {
  const apiBase = getApiBase();
  const wsUrl = `${getWsBase()}/ws`;
  const backendUrl = import.meta.env.DEV ? getBackendTarget() : window.location.origin;

  const timeframeOptions = TIMEFRAME_OPTIONS;
  const searchQuery = ref("");
  const searchResults = ref([]);
  const searchOpen = ref(false);
  const watchlist = ref([]);
  const watchlistLoading = ref(true);
  const watchlistError = ref(false);
  const leftTab = ref("watch");
  const rightTab = ref("indicators");
  const currentTicker = ref("AAPL");
  const currentName = ref("載入中...");
  const currentPeriod = ref("1y");
  const currentInterval = ref("1d");
  const chartLoading = ref(true);
  const loadingMessage = ref("正在載入資料...");
  const ohlcData = ref([]);
  const drawings = ref([]);
  const alerts = ref([]);
  const notifications = ref([]);
  const wsConnected = ref(false);
  const latency = ref("—");
  const lastUpdate = ref("—");
  const clockTime = ref("—");
  const dbStats = ref(null);
  const dbStatsError = ref("");
  const syncingCurrent = ref(false);
  const syncingAll = ref(false);
  const alertModalOpen = ref(false);
  const activeTool = ref("cursor");
  const backtestResult = ref(null);

  const quote = reactive({
    price: null,
    open: null,
    high: null,
    low: null,
    volume: null,
    market_cap: null,
    change: 0,
    change_pct: 0,
    name: "載入中...",
  });

  const marketStatus = reactive({ tseOpen: false, hkOpen: false });
  const activeInd = reactive({ ma20: true, ma50: true, ma200: false, ema12: true, bb: false, vwap: false });
  const activePanels = reactive({ rsi: true, macd: false, stoch: false });
  const crosshair = reactive({
    visible: false,
    date: "—",
    open: "—",
    high: "—",
    low: "—",
    close: "—",
    volume: "—",
  });
  const alertForm = reactive({ ticker: "AAPL", type: "price", cond: "大於", value: "" });
  const backtestForm = reactive({
    strategy: "MA 黃金/死亡交叉",
    start: "2022-01-01",
    end: new Date().toISOString().slice(0, 10),
    capital: 100000,
    fee: 0.1,
    sl: 5,
    tp: 10,
  });

  const indicatorSnapshot = computed(() => buildIndicatorSnapshot(ohlcData.value));

  let ws = null;
  let wsReconnectTimer = null;
  let clockTimer = null;
  let watchlistTimer = null;

  function pushNotification({ icon, title, msg, type = "" }) {
    const id = `${Date.now()}-${Math.random()}`;
    notifications.value = [
      ...notifications.value,
      { id, icon, title, msg, type, time: new Date().toLocaleTimeString("zh-TW") },
    ];
    window.setTimeout(() => dismissNotification(id), 6000);
  }

  function dismissNotification(id) {
    notifications.value = notifications.value.filter((item) => item.id !== id);
  }

  async function apiFetch(path, options = {}) {
    const start = Date.now();
    const response = await fetch(`${apiBase}${path}`, options);
    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : null;
    latency.value = `${Date.now() - start}ms`;
    if (!response.ok) {
      throw new Error(payload?.detail || `HTTP ${response.status}`);
    }
    return payload;
  }

  function applyQuote(data) {
    quote.price = data.price ?? null;
    quote.open = data.open ?? null;
    quote.high = data.high ?? null;
    quote.low = data.low ?? null;
    quote.volume = data.volume ?? null;
    quote.market_cap = data.market_cap ?? null;
    quote.change = data.change ?? 0;
    quote.change_pct = data.change_pct ?? 0;
    quote.name = data.name || currentName.value;
    if (data.name) currentName.value = data.name;
    lastUpdate.value = new Date().toLocaleTimeString("zh-TW");
  }

  function resetQuote() {
    applyQuote({
      price: null,
      open: null,
      high: null,
      low: null,
      volume: null,
      market_cap: null,
      change: 0,
      change_pct: 0,
      name: currentName.value,
    });
  }

  function checkAlerts(currentQuote) {
    alerts.value = alerts.value.map((alert) => {
      if (alert.triggered || alert.ticker !== currentQuote.ticker) return alert;
      let triggered = false;
      if (alert.type === "price") {
        if (alert.cond === "大於" && currentQuote.price > alert.value) triggered = true;
        if (alert.cond === "小於" && currentQuote.price < alert.value) triggered = true;
      }
      if (triggered) {
        pushNotification({
          icon: "⚡",
          title: `警報觸發！${alert.ticker}`,
          msg: `${alert.type} ${alert.cond} ${alert.value}`,
          type: "alert",
        });
        return { ...alert, triggered: true };
      }
      return alert;
    });
  }

  function handleRealtimeQuote(message) {
    const data = message.data;
    if (data.ticker !== currentTicker.value && data.ticker !== normalizeTicker(currentTicker.value)) return;
    applyQuote(data);
    if (ohlcData.value.length > 0) {
      const last = ohlcData.value[ohlcData.value.length - 1];
      const today = new Date().toISOString().slice(0, 10);
      if (last.date === today || last.date.startsWith(today)) {
        const updated = {
          ...last,
          close: data.price,
          high: data.high && data.high > last.high ? data.high : last.high,
          low: data.low && data.low < last.low ? data.low : last.low,
        };
        ohlcData.value = [...ohlcData.value.slice(0, -1), updated];
      }
    }
    checkAlerts(data);
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
      watchlist.value = await apiFetch("/api/watchlist");
      const current = watchlist.value.find((item) => item.ticker === currentTicker.value);
      if (current) currentName.value = current.name || current.ticker;
    } catch (error) {
      watchlistError.value = true;
    } finally {
      watchlistLoading.value = false;
    }
  }

  async function loadQuote(ticker = currentTicker.value) {
    try {
      const data = await apiFetch(`/api/quote/${normalizeTicker(ticker)}`);
      if (data) applyQuote(data);
    } catch (error) {
      console.error(error);
    }
  }

  async function loadKline(ticker = currentTicker.value, period = currentPeriod.value, interval = currentInterval.value) {
    const normalized = normalizeTicker(ticker);
    chartLoading.value = true;
    loadingMessage.value = `載入 ${normalized} K 線...`;
    try {
      const data = await apiFetch(`/api/kline/${normalized}?period=${period}&interval=${interval}`);
      ohlcData.value = data.data || [];
      crosshair.visible = false;
      if (ohlcData.value.length > 0) await loadQuote(normalized);
      else resetQuote();
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "載入失敗", msg: `無法取得 ${normalized} 資料`, type: "error" });
    } finally {
      chartLoading.value = false;
    }
  }

  async function loadDbStats() {
    dbStatsError.value = "";
    try {
      dbStats.value = await apiFetch("/api/db/stats");
    } catch (error) {
      dbStats.value = null;
      dbStatsError.value = "無法取得 DB 統計";
    }
  }

  async function selectTicker(ticker, name = ticker) {
    const normalized = normalizeTicker(ticker);
    wsSend({ action: "unsubscribe", ticker: normalizeTicker(currentTicker.value) });
    currentTicker.value = normalized;
    currentName.value = name || normalized;
    drawings.value = [];
    ohlcData.value = [];
    crosshair.visible = false;
    wsSend({ action: "subscribe", ticker: normalized });
    await loadKline(normalized, currentPeriod.value, currentInterval.value);
  }

  function setTimeframe(timeframe) {
    currentPeriod.value = timeframe.tf;
    currentInterval.value = timeframe.iv;
    loadKline(currentTicker.value, timeframe.tf, timeframe.iv);
  }

  function setLeftTab(tab) {
    leftTab.value = tab;
  }

  async function setRightTab(tab) {
    rightTab.value = tab;
    if (tab === "db") await loadDbStats();
  }

  function toggleIndicator(name) {
    activeInd[name] = !activeInd[name];
  }

  function togglePanel(name) {
    activePanels[name] = !activePanels[name];
  }

  function setTool(tool) {
    activeTool.value = tool;
  }

  function addSignal(type) {
    if (!ohlcData.value.length) return;
    const index = Math.min(ohlcData.value.length - 1, Math.floor(ohlcData.value.length * 0.9));
    drawings.value = [...drawings.value, { type, index }];
    pushNotification({
      icon: type === "buy" ? "▲" : "▼",
      title: type === "buy" ? "買入標記" : "賣出標記",
      msg: "已標記在最近 K 線",
    });
  }

  function clearDrawings() {
    drawings.value = [];
  }

  function addHorizontalLine(price) {
    drawings.value = [...drawings.value, { type: "hline", price }];
    pushNotification({ icon: "─", title: "水平線已加", msg: `@${price.toFixed(2)}` });
  }

  function addDrawing(drawing) {
    drawings.value = [...drawings.value, drawing];

    if (drawing.type === "trendline") {
      pushNotification({ icon: "╱", title: "趨勢線已加", msg: "已加入分析線段" });
      return;
    }

    if (drawing.type === "fib") {
      pushNotification({ icon: "⋮", title: "費波那契已加", msg: "已加入回撤分析" });
    }
  }

  function removeLastDrawing() {
    if (!drawings.value.length) return;
    drawings.value = drawings.value.slice(0, -1);
    pushNotification({ icon: "↶", title: "已復原", msg: "已移除最後一筆繪圖" });
  }

  function updateCrosshair(payload) {
    Object.assign(crosshair, payload);
  }

  function hideCrosshair() {
    crosshair.visible = false;
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

  function syncAll() {
    syncingAll.value = true;
    pushNotification({ icon: "📥", title: "全量同步開始", msg: "這可能需要幾分鐘，請稍候" });
    window.setTimeout(() => {
      syncingAll.value = false;
    }, 30000);
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
    const ticker = normalizeTicker(searchQuery.value);
    if (!ticker) return;
    searchQuery.value = "";
    searchOpen.value = false;
    await selectTicker(ticker, ticker);
  }

  async function selectSearchResult(result) {
    searchQuery.value = "";
    searchOpen.value = false;
    await selectTicker(result.ticker, result.name || result.ticker);
  }

  function openAlertModal() {
    alertForm.ticker = currentTicker.value;
    alertModalOpen.value = true;
  }

  function closeAlertModal() {
    alertModalOpen.value = false;
  }

  function updateAlertField(key, value) {
    alertForm[key] = value;
  }

  function saveAlert() {
    const numericValue = Number(alertForm.value);
    if (!alertForm.ticker || Number.isNaN(numericValue)) {
      pushNotification({ icon: "⚠️", title: "警報設定失敗", msg: "請完整填寫股票代號與數值", type: "error" });
      return;
    }
    const record = {
      ticker: normalizeTicker(alertForm.ticker || currentTicker.value),
      type: alertForm.type,
      cond: alertForm.cond,
      value: numericValue,
      active: true,
      triggered: false,
    };
    alerts.value = [...alerts.value, record];
    alertModalOpen.value = false;
    alertForm.value = "";
    pushNotification({ icon: "🔔", title: "警報已設定", msg: `${record.ticker} ${record.cond} ${record.value}`, type: "success" });
  }

  function updateBacktestField(key, value) {
    backtestForm[key] = ["capital", "fee", "sl", "tp"].includes(key) ? Number(value) : value;
  }

  function runBacktest() {
    const result = runBacktestSimulation(ohlcData.value, {
      strategy: backtestForm.strategy,
      start: backtestForm.start,
      end: backtestForm.end,
      capital: Number(backtestForm.capital),
      fee: Number(backtestForm.fee) / 100,
      sl: Number(backtestForm.sl) / 100,
      tp: Number(backtestForm.tp) / 100,
    });
    if (result.error) {
      backtestResult.value = null;
      pushNotification({ icon: "⚠️", title: "資料不足", msg: result.error, type: "error" });
      return;
    }
    backtestResult.value = result;
    pushNotification({
      icon: "📊",
      title: "回測完成",
      msg: `${result.strategy} — ${result.totalReturn >= 0 ? "+" : ""}${result.totalReturn.toFixed(2)}%`,
      type: "success",
    });
  }

  function updateClock() {
    const now = new Date();
    clockTime.value = now.toLocaleString("zh-TW", { hour12: false });
    const hours = now.getUTCHours() + 8;
    const minutesOfDay = hours * 60 + now.getUTCMinutes();
    const weekday = now.getDay();
    marketStatus.tseOpen = minutesOfDay >= 9 * 60 && minutesOfDay < 13 * 60 + 30 && weekday >= 1 && weekday <= 5;
    marketStatus.hkOpen = minutesOfDay >= 9 * 60 + 30 && minutesOfDay < 16 * 60 && weekday >= 1 && weekday <= 5;
  }

  onMounted(async () => {
    updateClock();
    clockTimer = window.setInterval(updateClock, 1000);
    connectWs();
    await loadWatchlist();
    await loadKline(currentTicker.value, currentPeriod.value, currentInterval.value);
    watchlistTimer = window.setInterval(loadWatchlist, 60000);
  });

  onBeforeUnmount(() => {
    if (clockTimer) clearInterval(clockTimer);
    if (watchlistTimer) clearInterval(watchlistTimer);
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer);
    if (ws && ws.readyState < 2) ws.close();
  });

  return {
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
    fmtPrice,
    fmtVol,
    fmtMktCap,
  };
}
