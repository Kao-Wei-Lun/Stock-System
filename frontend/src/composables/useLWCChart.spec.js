import { defineComponent, nextTick, reactive, ref } from "vue";
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

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

describe("useLWCChart", () => {
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
});
