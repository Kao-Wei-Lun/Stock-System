import { reactive, ref } from "vue";
import { describe, expect, it, vi } from "vitest";

import {
  createDashboardComparison,
  normalizeComparisonTickers,
} from "./dashboardComparison";
import { createDashboardMarketSync } from "./dashboardMarketSync";
import {
  createDashboardNotifications,
  mapDashboardNotification,
} from "./dashboardNotifications";
import { createDashboardTerminalState } from "./dashboardTerminalState";
import { createLazyDashboardWorkspacePersistence } from "./lazyDashboardWorkspacePersistence";
import {
  createDashboardWorkspacePersistence,
  sameWorkspaceId,
} from "./dashboardWorkspacePersistence";

const normalizeTicker = (value) => String(value || "").trim().toUpperCase();

describe("dashboard facade controllers", () => {
  it("creates isolated terminal refs with the requested initial state", () => {
    const state = createDashboardTerminalState({
      ticker: "2330.TW",
      period: "5d",
      interval: "1m",
      klineDisplayMode: "day",
      chartEngineMode: "lwc",
      cleanChartMode: true,
      chartLayout: "double",
    });

    expect(state.currentTicker.value).toBe("2330.TW");
    expect(state.currentInterval.value).toBe("1m");
    expect(state.chartEngineMode.value).toBe("lwc");
    expect(state.cleanChartMode.value).toBe(true);
    expect(state.rawOhlcData.value).toEqual([]);
    state.currentTicker.value = "2317.TW";
    expect(state.currentName.value).toBe("載入中...");
  });

  it("maps persisted macro notifications without leaking MARKET as a ticker", () => {
    const mapped = mapDashboardNotification(
      {
        id: 7,
        category: "system",
        level: "warning",
        title: "市場提醒",
        message: "風險升高",
        created_at: "2026-07-24T08:00:00+08:00",
        payload: {
          ticker: "MARKET",
          context_tags: ["觀察群組:大盤", "波動"],
          macro_summary: { risk: "high" },
        },
      },
      () => "08:00",
    );

    expect(mapped).toMatchObject({
      id: "remote-7",
      ticker: null,
      workspaceTarget: "macro",
      contextGroupName: "大盤",
      time: "08:00",
    });
  });

  it("keeps local and remote notification mutations behind one controller", async () => {
    const localNotifications = ref([]);
    const remoteNotifications = ref([]);
    const scheduled = [];
    const dashboardApi = {
      listNotifications: vi.fn().mockResolvedValue({
        items: [{
          id: 4,
          level: "info",
          title: "資料",
          message: "完成",
          payload: {},
        }],
      }),
      markNotificationRead: vi.fn().mockResolvedValue({
        id: 4,
        level: "info",
        title: "資料",
        message: "完成",
        read_at: "2026-07-24T08:01:00+08:00",
        payload: {},
      }),
      setNotificationReadState: vi.fn(),
    };
    const controller = createDashboardNotifications({
      dashboardApi,
      localNotifications,
      remoteNotifications,
      formatTimestamp: () => "08:00",
      now: () => new Date("2026-07-24T00:00:00.000Z"),
      random: () => 0.25,
      schedule: (callback, delay) => scheduled.push({ callback, delay }),
    });

    controller.pushNotification({ icon: "✅", title: "完成", msg: "本機" });
    expect(localNotifications.value).toHaveLength(1);
    expect(scheduled[0].delay).toBe(6000);
    scheduled[0].callback();
    expect(localNotifications.value).toEqual([]);

    await controller.loadNotifications();
    expect(remoteNotifications.value[0].id).toBe("remote-4");
    await controller.dismissNotification("remote-4");
    expect(dashboardApi.markNotificationRead).toHaveBeenCalledWith(4);
    expect(remoteNotifications.value[0].read).toBe(true);
  });

  it("normalizes, de-duplicates, excludes the main ticker, and caps comparison tickers", () => {
    expect(normalizeComparisonTickers(
      [" aapl ", "MSFT", "AAPL", "TSLA", "NVDA", "AMZN", "META"],
      "msft",
      normalizeTicker,
    )).toEqual(["AAPL", "TSLA", "NVDA", "AMZN", "META"]);
  });

  it("loads comparison data while discarding stale request results", async () => {
    const compareTickers = ref([]);
    const rawCompareSeries = ref([{ ticker: "OLD" }]);
    let requestSequence = 2;
    const dashboardApi = {
      getOhlc: vi.fn().mockResolvedValue({
        data: [{ close: 100 }, { close: 110 }],
      }),
      getFutoptOhlc: vi.fn(),
    };
    const controller = createDashboardComparison({
      dashboardApi,
      compareTickers,
      rawCompareSeries,
      comparisonMode: ref("percent"),
      currentTicker: ref("MSFT"),
      currentPeriod: ref("1y"),
      currentInterval: ref("1d"),
      klineDisplayMode: ref("day"),
      normalizeTicker,
      isFutoptTicker: () => false,
      resolveFutoptInterval: (value) => value,
      resolveFutoptPeriod: (value) => value,
      resolveTimeframeInterval: (_period, interval) => interval,
      getEffectiveKlineDisplayMode: (mode) => mode,
      getExpandedFetchPeriod: (period) => period,
      getDisplayNameForTicker: (ticker) => `Name ${ticker}`,
      getRequestSequence: () => requestSequence,
      pushNotification: vi.fn(),
    });

    await controller.loadComparisonSeries(["AAPL"], { requestToken: 1 });
    expect(rawCompareSeries.value).toEqual([{ ticker: "OLD" }]);
    requestSequence = 3;
    await controller.loadComparisonSeries(["AAPL"], { requestToken: 3 });
    expect(rawCompareSeries.value[0]).toMatchObject({
      ticker: "AAPL",
      name: "Name AAPL",
      changePct: 10,
    });
  });

  it("runs stock sync dependencies and always releases the busy state", async () => {
    const syncingCurrent = ref(false);
    const syncingAll = ref(false);
    const ensureKline = vi.fn().mockResolvedValue(undefined);
    const applyQuote = vi.fn();
    const pushNotification = vi.fn();
    const dashboardApi = {
      refreshQuote: vi.fn().mockResolvedValue({ price: 101, refresh_status: "throttled" }),
      syncFutoptOhlc: vi.fn(),
    };
    const apiFetch = vi.fn().mockResolvedValue({ synced: 3 });
    const controller = createDashboardMarketSync({
      dashboardApi,
      apiFetch,
      currentTicker: ref("2330.TW"),
      currentPeriod: ref("5d"),
      currentInterval: ref("1m"),
      syncingCurrent,
      syncingAll,
      normalizeTicker,
      isFutoptTicker: () => false,
      applyQuote,
      ensureKline,
      loadWatchlist: vi.fn(),
      loadEventCalendar: vi.fn(),
      loadMarketSnapshots: vi.fn(),
      loadMacroDashboard: vi.fn(),
      loadTickerIntelligence: vi.fn(),
      pushNotification,
    });

    await controller.syncCurrentTicker();

    expect(apiFetch).toHaveBeenCalledWith("/api/sync/2330.TW", { method: "POST" });
    expect(applyQuote).toHaveBeenCalledWith(expect.objectContaining({ price: 101 }));
    expect(ensureKline).toHaveBeenCalledWith("2330.TW", "5d", "1m", { force: true });
    expect(syncingCurrent.value).toBe(false);
    expect(pushNotification).toHaveBeenLastCalledWith(
      expect.objectContaining({ title: "同步完成", type: "success" }),
    );
  });

  it("persists and reapplies a workspace through the controller contract", async () => {
    const refs = {
      workspacePresets: ref([]),
      activeWorkspacePresetId: ref(null),
      currentTicker: ref("2330.TW"),
      currentName: ref("台積電"),
      currentPeriod: ref("5d"),
      currentInterval: ref("1m"),
      klineDisplayMode: ref("day"),
      chartEngineMode: ref("lwc"),
      cleanChartMode: ref(false),
      chartLayout: ref("single"),
      compareTickers: ref(["2317.TW"]),
      comparisonMode: ref("percent"),
      activeTool: ref("cursor"),
      leftTab: ref("watch"),
      rightTab: ref("indicators"),
      workspaceTab: ref("chart"),
      drawings: ref([]),
      selectedDrawingId: ref(null),
      rawOhlcData: ref([{ close: 1 }]),
    };
    const createdRecord = {
      id: 12,
      name: "台股",
      active_ticker: "2330.TW",
      payload: {
        currentTicker: "2330.TW",
        currentName: "台積電",
        currentPeriod: "5d",
        currentInterval: "1m",
        chartEngineMode: "lwc",
      },
    };
    const dashboardApi = {
      createWorkspace: vi.fn().mockResolvedValue(createdRecord),
      updateWorkspace: vi.fn(),
      listWorkspaces: vi.fn(),
      getWorkspace: vi.fn(),
      deleteWorkspace: vi.fn(),
    };
    const ensureKline = vi.fn().mockResolvedValue(undefined);
    const subscribeTicker = vi.fn();
    const pushNotification = vi.fn();
    const controller = createDashboardWorkspacePersistence({
      dashboardApi,
      isBrowser: () => false,
      ...refs,
      screenerFilters: reactive({ market: "TW" }),
      activeInd: reactive({ ma20: true }),
      activePanels: reactive({ macd: true }),
      indicatorSettings: reactive({ ma20: 20 }),
      crosshair: reactive({ visible: true }),
      defaultActiveInd: { ma20: true },
      defaultActivePanels: { macd: true },
      chartLayoutOptions: ["single", "double", "quad"],
      toolOptions: ["cursor", "hline"],
      workspaceTabOptions: ["chart", "events", "macro", "screener"],
      normalizeTicker,
      resolveDashboardTimeframeForTicker: (_ticker, period, interval) => ({ period, interval }),
      getEffectiveKlineDisplayMode: (mode) => mode || "day",
      normalizeChartEngineMode: (mode) => mode === "lwc" ? "lwc" : "legacy",
      normalizeDashboardRightTab: (tab) => tab || "indicators",
      createDrawingEntry: (drawing) => drawing,
      applyScreenerFilters: vi.fn(),
      clearRealtimeTicker: vi.fn(),
      unsubscribeTicker: vi.fn(),
      subscribeTicker,
      rememberRecentTicker: vi.fn(),
      ensureKline,
      loadEventCalendar: vi.fn(),
      loadTickerIntelligence: vi.fn(),
      loadMacroDashboard: vi.fn(),
      runScreener: vi.fn(),
      pushNotification,
    });

    await controller.saveWorkspacePreset(" 台股 ");
    expect(dashboardApi.createWorkspace).toHaveBeenCalledWith(
      expect.objectContaining({ name: "台股", active_ticker: "2330.TW" }),
    );
    expect(refs.activeWorkspacePresetId.value).toBe(12);
    expect(sameWorkspaceId("12", 12)).toBe(true);

    await controller.loadWorkspacePreset(12);
    expect(refs.rawOhlcData.value).toEqual([]);
    expect(ensureKline).toHaveBeenCalledWith("2330.TW", "5d", "1m", { force: true });
    expect(subscribeTicker).toHaveBeenCalledWith("2330.TW");
    expect(pushNotification).toHaveBeenLastCalledWith(
      expect.objectContaining({ title: "工作區已載入", type: "success" }),
    );
  });

  it("loads the workspace controller once and forwards concurrent actions", async () => {
    const loadModule = vi.fn().mockResolvedValue({
      createDashboardWorkspacePersistence: () => ({
        loadWorkspacePresets: vi.fn().mockResolvedValue(["ready"]),
        loadWorkspacePreset: vi.fn(),
        saveWorkspacePreset: vi.fn(),
        deleteWorkspacePreset: vi.fn(),
      }),
    });
    const facade = createLazyDashboardWorkspacePersistence({}, loadModule);

    const [first, second] = await Promise.all([
      facade.loadWorkspacePresets(),
      facade.loadWorkspacePresets(),
    ]);

    expect(loadModule).toHaveBeenCalledTimes(1);
    expect(first).toEqual(["ready"]);
    expect(second).toEqual(["ready"]);
  });
});
