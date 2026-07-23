import { computed, ref } from "vue";
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChartWorkspace from "./ChartWorkspace.vue";

const engineCalls = vi.hoisted(() => ({ legacy: 0, lwc: 0, legacyDispose: 0, lwcDispose: 0 }));

vi.mock("../composables/useChartEngine", () => ({
  useChartEngine: () => {
    engineCalls.legacy += 1;
    return ({
    chartMode: ref("candles"),
    priceScaleMode: ref("linear"),
    visibleData: ref([
      { date: "2026-04-01", close: 200, high: 205, low: 198, open: 199, volume: 1000 },
      { date: "2026-04-02", close: 204, high: 206, low: 201, open: 202, volume: 1200 },
      { date: "2026-04-03", close: 210, high: 212, low: 203, open: 204, volume: 1300 },
    ]),
    viewportStartIndex: ref(0),
    canvasClass: computed(() => ""),
    visibleRangeLabel: computed(() => "可視範圍"),
    visibleBarsLabel: computed(() => "0 根"),
    visibleChangeLabel: computed(() => "+0.00%"),
    visibleChangeClass: computed(() => "up"),
    zoomLabel: computed(() => "Zoom 1x"),
    yScaleLabel: computed(() => "Y 自動"),
    priceScaleModeLabel: computed(() => "線性"),
    interactionHint: computed(() => "hint"),
    canPanLeft: computed(() => false),
    canPanRight: computed(() => false),
    canZoomIn: computed(() => false),
    canZoomOut: computed(() => false),
    canUseLogScale: computed(() => false),
    canGoBackHistory: computed(() => false),
    canGoForwardHistory: computed(() => false),
    canResetYScale: computed(() => false),
    setChartMode: vi.fn(),
    setPriceScaleMode: vi.fn(),
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
    zoomYIn: vi.fn(),
    zoomYOut: vi.fn(),
    panLeft: vi.fn(),
    panRight: vi.fn(),
    goHistoryBack: vi.fn(),
    goHistoryForward: vi.fn(),
    jumpToLatest: vi.fn(),
    resetView: vi.fn(),
    resetYScale: vi.fn(),
    refreshLayout: vi.fn(),
    onMouseDown: vi.fn(),
    onMouseMove: vi.fn(),
    onMouseLeave: vi.fn(),
    onMouseUp: vi.fn(),
    onWheel: vi.fn(),
    onChartClick: vi.fn(),
    onDoubleClick: vi.fn(),
    activate: vi.fn(),
    dispose: () => { engineCalls.legacyDispose += 1; },
    });
  },
}));

vi.mock("../composables/useLWCChart", () => ({
  useLWCChart: () => {
    engineCalls.lwc += 1;
    return ({
    chartMode: ref("candles"),
    priceScaleMode: ref("linear"),
    visibleData: ref([
      { date: "2026-04-01", close: 200, high: 205, low: 198, open: 199, volume: 1000 },
      { date: "2026-04-02", close: 204, high: 206, low: 201, open: 202, volume: 1200 },
      { date: "2026-04-03", close: 210, high: 212, low: 203, open: 204, volume: 1300 },
    ]),
    viewportStartIndex: ref(0),
    canvasClass: computed(() => ""),
    visibleRangeLabel: computed(() => "å¯è¦–ç¯„åœ"),
    visibleBarsLabel: computed(() => "0 æ ¹"),
    visibleChangeLabel: computed(() => "+0.00%"),
    visibleChangeClass: computed(() => "up"),
    zoomLabel: computed(() => "Zoom 1x"),
    yScaleLabel: computed(() => "Y LWC"),
    priceScaleModeLabel: computed(() => "ç·šæ€§"),
    interactionHint: computed(() => "lwc hint"),
    canPanLeft: computed(() => false),
    canPanRight: computed(() => false),
    canZoomIn: computed(() => false),
    canZoomOut: computed(() => false),
    canUseLogScale: computed(() => false),
    canGoBackHistory: computed(() => false),
    canGoForwardHistory: computed(() => false),
    canResetYScale: computed(() => false),
    setChartMode: vi.fn(),
    setPriceScaleMode: vi.fn(),
    zoomIn: vi.fn(),
    zoomOut: vi.fn(),
    zoomYIn: vi.fn(),
    zoomYOut: vi.fn(),
    panLeft: vi.fn(),
    panRight: vi.fn(),
    goHistoryBack: vi.fn(),
    goHistoryForward: vi.fn(),
    jumpToLatest: vi.fn(),
    resetView: vi.fn(),
    resetYScale: vi.fn(),
    refreshLayout: vi.fn(),
    onMouseDown: vi.fn(),
    onMouseMove: vi.fn(),
    onMouseLeave: vi.fn(),
    onMouseUp: vi.fn(),
    onWheel: vi.fn(),
    onChartClick: vi.fn(),
    onDoubleClick: vi.fn(),
    activate: vi.fn(),
    dispose: () => { engineCalls.lwcDispose += 1; },
    });
  },
}));

function createProps() {
  return {
    currentTicker: "AAPL",
    currentName: "Apple",
    timeframeOptions: [
      { tf: "1d", iv: "1m", label: "1m" },
      { tf: "1y", iv: "1d", label: "1Y" },
    ],
    currentPeriod: "1y",
    currentInterval: "1d",
    quote: {
      price: 210.5,
      open: 208,
      high: 212,
      low: 207.8,
      volume: 123456,
      market_cap: 999999999,
      change: 5.5,
      change_pct: 2.68,
      source: "yahoo_finance",
      is_delayed: true,
      quote_timestamp: "2020-03-29T04:00:00+00:00",
      synced_at: "2020-03-29T04:00:05+00:00",
    },
    activeTool: "cursor",
    activePanels: { macd: true, stoch: true },
    klineDisplayMode: "day",
    engineMode: "legacy",
    cleanChartMode: false,
    chartLayout: "single",
    loading: false,
    loadingMessage: "loading",
    crosshair: { visible: false, absoluteIndex: null },
    ohlcData: [
      { date: "2026-04-01", close: 200, high: 205, low: 198, open: 199, volume: 1000 },
      { date: "2026-04-02", close: 204, high: 206, low: 201, open: 202, volume: 1200 },
      { date: "2026-04-03", close: 210, high: 212, low: 203, open: 204, volume: 1300 },
    ],
    activeInd: { ma20: true },
    indicatorSettings: {
      rsiPeriod: 14,
      aroonPeriod: 14,
      trixPeriod: 15,
      trixSignal: 9,
      williamsrPeriod: 14,
      mfiPeriod: 14,
      rocPeriod: 10,
      bbPeriod: 20,
      macdFast: 12,
      macdSlow: 26,
      macdSignal: 9,
      stochK: 14,
      stochD: 3,
      atrPeriod: 14,
      cciPeriod: 20,
      adxPeriod: 14,
      cmfPeriod: 20,
    },
    drawings: [],
    selectedDrawingId: null,
    workspacePresets: [{ id: 1, name: "Desk 1" }],
    activeWorkspacePresetId: 1,
    syncingCurrent: false,
    compareSeries: [],
    comparisonMode: "percent",
    institutionalOverlay: null,
    tickerEvents: [],
    macroSummary: null,
    isFullscreen: false,
  };
}

describe("ChartWorkspace", () => {
  beforeEach(() => {
    engineCalls.legacy = 0;
    engineCalls.lwc = 0;
    engineCalls.legacyDispose = 0;
    engineCalls.lwcDispose = 0;
  });

  it("reuses engine instances across repeated switches and disposes on unmount", async () => {
    const wrapper = mount(ChartWorkspace, { props: createProps() });
    await flushPromises();
    for (let index = 0; index < 20; index += 1) {
      await wrapper.setProps({ engineMode: index % 2 === 0 ? "lwc" : "legacy" });
      await flushPromises();
    }

    expect(engineCalls.legacy).toBe(1);
    expect(engineCalls.lwc).toBe(1);
    wrapper.unmount();
    expect(engineCalls.legacyDispose).toBeGreaterThan(0);
    expect(engineCalls.lwcDispose).toBeGreaterThan(0);
  });

  it("loads only the selected engine during initial render", async () => {
    const legacyWrapper = mount(ChartWorkspace, { props: createProps() });
    await flushPromises();
    expect(engineCalls.legacy).toBe(1);
    expect(engineCalls.lwc).toBe(0);
    legacyWrapper.unmount();

    engineCalls.legacy = 0;
    const lwcWrapper = mount(ChartWorkspace, {
      props: { ...createProps(), engineMode: "lwc" },
    });
    await flushPromises();
    expect(engineCalls.legacy).toBe(0);
    expect(engineCalls.lwc).toBe(1);
    lwcWrapper.unmount();
  });

  it("renders quote metadata chips", () => {
    const wrapper = mount(ChartWorkspace, { props: createProps() });

    expect(wrapper.text()).toContain("資料時間：");
    expect(wrapper.text()).toContain("來源：yahoo_finance");
    expect(wrapper.text()).toContain("延遲快照");
  });

  it("warns when quote data is stale", () => {
    const wrapper = mount(ChartWorkspace, { props: createProps() });

    expect(wrapper.text()).toContain("資料較舊");
  });

  it("uses backend market-session freshness instead of a fixed wall-clock cutoff", () => {
    const wrapper = mount(ChartWorkspace, {
      props: {
        ...createProps(),
        quote: {
          ...createProps().quote,
          freshness_status: "market_closed",
          is_stale: false,
          market_is_open: false,
        },
      },
    });

    expect(wrapper.text()).toContain("休市快照有效");
    expect(wrapper.text()).toContain("市場目前休市");
  });

  it("surfaces macro posture inside the chart workflow", () => {
    const wrapper = mount(ChartWorkspace, {
      props: {
        ...createProps(),
        macroSummary: {
          overall_risk: "medium",
          trade_posture: "selective",
          decision_hint: "環境偏震盪，只做最強標的，並縮小部位與嚴守停損。",
        },
      },
    });

    expect(wrapper.text()).toContain("中風險");
    expect(wrapper.text()).toContain("選擇性出手");
    expect(wrapper.text()).toContain("只做最強標的");
  });

  it("emits workspace save and load actions", async () => {
    const wrapper = mount(ChartWorkspace, { props: createProps() });

    await wrapper.find(".workspace-input").setValue("Momentum Desk");
    const buttons = wrapper.findAll(".workspace-toolbar .tool-btn");
    await buttons[0].trigger("click");

    await wrapper.find(".workspace-select").setValue("1");
    await buttons[1].trigger("click");

    expect(wrapper.emitted("save-workspace")[0]).toEqual(["Momentum Desk"]);
    expect(wrapper.emitted("load-workspace")[0]).toEqual([1]);
  });

  it("emits journal creation from the chart toolbar", async () => {
    const wrapper = mount(ChartWorkspace, { props: createProps() });
    const toolbarButtons = wrapper.findAll(".chart-toolbar .tool-btn");
    await toolbarButtons[toolbarButtons.length - 1].trigger("click");

    expect(wrapper.emitted("open-journal-entry")[0]).toEqual([
      { ticker: "AAPL", entry_price: 210.5 },
    ]);
  });

  it("emits engine mode changes from the chart toolbar", async () => {
    const wrapper = mount(ChartWorkspace, { props: createProps() });
    const engineButtons = wrapper.findAll(".chart-toolbar .tool-btn").filter((button) =>
      ["Legacy", "LWC Beta"].includes(button.text()),
    );

    await engineButtons[1].trigger("click");

    expect(wrapper.emitted("set-engine-mode")[0]).toEqual(["lwc"]);
  });

  it("emits timeframe changes from the chart toolbar", async () => {
    const wrapper = mount(ChartWorkspace, { props: createProps() });
    const timeframeButton = wrapper.findAll(".chart-toolbar .tool-btn").find((button) => button.text() === "1m");

    await timeframeButton.trigger("click");

    expect(wrapper.emitted("set-timeframe")[0]).toEqual([{ tf: "1d", iv: "1m", label: "1m" }]);
  });

  it("switches to a chart-first layout in fullscreen mode", () => {
    const wrapper = mount(ChartWorkspace, {
      props: {
        ...createProps(),
        isFullscreen: true,
      },
    });

    expect(wrapper.find(".center").classes()).toContain("is-chart-fullscreen");
    expect(wrapper.find(".chart-header").exists()).toBe(false);
    expect(wrapper.find(".chart-meta").exists()).toBe(false);
    expect(wrapper.find(".workspace-toolbar").exists()).toBe(false);
    expect(wrapper.find(".drawing-manager").exists()).toBe(false);
    expect(wrapper.find(".chart-toolbar").exists()).toBe(true);
    expect(wrapper.find(".indicator-deck").exists()).toBe(false);
    expect(wrapper.find(".volume-area").exists()).toBe(true);
    expect(wrapper.findAll(".ind-panel.visible").length).toBeGreaterThan(0);
  });

  it("opens the indicator deck and emits panel toggles", async () => {
    const wrapper = mount(ChartWorkspace, { props: createProps() });
    const deckToggle = wrapper.findAll(".chart-toolbar .tool-btn").find((button) => button.text() === "指標面板");

    await deckToggle.trigger("click");

    const macdToggle = wrapper.findAll(".indicator-chip").find((button) => button.text().startsWith("MACD"));
    await macdToggle.trigger("click");
    const kdToggle = wrapper.findAll(".indicator-chip").find((button) => button.text().startsWith("KD Stoch"));
    await kdToggle.trigger("click");

    expect(wrapper.find(".indicator-deck").exists()).toBe(true);
    expect(wrapper.emitted("toggle-panel")[0]).toEqual(["macd"]);
    expect(wrapper.emitted("toggle-panel")[1]).toEqual(["stoch"]);
  });

  it("renders event markers and links event rows to vertical lines", async () => {
    const wrapper = mount(ChartWorkspace, {
      props: {
        ...createProps(),
        tickerEvents: [
          { event_type: "earnings", title: "AAPL Earnings", event_date: "2026-04-02", importance: "high" },
        ],
      },
    });

    expect(wrapper.find(".chart-event-marker").exists()).toBe(true);
    await wrapper.find(".chart-event-marker").trigger("click");

    expect(wrapper.emitted("add-drawing")[0]).toEqual([
      { type: "vline", index: 1, label: "AAPL Earnings" },
    ]);
  });
});
