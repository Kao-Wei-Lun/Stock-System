import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TaiwanHeatmap from "./TaiwanHeatmap.vue";

vi.mock("vue-echarts", () => ({
  THEME_KEY: Symbol("THEME_KEY"),
  default: {
    name: "VChart",
    props: {
      option: {
        type: Object,
        required: true,
      },
      autoresize: {
        type: Boolean,
        default: false,
      },
    },
    template: "<div class='v-chart-stub'></div>",
  },
}));

function jsonResponse(payload, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  });
}

describe("TaiwanHeatmap", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a TradingView-style stock heatmap palette and tooltip", async () => {
    globalThis.fetch
      .mockImplementationOnce(() =>
        jsonResponse({
          data: [
            {
              ticker: "2330",
              name: "台積電",
              sector: "半導體",
              trade_value: 1200000000,
              change_pct: 4.12,
              price: 812,
            },
          ],
        }),
      )
      .mockImplementationOnce(() =>
        jsonResponse({
          data: [
            {
              ticker: "8299",
              name: "群聯",
              sector: "半導體",
              trade_value: 410000000,
              change_pct: -2.34,
              price: 580,
            },
            {
              ticker: "0050",
              name: "元大台灣50",
              sector: "未分類",
              trade_value: 50000000,
              change_pct: 1.5,
              price: 182.4,
            },
          ],
        }),
      );

    const wrapper = mount(TaiwanHeatmap, {
      props: {
        mode: "stocks",
      },
    });

    await flushPromises();

    const chart = wrapper.findComponent({ name: "VChart" });
    const option = chart.props("option");
    const [sectorNode] = option.series[0].data;

    expect(option.series[0].data).toHaveLength(1);
    expect(sectorNode.name).toBe("半導體");
    expect(sectorNode.children.map((item) => item.itemStyle.color)).toEqual(["#f23645", "#22ab94"]);
    expect(option.series[0].levels[1].upperLabel.fontSize).toBe(12);
    expect(option.series[0].levels[1].itemStyle.gapWidth).toBe(2);

    const tooltipHtml = option.tooltip.formatter({ data: sectorNode.children[0] });
    expect(tooltipHtml).toContain("台積電");
    expect(tooltipHtml).toContain("成交值");
    expect(tooltipHtml).toContain("#f23645");
    expect(wrapper.find(".heatmap-loading").exists()).toBe(false);
  });

  it("uses manual sector drill-down and emits ticker selection from leaf nodes", async () => {
    globalThis.fetch
      .mockImplementationOnce(() =>
        jsonResponse({
          data: [
            {
              ticker: "2330",
              name: "台積電",
              sector: "半導體",
              trade_value: 1200000000,
              change_pct: 4.12,
              price: 812,
            },
          ],
        }),
      )
      .mockImplementationOnce(() =>
        jsonResponse({
          data: [
            {
              ticker: "0050",
              name: "元大台灣50",
              sector: "未分類",
              trade_value: 900000000,
              change_pct: 0.52,
              price: 182.4,
            },
          ],
        }),
      );

    const wrapper = mount(TaiwanHeatmap, {
      props: {
        mode: "indices",
      },
    });

    await flushPromises();

    const chart = wrapper.findComponent({ name: "VChart" });
    const option = chart.props("option");
    const [indexSector] = option.series[0].data;

    expect(option.series[0].roam).toBe(true);
    expect(option.series[0].nodeClick).toBe(false);
    expect(option.series[0].breadcrumb.show).toBe(false);
    expect(option.series[0].levels[1].upperLabel.formatter({ name: "大盤指數與 ETF" })).toBe("大盤指數與 ETF");
    expect(indexSector.name).toBe("大盤指數與 ETF");
    expect(indexSector.children).toHaveLength(1);

    chart.vm.$emit("click", {
      data: indexSector,
      name: "大盤指數與 ETF",
      treePathInfo: [{}, {}],
    });
    await flushPromises();

    expect(wrapper.find(".heatmap-back-btn").exists()).toBe(true);

    chart.vm.$emit("click", { data: indexSector.children[0] });
    await flushPromises();

    expect(wrapper.emitted("select-ticker")[0]).toEqual([
      {
        ticker: "0050",
        name: "元大台灣50",
      },
    ]);
  });
});
