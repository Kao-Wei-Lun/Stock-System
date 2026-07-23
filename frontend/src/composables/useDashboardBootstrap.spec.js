import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, ref } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";


const apiState = vi.hoisted(() => ({ calls: [], futoptOhlcHandler: null, cachedOhlc: null, cacheWrites: [] }));

vi.mock("../services/terminalCache", () => ({
  createTerminalCache: () => ({
    readOhlc: () => Promise.resolve(apiState.cachedOhlc),
    writeOhlc: (payload) => { apiState.cacheWrites.push(payload); return Promise.resolve(true); },
    readWatchlistMetadata: () => Promise.resolve(null),
    writeWatchlistMetadata: () => Promise.resolve(true),
    clear: () => Promise.resolve(),
  }),
}));

vi.mock("../api/dashboardApi", () => ({
  createDashboardApi: () => new Proxy({
    getFutoptOhlc(ticker, options) {
      apiState.calls.push({ method: "getFutoptOhlc", ticker, options });
      if (apiState.futoptOhlcHandler) return apiState.futoptOhlcHandler(ticker, options);
      return Promise.resolve({ ticker, data: [], refresh_status: "not_needed", is_stale: false });
    },
    getFutoptQuote(ticker) {
      apiState.calls.push({ method: "getFutoptQuote", ticker });
      return Promise.resolve({ ticker, price: 100, source: "test" });
    },
    listWorkspaces() {
      apiState.calls.push({ method: "listWorkspaces" });
      return Promise.resolve({ items: [] });
    },
    listWatchlistMetadata() {
      apiState.calls.push({ method: "listWatchlistMetadata" });
      return Promise.resolve({ groups: [] });
    },
    listNotifications() {
      apiState.calls.push({ method: "listNotifications" });
      return Promise.resolve({ items: [] });
    },
  }, {
    get(target, property) {
      if (property in target) return target[property];
      return (...args) => {
        apiState.calls.push({ method: String(property), args });
        return Promise.resolve({ items: [], data: [] });
      };
    },
  }),
}));

vi.mock("./dashboard/dashboardRealtime", () => ({
  createDashboardRealtime: () => ({
    wsConnected: ref(false),
    connect: vi.fn(),
    disconnect: vi.fn(),
    subscribeTicker: vi.fn(),
    unsubscribeTicker: vi.fn(),
  }),
}));

import { useDashboard } from "./useDashboard";


function mountDashboard(options) {
  let dashboard;
  const Host = defineComponent({
    setup() {
      dashboard = useDashboard(options);
      return {};
    },
    template: "<div />",
  });
  const wrapper = mount(Host);
  return { wrapper, get dashboard() { return dashboard; } };
}

function candle(close) {
  return {
    date: "2026-07-23T09:00:00+08:00",
    open: close,
    high: close,
    low: close,
    close,
    volume: 1,
  };
}

describe("useDashboard route bootstrap", () => {
  beforeEach(() => {
    apiState.calls = [];
    apiState.futoptOhlcHandler = null;
    apiState.cachedOhlc = null;
    apiState.cacheWrites = [];
    localStorage.clear();
  });

  it("loads only terminal critical resources during terminal startup", async () => {
    const mounted = mountDashboard({
      initialWorkspacePage: "terminal",
      initialTicker: "*TMFF",
      initialRightTab: "alerts",
    });
    await mounted.dashboard.bootstrapWorkspace("terminal", "alerts");
    await flushPromises();

    const methods = apiState.calls.map((call) => call.method);
    expect(methods).toEqual(expect.arrayContaining([
      "getFutoptOhlc",
      "listWorkspaces",
      "listWatchlistMetadata",
      "listNotifications",
    ]));
    expect(methods).not.toEqual(expect.arrayContaining([
      "getFubonSnapshot",
      "listTradeJournal",
      "listBacktestRuns",
      "runScreener",
      "getAssetPortfolio",
      "listAlerts",
    ]));
    mounted.wrapper.unmount();
  });

  it("loads market snapshots only after entering overview", async () => {
    const mounted = mountDashboard({
      initialWorkspacePage: "terminal",
      initialTicker: "*TMFF",
    });
    await flushPromises();
    expect(apiState.calls.some((call) => call.method === "getFubonSnapshotSummary")).toBe(false);

    await mounted.dashboard.bootstrapWorkspace("overview");

    expect(apiState.calls.some((call) => call.method === "getFubonSnapshotSummary")).toBe(true);
    mounted.wrapper.unmount();
  });

  it("loads journal data only when the journal tab is first opened", async () => {
    const mounted = mountDashboard({
      initialWorkspacePage: "terminal",
      initialTicker: "*TMFF",
    });
    await flushPromises();
    expect(apiState.calls.some((call) => call.method === "listJournalTrades")).toBe(false);

    await mounted.dashboard.setRightTab("journal");

    expect(apiState.calls.some((call) => call.method === "listJournalTrades")).toBe(true);
    expect(apiState.calls.some((call) => call.method === "listJournalFilterPresets")).toBe(true);
    mounted.wrapper.unmount();
  });

  it("does not apply a slow prior ticker response after a fast ticker switch", async () => {
    const pending = new Map();
    apiState.futoptOhlcHandler = (ticker) => new Promise((resolve) => pending.set(ticker, resolve));
    const mounted = mountDashboard({
      initialWorkspacePage: "terminal",
      initialTicker: "*TXFF",
    });
    await flushPromises();

    const switchPromise = mounted.dashboard.selectTicker("*TMFF", "微型臺指");
    await flushPromises();
    pending.get("*TMFF")({ ticker: "*TMFF", data: [candle(200)], refresh_status: "refreshed" });
    await switchPromise;
    pending.get("*TXFF")({ ticker: "*TXFF", data: [candle(100)], refresh_status: "refreshed" });
    await flushPromises();

    expect(mounted.dashboard.currentTicker.value).toBe("*TMFF");
    expect(mounted.dashboard.ohlcData.value.at(-1).close).toBe(200);
    mounted.wrapper.unmount();
  });

  it("paints a valid cache first and replaces it with the database response", async () => {
    let resolveBackend;
    apiState.cachedOhlc = { savedAt: 123, rows: [candle(90)] };
    apiState.futoptOhlcHandler = () => new Promise((resolve) => { resolveBackend = resolve; });
    const mounted = mountDashboard({
      initialWorkspacePage: "terminal",
      initialTicker: "*TMFF",
    });
    await flushPromises();

    expect(mounted.dashboard.klineDataOrigin.value).toBe("cache");
    expect(mounted.dashboard.ohlcData.value.at(-1).close).toBe(90);
    expect(mounted.dashboard.chartLoading.value).toBe(false);

    resolveBackend({ ticker: "*TMFF", data: [candle(100)], refresh_status: "not_needed" });
    await flushPromises();

    expect(mounted.dashboard.klineDataOrigin.value).toBe("database");
    expect(mounted.dashboard.ohlcData.value.at(-1).close).toBe(100);
    expect(apiState.cacheWrites.at(-1).rows.at(-1).close).toBe(100);
    mounted.wrapper.unmount();
  });
});
