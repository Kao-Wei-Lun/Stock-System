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
});
