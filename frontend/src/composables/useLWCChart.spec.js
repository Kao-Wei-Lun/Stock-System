import { defineComponent, nextTick, reactive, ref } from "vue";
import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const lwcMocks = vi.hoisted(() => {
  const seriesInstances = [];
  const timeScaleApi = {
    subscribeVisibleLogicalRangeChange: vi.fn(),
    unsubscribeVisibleLogicalRangeChange: vi.fn(),
    applyOptions: vi.fn(),
    setVisibleLogicalRange: vi.fn(),
    getVisibleLogicalRange: vi.fn(() => null),
    scrollToRealTime: vi.fn(),
  };

  const chartApi = {
    addSeries: vi.fn(() => {
      const priceScaleApi = {
        applyOptions: vi.fn(),
        setAutoScale: vi.fn(),
        getVisibleRange: vi.fn(() => null),
        setVisibleRange: vi.fn(),
      };
      const instance = {
        setData: vi.fn(),
        update: vi.fn(),
        applyOptions: vi.fn(),
        priceScaleApi,
        priceScale: vi.fn(() => priceScaleApi),
        createPriceLine: vi.fn(() => ({})),
      };
      seriesInstances.push(instance);
      return instance;
    }),
    removeSeries: vi.fn(),
    timeScale: vi.fn(() => timeScaleApi),
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
    resize: vi.fn(),
    panes: vi.fn(() => []),
    remove: vi.fn(),
  };

  return {
    chartApi,
    timeScaleApi,
    seriesInstances,
    createChart: vi.fn(() => chartApi),
  };
});

vi.mock("lightweight-charts", () => ({
  AreaSeries: "AreaSeries",
  CandlestickSeries: "CandlestickSeries",
  HistogramSeries: "HistogramSeries",
  LineSeries: "LineSeries",
  PriceScaleMode: {
    Logarithmic: 1,
    Normal: 0,
  },
  createChart: lwcMocks.createChart,
}));

vi.mock("./useLWCIndicators", () => ({
  buildLWCIndicatorModel: vi.fn(() => ({
    overlays: [],
    panels: [],
  })),
}));

vi.mock("./useLWCDrawings", () => ({
  useLWCDrawings: () => ({
    scheduleRender: vi.fn(),
    cleanupOverlay: vi.fn(),
  }),
}));

import { useLWCChart } from "./useLWCChart";
import { buildLWCIndicatorModel } from "./useLWCIndicators";

describe("useLWCChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    lwcMocks.seriesInstances.length = 0;
    vi.mocked(buildLWCIndicatorModel).mockImplementation(() => ({
      overlays: [],
      panels: [],
    }));
  });

  it("maps candles mode to candle series data when initializing LWC", async () => {
    const emit = vi.fn();
    const props = reactive({
      ohlcData: [
        { date: "2026-04-01", open: 10, high: 12, low: 9, close: 11, volume: 1000 },
        { date: "2026-04-02", open: 11, high: 13, low: 10, close: 12, volume: 1200 },
      ],
      activeInd: {},
      activePanels: {},
      indicatorSettings: {},
      cleanChartMode: false,
      currentInterval: "1d",
      currentTicker: "AAPL",
      isFullscreen: false,
    });

    const wrapper = mount(defineComponent({
      setup() {
        const container = ref(null);
        useLWCChart({
          chartContainer: container,
          props,
          emit,
        });
        return { container };
      },
      template: "<div ref='container' style='width: 640px; height: 420px;'></div>",
    }));

    await nextTick();
    await nextTick();

    expect(lwcMocks.createChart).toHaveBeenCalled();
    expect(lwcMocks.createChart.mock.calls[0][1]).toMatchObject({
      width: expect.any(Number),
      height: expect.any(Number),
      rightPriceScale: {
        scaleMargins: {
          top: 0.035,
          bottom: 0.06,
        },
      },
    });
    expect(lwcMocks.createChart.mock.calls[0][1]).not.toHaveProperty("autoSize");
    expect(lwcMocks.seriesInstances[0].setData).toHaveBeenCalled();
    expect(lwcMocks.seriesInstances[0].priceScaleApi.applyOptions).toHaveBeenCalledWith({
      autoScale: true,
      mode: 0,
      scaleMargins: {
        top: 0.035,
        bottom: 0.06,
      },
    });

    const firstPayload = lwcMocks.seriesInstances[0].setData.mock.calls[0][0];
    expect(firstPayload[0]).toMatchObject({
      open: 10,
      high: 12,
      low: 9,
      close: 11,
    });
    expect(firstPayload[0].time).toEqual({
      year: 2026,
      month: 4,
      day: 1,
    });

    wrapper.unmount();
  });

  it("updates only the last point for current and appended realtime bars", async () => {
    const first = { date: "2026-04-01", open: 10, high: 12, low: 9, close: 11, volume: 1000 };
    const second = { date: "2026-04-02", open: 11, high: 13, low: 10, close: 12, volume: 1200 };
    const props = reactive({
      ohlcData: [first, second],
      activeInd: {},
      activePanels: {},
      indicatorSettings: {},
      cleanChartMode: false,
      currentInterval: "1d",
      currentTicker: "AAPL",
      isFullscreen: false,
    });
    const wrapper = mount(defineComponent({
      setup() {
        const container = ref(null);
        useLWCChart({ chartContainer: container, props, emit: vi.fn() });
        return { container };
      },
      template: "<div ref='container' style='width: 640px; height: 420px;'></div>",
    }));
    await nextTick();
    await nextTick();

    const mainSeries = lwcMocks.seriesInstances[0];
    const initialSetDataCalls = mainSeries.setData.mock.calls.length;
    const updatedSecond = { ...second, high: 14, close: 13 };
    props.ohlcData = [first, updatedSecond];
    await nextTick();

    expect(mainSeries.update).toHaveBeenLastCalledWith(expect.objectContaining({ high: 14, close: 13 }));
    expect(mainSeries.setData).toHaveBeenCalledTimes(initialSetDataCalls);

    const third = { date: "2026-04-03", open: 13, high: 15, low: 12, close: 14, volume: 1300 };
    props.ohlcData = [first, updatedSecond, third];
    await nextTick();

    expect(mainSeries.update).toHaveBeenLastCalledWith(expect.objectContaining({ high: 15, close: 14 }));
    expect(mainSeries.setData).toHaveBeenCalledTimes(initialSetDataCalls);
    wrapper.unmount();
  });

  it("updates indicator tails without recreating panes on a realtime bar", async () => {
    vi.mocked(buildLWCIndicatorModel).mockImplementation(({ rows }) => ({
      overlays: [{
        key: "test-ma",
        type: "line",
        options: {},
        data: rows.map((row) => ({ time: row.time, value: row.close })),
      }],
      panels: [],
    }));
    const first = { date: "2026-04-01", open: 10, high: 12, low: 9, close: 11, volume: 1000 };
    const second = { date: "2026-04-02", open: 11, high: 13, low: 10, close: 12, volume: 1200 };
    const props = reactive({
      ohlcData: [first, second],
      activeInd: { ma20: true },
      activePanels: {},
      indicatorSettings: {},
      cleanChartMode: false,
      currentInterval: "1d",
      currentTicker: "AAPL",
      isFullscreen: false,
    });
    const wrapper = mount(defineComponent({
      setup() {
        const container = ref(null);
        useLWCChart({ chartContainer: container, props, emit: vi.fn() });
        return { container };
      },
      template: "<div ref='container' style='width: 640px; height: 420px;'></div>",
    }));
    await nextTick();
    await nextTick();

    const indicatorSeries = lwcMocks.seriesInstances[2];
    const createdSeriesCount = lwcMocks.chartApi.addSeries.mock.calls.length;
    props.ohlcData = [first, { ...second, close: 13 }];
    await nextTick();

    expect(indicatorSeries.update).toHaveBeenCalledWith(expect.objectContaining({ value: 13 }));
    expect(lwcMocks.chartApi.addSeries).toHaveBeenCalledTimes(createdSeriesCount);
    wrapper.unmount();
  });

  it("keeps auto scale until explicit Y controls lock it and exposes clipping recovery", async () => {
    const first = { date: "2026-04-01", open: 10, high: 12, low: 9, close: 11, volume: 1000 };
    const second = { date: "2026-04-02", open: 11, high: 13, low: 10, close: 12, volume: 1200 };
    const props = reactive({
      ohlcData: [first, second],
      activeInd: {},
      activePanels: {},
      indicatorSettings: {},
      cleanChartMode: false,
      currentInterval: "1d",
      currentTicker: "AAPL",
      isFullscreen: false,
    });
    let controller;
    const wrapper = mount(defineComponent({
      setup() {
        const container = ref(null);
        controller = useLWCChart({ chartContainer: container, props, emit: vi.fn() });
        return { container };
      },
      template: "<div ref='container' style='width: 640px; height: 420px;'></div>",
    }));
    await nextTick();
    await nextTick();

    expect(lwcMocks.createChart.mock.calls[0][1].handleScale.axisPressedMouseMove.price).toBe(false);
    expect(controller.yScaleLabel.value).toContain("Y 軸 自動");
    expect(controller.canResetYScale.value).toBe(false);

    controller.zoomYIn();
    expect(controller.yScaleLabel.value).toContain("手動鎖定");
    expect(controller.canResetYScale.value).toBe(true);
    expect(lwcMocks.seriesInstances[0].priceScaleApi.setAutoScale).toHaveBeenLastCalledWith(false);

    props.ohlcData = [first, { ...second, high: 30, close: 29 }];
    await nextTick();
    expect(controller.yScaleClipped.value).toBe(true);

    controller.resetYScale();
    expect(controller.yScaleLabel.value).toContain("Y 軸 自動");
    expect(controller.yScaleClipped.value).toBe(false);
    expect(lwcMocks.seriesInstances[0].priceScaleApi.setAutoScale).toHaveBeenLastCalledWith(true);
    wrapper.unmount();
  });
});
