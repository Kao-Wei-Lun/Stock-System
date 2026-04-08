import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import ProChartTerminalWorkspace from "./ProChartTerminalWorkspace.vue";

function createProps() {
  return {
    groups: [],
    activeGroupId: null,
    watchlist: [],
    timeframeOptions: [],
    currentTicker: "AAPL",
    currentName: "Apple",
    currentPeriod: "1y",
    currentInterval: "1d",
    quote: {
      price: 210.5,
      change_pct: 1.23,
    },
    activeTool: "cursor",
    activePanels: { macd: true, stoch: true },
    klineDisplayMode: "day",
    chartEngineMode: "lwc",
    cleanChartMode: false,
    chartLayout: "single",
    chartLoading: false,
    loadingMessage: "",
    crosshair: { visible: false, absoluteIndex: null },
    ohlcData: [],
    activeInd: {},
    indicatorSettings: {},
    drawings: [],
    selectedDrawingId: null,
    workspacePresets: [],
    activeWorkspacePresetId: null,
    syncingCurrent: false,
    compareSeries: [],
    comparisonMode: "percent",
    institutionalOverlay: null,
    tickerEvents: [],
    macroSummary: null,
    alerts: [],
    alertTriggerLogs: {},
    alertLogLoading: {},
    expandedAlertLogId: null,
    journalForm: {
      ticker: "AAPL",
      attachments: [],
    },
    journalLoading: false,
    rightTab: "alerts",
    leftCollapsed: true,
    rightCollapsed: true,
    chartFullscreen: false,
  };
}

describe("ProChartTerminalWorkspace", () => {
  it("keeps chart-focused zen mode free of command chrome", () => {
    const wrapper = mount(ProChartTerminalWorkspace, {
      props: {
        ...createProps(),
        chartFullscreen: true,
      },
      global: {
        stubs: {
          ChartWorkspace: {
            name: "ChartWorkspace",
            template: "<div class='chart-workspace-stub'>chart</div>",
          },
          TerminalTickerRail: {
            name: "TerminalTickerRail",
            template: "<aside class='ticker-rail-stub'>rail</aside>",
          },
          TerminalUtilityDrawer: {
            name: "TerminalUtilityDrawer",
            template: "<aside class='utility-drawer-stub'>drawer</aside>",
          },
        },
      },
    });

    expect(wrapper.find(".terminal-commandbar").exists()).toBe(false);
    expect(wrapper.find(".ticker-rail-stub").exists()).toBe(false);
    expect(wrapper.find(".utility-drawer-stub").exists()).toBe(false);
    expect(wrapper.find(".terminal-page").classes()).toContain("is-chart-fullscreen");
    expect(wrapper.find(".chart-workspace-stub").exists()).toBe(true);
  });
});
