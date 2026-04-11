function normalizeBaseUrl(baseUrl = "") {
  return String(baseUrl || "").replace(/\/$/, "");
}

function buildJsonRequest(method, body) {
  return {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  };
}

export function createDashboardApi({ baseUrl = "" } = {}) {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);

  async function request(path, options = {}) {
    const response = await fetch(`${normalizedBaseUrl}${path}`, options);
    const contentType = response.headers?.get?.("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      const error = new Error(payload?.detail || `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  return {
    searchSymbols(query) {
      return request(`/api/search?q=${encodeURIComponent(query)}`);
    },
    getOhlc(ticker, options = {}) {
      const params = new URLSearchParams();
      if (options.period) params.set("period", String(options.period));
      if (options.interval) params.set("interval", String(options.interval));
      const query = params.toString();
      return request(`/api/ohlc/${encodeURIComponent(ticker)}${query ? `?${query}` : ""}`);
    },
    getFutoptOhlc(ticker, options = {}) {
      const params = new URLSearchParams();
      if (options.period) params.set("period", String(options.period));
      if (options.interval) params.set("interval", String(options.interval));
      const query = params.toString();
      return request(`/api/futopt/ohlc/${encodeURIComponent(ticker)}${query ? `?${query}` : ""}`);
    },
    getFubonSnapshot(market, options = {}) {
      const params = new URLSearchParams();
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/fubon/snapshot/${encodeURIComponent(market)}${query ? `?${query}` : ""}`);
    },
    getFubonMovers(market, options = {}) {
      const params = new URLSearchParams();
      if (options.direction) params.set("direction", String(options.direction));
      if (options.change) params.set("change", String(options.change));
      if (options.limit != null) params.set("limit", String(options.limit));
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/fubon/movers/${encodeURIComponent(market)}${query ? `?${query}` : ""}`);
    },
    getFubonActives(market, options = {}) {
      const params = new URLSearchParams();
      if (options.trade) params.set("trade", String(options.trade));
      if (options.limit != null) params.set("limit", String(options.limit));
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/fubon/actives/${encodeURIComponent(market)}${query ? `?${query}` : ""}`);
    },
    listWatchlist() {
      return request("/api/watchlist");
    },
    createWatchlistGroup(payload) {
      return request("/api/watchlist/groups", buildJsonRequest("POST", payload));
    },
    updateWatchlistGroup(groupId, payload) {
      return request(`/api/watchlist/groups/${groupId}`, buildJsonRequest("PATCH", payload));
    },
    deleteWatchlistGroup(groupId) {
      return request(`/api/watchlist/groups/${groupId}`, { method: "DELETE" });
    },
    createWatchlistItem(payload) {
      return request("/api/watchlist/items", buildJsonRequest("POST", payload));
    },
    deleteWatchlistItem(itemId) {
      return request(`/api/watchlist/items/${itemId}`, { method: "DELETE" });
    },
    reorderWatchlistItems(groupId, itemIds) {
      return request(`/api/watchlist/groups/${groupId}/items/order`, buildJsonRequest("PUT", {
        item_ids: itemIds,
      }));
    },
    listWorkspaces() {
      return request("/api/workspaces");
    },
    getWorkspace(workspaceId) {
      return request(`/api/workspaces/${workspaceId}`);
    },
    createWorkspace(payload) {
      return request("/api/workspaces", buildJsonRequest("POST", payload));
    },
    updateWorkspace(workspaceId, payload) {
      return request(`/api/workspaces/${workspaceId}`, buildJsonRequest("PUT", payload));
    },
    deleteWorkspace(workspaceId) {
      return request(`/api/workspaces/${workspaceId}`, { method: "DELETE" });
    },
    listAlerts() {
      return request("/api/alerts");
    },
    createAlert(payload) {
      return request("/api/alerts", buildJsonRequest("POST", payload));
    },
    updateAlert(alertId, payload) {
      return request(`/api/alerts/${alertId}`, buildJsonRequest("PATCH", payload));
    },
    listAlertTriggers(alertId, options = {}) {
      const params = new URLSearchParams();
      if (options.limit != null) params.set("limit", String(options.limit));
      const query = params.toString();
      return request(`/api/alerts/${alertId}/triggers${query ? `?${query}` : ""}`);
    },
    deleteAlert(alertId) {
      return request(`/api/alerts/${alertId}`, { method: "DELETE" });
    },
    listNotifications(options = {}) {
      const params = new URLSearchParams();
      if (options.unreadOnly) params.set("unread_only", "true");
      if (options.limit != null) params.set("limit", String(options.limit));
      const query = params.toString();
      return request(`/api/notifications${query ? `?${query}` : ""}`);
    },
    markNotificationRead(notificationId) {
      return request(`/api/notifications/${notificationId}/read`, { method: "POST" });
    },
    setNotificationReadState(notificationId, read) {
      return request(`/api/notifications/${notificationId}/read`, buildJsonRequest("PATCH", { read }));
    },
    listJournalTrades(options = {}) {
      const params = new URLSearchParams();
      if (options.ticker) params.set("ticker", String(options.ticker));
      if (options.market) params.set("market", String(options.market));
      if (options.strategy_code) params.set("strategy_code", String(options.strategy_code));
      if (options.tag) params.set("tag", String(options.tag));
      if (options.search) params.set("search", String(options.search));
      if (options.limit != null) params.set("limit", String(options.limit));
      const query = params.toString();
      return request(`/api/journal/trades${query ? `?${query}` : ""}`);
    },
    getJournalTrade(entryId) {
      return request(`/api/journal/trades/${entryId}`);
    },
    listJournalFilterPresets() {
      return request("/api/journal/presets");
    },
    createJournalFilterPreset(payload) {
      return request("/api/journal/presets", buildJsonRequest("POST", payload));
    },
    updateJournalFilterPreset(presetId, payload) {
      return request(`/api/journal/presets/${presetId}`, buildJsonRequest("PUT", payload));
    },
    deleteJournalFilterPreset(presetId) {
      return request(`/api/journal/presets/${presetId}`, { method: "DELETE" });
    },
    markJournalFilterPresetUsed(presetId) {
      return request(`/api/journal/presets/${presetId}/use`, { method: "POST" });
    },
    createJournalTrade(payload) {
      return request("/api/journal/trades", buildJsonRequest("POST", payload));
    },
    updateJournalTrade(entryId, payload) {
      return request(`/api/journal/trades/${entryId}`, buildJsonRequest("PATCH", payload));
    },
    deleteJournalTrade(entryId) {
      return request(`/api/journal/trades/${entryId}`, { method: "DELETE" });
    },
    getJournalTradeStats(options = {}) {
      const params = new URLSearchParams();
      if (options.ticker) params.set("ticker", String(options.ticker));
      if (options.market) params.set("market", String(options.market));
      if (options.strategy_code) params.set("strategy_code", String(options.strategy_code));
      if (options.tag) params.set("tag", String(options.tag));
      if (options.search) params.set("search", String(options.search));
      const query = params.toString();
      return request(`/api/journal/trades/stats${query ? `?${query}` : ""}`);
    },
    listBacktestStrategies() {
      return request("/api/backtests/strategies");
    },
    listBacktestRuns(options = {}) {
      const params = new URLSearchParams();
      if (options.ticker) params.set("ticker", String(options.ticker));
      if (options.limit != null) params.set("limit", String(options.limit));
      const query = params.toString();
      return request(`/api/backtests/runs${query ? `?${query}` : ""}`);
    },
    getBacktestRun(runId) {
      return request(`/api/backtests/runs/${runId}`);
    },
    createBacktestRun(payload) {
      return request("/api/backtests/runs", buildJsonRequest("POST", payload));
    },
    getQuote(ticker) {
      return request(`/api/quote/${encodeURIComponent(ticker)}`);
    },
    getFutoptQuote(ticker) {
      return request(`/api/futopt/quote/${encodeURIComponent(ticker)}`);
    },
    listEventCalendar(options = {}) {
      const params = new URLSearchParams();
      if (options.days != null) params.set("days", String(options.days));
      if (options.limit != null) params.set("limit", String(options.limit));
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/events/calendar${query ? `?${query}` : ""}`);
    },
    getTickerEvents(ticker, options = {}) {
      const params = new URLSearchParams();
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/events/${encodeURIComponent(ticker)}${query ? `?${query}` : ""}`);
    },
    listNews(options = {}) {
      const params = new URLSearchParams();
      if (options.limit != null) params.set("limit", String(options.limit));
      const query = params.toString();
      return request(`/api/news${query ? `?${query}` : ""}`);
    },
    getTickerNews(ticker, options = {}) {
      const params = new URLSearchParams();
      if (options.limit != null) params.set("limit", String(options.limit));
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/news/${encodeURIComponent(ticker)}${query ? `?${query}` : ""}`);
    },
    getMacroDashboard(options = {}) {
      const params = new URLSearchParams();
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/market/macro${query ? `?${query}` : ""}`);
    },
    getFundamentals(ticker, options = {}) {
      const params = new URLSearchParams();
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/fundamentals/${encodeURIComponent(ticker)}${query ? `?${query}` : ""}`);
    },
    getFundamentalEvents(ticker, options = {}) {
      const params = new URLSearchParams();
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/fundamentals/${encodeURIComponent(ticker)}/events${query ? `?${query}` : ""}`);
    },
    getTaiwanChips(ticker, options = {}) {
      const params = new URLSearchParams();
      if (options.refresh) params.set("refresh", "true");
      const query = params.toString();
      return request(`/api/tw/chips/${encodeURIComponent(ticker)}${query ? `?${query}` : ""}`);
    },
    listScreenerPresets() {
      return request("/api/screener/presets");
    },
    createScreenerPreset(payload) {
      return request("/api/screener/presets", buildJsonRequest("POST", payload));
    },
    updateScreenerPreset(presetId, payload) {
      return request(`/api/screener/presets/${presetId}`, buildJsonRequest("PUT", payload));
    },
    deleteScreenerPreset(presetId) {
      return request(`/api/screener/presets/${presetId}`, { method: "DELETE" });
    },
    runScreener(payload) {
      return request("/api/screener/run", buildJsonRequest("POST", payload));
    },
  };
}

export const dashboardApi = createDashboardApi();
