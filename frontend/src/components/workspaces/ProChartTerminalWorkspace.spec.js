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
      bid: 210.4,
      ask: 210.5,
      bids: [{ price: 210.4, size: 12 }],
      asks: [{ price: 210.5, size: 9 }],
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

function createGlobal() {
  return {
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
      BidAskPanel: {
        name: "BidAskPanel",
        template: "<aside class='bid-ask-panel-stub'>book</aside>",
      },
    },
  };
}

describe("ProChartTerminalWorkspace", () => {
  it("shows the book panel alongside the chart in normal mode", () => {
    const wrapper = mount(ProChartTerminalWorkspace, {
      props: createProps(),
      global: createGlobal(),
    });

    expect(wrapper.find(".terminal-commandbar").exists()).toBe(true);
    expect(wrapper.find(".chart-workspace-stub").exists()).toBe(true);
    expect(wrapper.find(".bid-ask-panel-stub").exists()).toBe(true);
    expect(wrapper.findAll(".terminal-action")).toHaveLength(4);
  });

  it("only renders the commandbar watchlist toggle when the left rail is collapsed", () => {
    const wrapper = mount(ProChartTerminalWorkspace, {
      props: createProps(),
      global: createGlobal(),
    });

    const watchlistButtons = wrapper.findAll("button").filter((button) => button.text().includes("觀察池"));

    expect(watchlistButtons).toHaveLength(1);
    expect(wrapper.find(".terminal-collapsed-toggle.left").exists()).toBe(false);
  });

  it("keeps chart-focused zen mode free of command chrome", () => {
    const wrapper = mount(ProChartTerminalWorkspace, {
      props: {
        ...createProps(),
        chartFullscreen: true,
      },
      global: createGlobal(),
    });

    expect(wrapper.find(".terminal-commandbar").exists()).toBe(false);
    expect(wrapper.find(".ticker-rail-stub").exists()).toBe(false);
    expect(wrapper.find(".utility-drawer-stub").exists()).toBe(false);
    expect(wrapper.find(".bid-ask-panel-stub").exists()).toBe(false);
    expect(wrapper.find(".terminal-page").classes()).toContain("is-chart-fullscreen");
    expect(wrapper.find(".chart-workspace-stub").exists()).toBe(true);
  });
});
