import { computed, ref } from "vue";
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import ChartWorkspace from "./ChartWorkspace.vue";

vi.mock("../composables/useChartEngine", () => ({
  useChartEngine: () => ({
    chartMode: ref("candles"),
    priceScaleMode: ref("linear"),
    visibleData: ref([]),
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
    onMouseDown: vi.fn(),
    onMouseMove: vi.fn(),
    onMouseLeave: vi.fn(),
    onMouseUp: vi.fn(),
    onWheel: vi.fn(),
    onChartClick: vi.fn(),
    onDoubleClick: vi.fn(),
  }),
}));

function createProps() {
  return {
    currentTicker: "AAPL",
    currentName: "Apple",
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
      quote_timestamp: "2026-03-29T04:00:00+00:00",
      synced_at: "2026-03-29T04:00:05+00:00",
    },
    activeTool: "cursor",
    activePanels: { macd: true, stoch: true },
    klineDisplayMode: "day",
    cleanChartMode: false,
    chartLayout: "single",
    loading: false,
    loadingMessage: "loading",
    crosshair: { visible: false, absoluteIndex: null },
    ohlcData: [],
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
    isFullscreen: false,
  };
}

describe("ChartWorkspace", () => {
  it("renders quote metadata chips", () => {
    const wrapper = mount(ChartWorkspace, { props: createProps() });

    expect(wrapper.text()).toContain("資料時間：");
    expect(wrapper.text()).toContain("來源：yahoo_finance");
    expect(wrapper.text()).toContain("延遲快照");
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
});
