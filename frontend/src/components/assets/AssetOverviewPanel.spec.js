import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

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

import AssetOverviewPanel from "./AssetOverviewPanel.vue";

function buildProps() {
  return {
    assetPerformanceRange: "1y",
    assetBaseCurrency: "TWD",
    assetSummary: {
      total_asset_value_base: 180000,
      unrealized_total_base: 12000,
      realized_total_base: 6000,
    },
    assetWarnings: [],
    assetQuoteGaps: [],
    assetReconciliation: { items: [], summary: {} },
    assetPerformanceSummary: {
      start_value_base: 150000,
      true_performance_base: 18000,
      true_return_pct: 12,
      high_water_mark_base: 182000,
      max_drawdown_pct: -3.2,
      point_count: 3,
      realized_end_base: 6000,
    },
    assetPerformanceSeries: [
      {
        date: "2026-04-01",
        cash_total_base: 50000,
        market_value_total_base: 100000,
        total_asset_value_base: 150000,
        true_performance_base: 0,
        net_flow_base: 0,
        realized_total_base: 0,
        unrealized_total_base: 0,
        drawdown_pct: 0,
      },
      {
        date: "2026-04-02",
        cash_total_base: 52000,
        market_value_total_base: 110000,
        total_asset_value_base: 162000,
        true_performance_base: 7000,
        net_flow_base: 5000,
        realized_total_base: 2000,
        unrealized_total_base: 5000,
        drawdown_pct: -1,
      },
      {
        date: "2026-04-03",
        cash_total_base: 48000,
        market_value_total_base: 132000,
        total_asset_value_base: 180000,
        true_performance_base: 18000,
        net_flow_base: 12000,
        realized_total_base: 6000,
        unrealized_total_base: 12000,
        drawdown_pct: -3.2,
      },
    ],
    assetMonthlyHeatmap: [
      { month: "2026-03", true_performance_base: 5000, return_pct: 3.2 },
      { month: "2026-04", true_performance_base: 12000, return_pct: 6.8 },
    ],
    assetAlerts: [],
    assetAccountAllocation: [
      { key: "Broker A", value_base: 120000, weight_pct: 66.67 },
      { key: "Bank B", value_base: 60000, weight_pct: 33.33 },
    ],
    assetMarketAllocation: [
      { key: "US", value_base: 90000, weight_pct: 50 },
      { key: "TW", value_base: 90000, weight_pct: 50 },
    ],
    assetContributors: {
      top_gainers: [{ ticker: "AAPL", unrealized_pnl_base: 9000 }],
      top_losers: [{ ticker: "TSM", unrealized_pnl_base: -2000 }],
    },
    assetHoldings: [
      { account_id: 1, ticker: "AAPL", account_name: "Broker A", market_value_base: 90000, unrealized_pnl_base: 9000 },
    ],
    assetCashEntries: [
      { id: 11, account_name: "Bank B", flow_type: "deposit", flow_date: "2026-04-03T10:00:00Z", amount: 10000, currency: "TWD" },
    ],
    assetTradeEntries: [
      { id: 12, account_name: "Broker A", ticker: "AAPL", side: "buy", trade_date: "2026-04-02T09:00:00Z", quantity: 10, price: 180, market: "US" },
    ],
  };
}

describe("AssetOverviewPanel", () => {
  it("switches the main chart metric from summary cards", async () => {
    const wrapper = mount(AssetOverviewPanel, {
      props: buildProps(),
    });

    const charts = wrapper.findAllComponents({ name: "VChart" });
    expect(charts[0].props("option").series[0].name).toBe("總資產");

    const cashCard = wrapper.findAll(".asset-summary-action").find((item) => item.text().includes("現金總額"));
    await cashCard.trigger("click");

    expect(wrapper.findAllComponents({ name: "VChart" })[0].props("option").series[0].name).toBe("現金");
  });

  it("emits holdings drilldown from interactive charts", async () => {
    const wrapper = mount(AssetOverviewPanel, {
      props: buildProps(),
    });

    const charts = wrapper.findAllComponents({ name: "VChart" });

    charts[2].vm.$emit("click", { data: [3, 0, 6.8, "2026-04", 12000] });
    charts[3].vm.$emit("click", { data: { name: "Broker A" } });
    charts[5].vm.$emit("click", { data: { ticker: "AAPL" } });

    expect(wrapper.emitted("focus-holdings")).toEqual([
      [{ accountKey: "", marketKey: "", ticker: "", month: "2026-04" }],
      [{ accountKey: "Broker A", marketKey: "", ticker: "", month: "" }],
      [{ accountKey: "", marketKey: "", ticker: "AAPL", month: "" }],
    ]);
  });
});
