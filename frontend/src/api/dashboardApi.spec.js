import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createDashboardApi } from "./dashboardApi";

function jsonResponse(payload, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get(name) {
        return name === "content-type" ? "application/json" : "";
      },
    },
    json: async () => payload,
  });
}

describe("dashboardApi", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates workspaces with JSON payloads", async () => {
    globalThis.fetch.mockImplementation(() => jsonResponse({ id: 9, name: "Morning Desk" }));
    const api = createDashboardApi({ baseUrl: "http://127.0.0.1:8001/" });

    const payload = {
      name: "Morning Desk",
      chart_layout: "single",
      payload: { drawings: [] },
    };
    const result = await api.createWorkspace(payload);

    expect(result).toEqual({ id: 9, name: "Morning Desk" });
    expect(globalThis.fetch).toHaveBeenCalledWith("http://127.0.0.1:8001/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  });

  it("builds notification query strings", async () => {
    globalThis.fetch.mockImplementation(() => jsonResponse({ items: [] }));
    const api = createDashboardApi();

    await api.listNotifications({ unreadOnly: true, limit: 20 });

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/notifications?unread_only=true&limit=20", {});
  });

  it("builds alert trigger log query strings", async () => {
    globalThis.fetch.mockImplementation(() => jsonResponse({ items: [] }));
    const api = createDashboardApi();

    await api.listAlertTriggers(7, { limit: 10 });

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/alerts/7/triggers?limit=10", {});
  });

  it("marks notifications as read", async () => {
    globalThis.fetch.mockImplementation(() => jsonResponse({ id: 5, read_at: "2026-03-29T03:00:00+00:00" }));
    const api = createDashboardApi({ baseUrl: "http://localhost:8001" });

    const result = await api.markNotificationRead(5);

    expect(result.read_at).toBe("2026-03-29T03:00:00+00:00");
    expect(globalThis.fetch).toHaveBeenCalledWith("http://localhost:8001/api/notifications/5/read", {
      method: "POST",
    });
  });

  it("requests quote metadata from the quote endpoint", async () => {
    globalThis.fetch.mockImplementation(() =>
      jsonResponse({
        ticker: "AAPL",
        source: "yahoo_finance",
        quote_type: "delayed_snapshot",
        is_delayed: true,
      }),
    );
    const api = createDashboardApi({ baseUrl: "http://localhost:8001" });

    const result = await api.getQuote("AAPL");

    expect(result.quote_type).toBe("delayed_snapshot");
    expect(globalThis.fetch).toHaveBeenCalledWith("http://localhost:8001/api/quote/AAPL", {});
  });

  it("requests futopt quote and ohlc payloads from dedicated endpoints", async () => {
    globalThis.fetch
      .mockImplementationOnce(() => jsonResponse({ ticker: "TXFE6", is_delayed: false }))
      .mockImplementationOnce(() => jsonResponse({ ticker: "TXFE6", data: [] }));
    const api = createDashboardApi({ baseUrl: "http://localhost:8001" });

    const quote = await api.getFutoptQuote("TXF");
    const ohlc = await api.getFutoptOhlc("TXF", { period: "5d", interval: "5m" });

    expect(quote.ticker).toBe("TXFE6");
    expect(ohlc.ticker).toBe("TXFE6");
    expect(globalThis.fetch).toHaveBeenNthCalledWith(1, "http://localhost:8001/api/futopt/quote/TXF", {});
    expect(globalThis.fetch).toHaveBeenNthCalledWith(2, "http://localhost:8001/api/futopt/ohlc/TXF?period=5d&interval=5m", {});
  });

  it("creates persisted backtest runs", async () => {
    globalThis.fetch.mockImplementation(() => jsonResponse({ id: 21, strategy_key: "ma_cross" }));
    const api = createDashboardApi({ baseUrl: "http://localhost:8001" });

    const payload = {
      ticker: "AAPL",
      strategy: "MA 黃金/死亡交叉",
      start: "2024-01-01",
      end: "2024-12-31",
      capital: 100000,
    };
    const result = await api.createBacktestRun(payload);

    expect(result.id).toBe(21);
    expect(globalThis.fetch).toHaveBeenCalledWith("http://localhost:8001/api/backtests/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  });

  it("builds backtest history query strings", async () => {
    globalThis.fetch.mockImplementation(() => jsonResponse({ items: [] }));
    const api = createDashboardApi();

    await api.listBacktestRuns({ ticker: "AAPL", limit: 10 });

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/backtests/runs?ticker=AAPL&limit=10", {});
  });

  it("creates journal trades with JSON payloads", async () => {
    globalThis.fetch.mockImplementation(() => jsonResponse({ id: 11, ticker: "AAPL" }));
    const api = createDashboardApi();

    await api.createJournalTrade({
      ticker: "AAPL",
      entry_time: "2026-04-01T09:00",
      entry_price: 200,
      size: 10,
    });

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/journal/trades", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticker: "AAPL",
        entry_time: "2026-04-01T09:00",
        entry_price: 200,
        size: 10,
      }),
    });
  });

  it("manages journal filter presets", async () => {
    globalThis.fetch
      .mockImplementationOnce(() => jsonResponse({ items: [] }))
      .mockImplementationOnce(() => jsonResponse({ id: 4, name: "高風險日" }))
      .mockImplementationOnce(() => jsonResponse({ ok: true, preset_id: 4 }))
      .mockImplementationOnce(() => jsonResponse({ id: 4, use_count: 1 }));
    const api = createDashboardApi();

    await api.listJournalFilterPresets();
    await api.createJournalFilterPreset({
      name: "高風險日",
      scope: "all",
      filters: { tag: "市場:防守控倉" },
    });
    await api.deleteJournalFilterPreset(4);
    await api.markJournalFilterPresetUsed(4);

    expect(globalThis.fetch).toHaveBeenNthCalledWith(1, "/api/journal/presets", {});
    expect(globalThis.fetch).toHaveBeenNthCalledWith(2, "/api/journal/presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: "高風險日",
        scope: "all",
        filters: { tag: "市場:防守控倉" },
      }),
    });
    expect(globalThis.fetch).toHaveBeenNthCalledWith(3, "/api/journal/presets/4", {
      method: "DELETE",
    });
    expect(globalThis.fetch).toHaveBeenNthCalledWith(4, "/api/journal/presets/4/use", {
      method: "POST",
    });
  });

  it("patches notification read state", async () => {
    globalThis.fetch.mockImplementation(() => jsonResponse({ id: 5, read_at: null }));
    const api = createDashboardApi();

    await api.setNotificationReadState(5, false);

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/notifications/5/read", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ read: false }),
    });
  });

  it("builds event and macro query strings", async () => {
    globalThis.fetch.mockImplementation(() => jsonResponse({ items: [] }));
    const api = createDashboardApi();

    await api.listEventCalendar({ days: 14, limit: 10, refresh: true });
    await api.getMacroDashboard({ refresh: true });

    expect(globalThis.fetch).toHaveBeenNthCalledWith(1, "/api/events/calendar?days=14&limit=10&refresh=true", {});
    expect(globalThis.fetch).toHaveBeenNthCalledWith(2, "/api/market/macro?refresh=true", {});
  });

  it("posts screener runs and manages screener presets", async () => {
    globalThis.fetch
      .mockImplementationOnce(() => jsonResponse({ total: 1, items: [] }))
      .mockImplementationOnce(() => jsonResponse({ id: 3, name: "Momentum" }));
    const api = createDashboardApi();

    await api.runScreener({ filters: { market: "US" } });
    await api.createScreenerPreset({ name: "Momentum", filters: { market: "US" } });

    expect(globalThis.fetch).toHaveBeenNthCalledWith(1, "/api/screener/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filters: { market: "US" } }),
    });
    expect(globalThis.fetch).toHaveBeenNthCalledWith(2, "/api/screener/presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Momentum", filters: { market: "US" } }),
    });
  });
});
