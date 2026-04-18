import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import StockChipWorkspace from "./StockChipWorkspace.vue";

describe("StockChipWorkspace", () => {
  it("emits range and refresh actions for supported tickers", async () => {
    const wrapper = mount(StockChipWorkspace, {
      props: {
        currentTicker: "2330.TW",
        currentName: "台積電",
        stockSupported: true,
        rangeDays: 20,
        chipHistory: {
          resolved_range: { from: "2026-04-01", to: "2026-04-18" },
          series: [
            { snapshot_date: "2026-04-17", institutional_net_buy_sell: 1000 },
            { snapshot_date: "2026-04-18", institutional_net_buy_sell: 2000 },
          ],
          stats: { institutional_20d_sum: 3000 },
        },
      },
      global: {
        stubs: {
          StockChipOverview: { template: "<div data-testid='overview-stub'></div>" },
          StockChipTrendChart: { template: "<div data-testid='trend-stub'></div>" },
          StockChipStatsStrip: { template: "<div data-testid='stats-stub'></div>" },
          StockChipTurningPoints: { template: "<div data-testid='turning-stub'></div>" },
        },
      },
    });

    const rangeButton = wrapper.findAll("button").find((button) => button.text().includes("60 日"));
    const refreshButton = wrapper.findAll("button").find((button) => button.text().includes("重新整理"));

    await rangeButton.trigger("click");
    await refreshButton.trigger("click");

    expect(wrapper.emitted("set-range-days")?.[0]).toEqual([60]);
    expect(wrapper.emitted("refresh")).toHaveLength(1);
  });

  it("offers a shortcut back to market view when ticker is unsupported", async () => {
    const wrapper = mount(StockChipWorkspace, {
      props: {
        currentTicker: "AAPL",
        currentName: "Apple",
        stockSupported: false,
        rangeDays: 20,
      },
      global: {
        stubs: {
          StockChipOverview: true,
          StockChipTrendChart: true,
          StockChipStatsStrip: true,
          StockChipTurningPoints: true,
        },
      },
    });

    expect(wrapper.text()).toContain("目前標的不支援個股籌碼歷史");

    await wrapper.get(".chip-empty-card .tool-btn").trigger("click");

    expect(wrapper.emitted("switch-market")).toHaveLength(1);
  });
});
