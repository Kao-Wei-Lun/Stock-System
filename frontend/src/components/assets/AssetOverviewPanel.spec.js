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

vi.mock("../DeferredVChart.vue", () => ({
  default: {
    name: "DeferredVChart",
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
    template: "<div class='deferred-v-chart-stub'></div>",
  },
}));

import AssetOverviewPanel from "./AssetOverviewPanel.vue";

function findCharts(wrapper) {
  return wrapper.findAllComponents({ name: "DeferredVChart" });
}

function buildProps() {
  return {
    assetPerformanceRange: "1y",
    assetBaseCurrency: "TWD",
    assetSummary: {
      total_asset_value_base: 180000,
      current_position_cost_base: 120000,
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
      flow_breakdown: {
        deposit_base: 12000,
        withdraw_base: 0,
        dividend_interest_base: 0,
        fee_tax_base: 0,
        transfer_in_base: 0,
        transfer_out_base: 0,
        other_flow_base: 0,
        net_flow_base: 12000,
      },
      performance_breakdown: {
        realized_change_base: 6000,
        unrealized_change_base: 12000,
        other_change_base: 0,
        total_change_base: 18000,
      },
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
        flow_breakdown: {
          deposit_base: 0,
          withdraw_base: 0,
          dividend_interest_base: 0,
          fee_tax_base: 0,
          transfer_in_base: 0,
          transfer_out_base: 0,
          other_flow_base: 0,
          net_flow_base: 0,
        },
        performance_breakdown: {
          realized_change_base: 0,
          unrealized_change_base: 0,
          other_change_base: 0,
          total_change_base: 0,
        },
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
        flow_breakdown: {
          deposit_base: 5000,
          withdraw_base: 0,
          dividend_interest_base: 0,
          fee_tax_base: 0,
          transfer_in_base: 0,
          transfer_out_base: 0,
          other_flow_base: 0,
          net_flow_base: 5000,
        },
        performance_breakdown: {
          realized_change_base: 2000,
          unrealized_change_base: 5000,
          other_change_base: 0,
          total_change_base: 7000,
        },
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
        flow_breakdown: {
          deposit_base: 12000,
          withdraw_base: 0,
          dividend_interest_base: 0,
          fee_tax_base: 0,
          transfer_in_base: 0,
          transfer_out_base: 0,
          other_flow_base: 0,
          net_flow_base: 12000,
        },
        performance_breakdown: {
          realized_change_base: 6000,
          unrealized_change_base: 12000,
          other_change_base: 0,
          total_change_base: 18000,
        },
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
    assetCurrencyAllocation: [
      { key: "TWD", currency: "TWD", value_base: 120000, weight_pct: 66.67 },
      { key: "USD", currency: "USD", value_base: 60000, weight_pct: 33.33 },
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
  it("renders the KPI grid and the main performance chart", () => {
    const wrapper = mount(AssetOverviewPanel, {
      props: buildProps(),
    });

    expect(wrapper.text()).toContain("總資產");
    expect(wrapper.text()).toContain("近一日淨值變化");
    expect(wrapper.text()).toContain("最大回撤");

    const charts = findCharts(wrapper);
    expect(charts[0].props("option").series[0].name).toBe("總資產");
  });

  it("emits holdings drilldown from interactive charts", async () => {
    const wrapper = mount(AssetOverviewPanel, {
      props: buildProps(),
    });

    const charts = findCharts(wrapper);

    expect(charts[2].props("option").series[0].data).toHaveLength(12);

    charts[2].vm.$emit("click", { data: { month: "2026-04", hasData: true } });
    charts[3].vm.$emit("click", { data: { name: "Broker A" } });
    charts[4].vm.$emit("click", { data: { ticker: "AAPL" } });

    expect(wrapper.emitted("focus-holdings")).toEqual([
      [{ accountKey: "", marketKey: "", ticker: "", month: "2026-04" }],
      [{ accountKey: "Broker A", marketKey: "", ticker: "", month: "" }],
      [{ accountKey: "", marketKey: "", ticker: "AAPL", month: "" }],
    ]);
  });

  it("keeps heatmap month labels and tooltips away from the legend area", () => {
    const wrapper = mount(AssetOverviewPanel, {
      props: buildProps(),
    });

    const heatmapOption = findCharts(wrapper)[2].props("option");

    expect(heatmapOption.grid.bottom).toBe(82);
    expect(heatmapOption.visualMap.bottom).toBe(16);
    expect(heatmapOption.xAxis.axisLabel.margin).toBe(16);
    expect(heatmapOption.tooltip.confine).toBe(true);
    expect(typeof heatmapOption.tooltip.position).toBe("function");
    expect(heatmapOption.visualMap.itemWidth).toBeUndefined();
    expect(heatmapOption.visualMap.itemHeight).toBeUndefined();
  });

  it("shows a story-first breakdown and keeps the waterfall view available", async () => {
    const wrapper = mount(AssetOverviewPanel, {
      props: buildProps(),
    });

    const story = wrapper.get('[data-testid="asset-change-story"]');
    const waterfallShell = wrapper.get(".asset-chart-shell-waterfall");

    expect(story.isVisible()).toBe(true);
    expect(story.text()).toContain("主要是投資報酬在推高資產");
    expect(story.text()).toContain("資金流拆解");
    expect(story.text()).toContain("已實現損益");
    expect(waterfallShell.attributes("style")).toContain("display: none");

    await wrapper.get('[data-testid="asset-change-view-waterfall"]').trigger("click");

    expect(waterfallShell.attributes("style") || "").not.toContain("display: none");
  });

  it("drops a meaningless zero start step from the waterfall chart", () => {
    const props = buildProps();
    props.assetPerformanceSummary.start_value_base = 0;

    const wrapper = mount(AssetOverviewPanel, {
      props,
    });

    const charts = findCharts(wrapper);
    expect(charts[1].props("option").xAxis.data).toEqual(["淨流入", "真實績效", "期末"]);
  });

  it("prefers API daily NAV change when it is available", () => {
    const props = buildProps();
    props.assetPerformanceSummary.daily_nav_change_base = 2500;
    props.assetPerformanceSummary.daily_nav_change_pct = 1.5;
    props.assetPerformanceSummary.daily_metric_note = "API daily note";

    const wrapper = mount(AssetOverviewPanel, {
      props,
    });

    const card = wrapper.get('[data-testid="asset-kpi-recent-change"]');
    expect(card.text()).toContain("+TWD 2,500");
    expect(card.text()).not.toContain("+TWD 18,000");
    expect(card.attributes("title")).toBe("API daily note");
  });

  it("keeps the existing daily NAV fallback when API value is missing", () => {
    const wrapper = mount(AssetOverviewPanel, {
      props: buildProps(),
    });

    expect(wrapper.get('[data-testid="asset-kpi-recent-change"]').text()).toContain("+TWD 18,000");
  });

  it("shows current position cost without treating zero as empty", () => {
    const zeroProps = buildProps();
    zeroProps.assetSummary.current_position_cost_base = 0;
    const zeroWrapper = mount(AssetOverviewPanel, {
      props: zeroProps,
    });

    expect(zeroWrapper.get('[data-testid="asset-performance-summary-current-position-cost"]').text()).toContain("TWD 0");

    const nullProps = buildProps();
    nullProps.assetSummary.current_position_cost_base = null;
    const nullWrapper = mount(AssetOverviewPanel, {
      props: nullProps,
    });

    expect(nullWrapper.get('[data-testid="asset-performance-summary-current-position-cost"]').text()).toContain("--");
  });

  it("enables currency allocation while keeping sector allocation disabled", async () => {
    const wrapper = mount(AssetOverviewPanel, {
      props: buildProps(),
    });

    const sectorTab = wrapper.get('[data-testid="asset-allocation-tab-sector"]');
    const currencyTab = wrapper.get('[data-testid="asset-allocation-tab-currency"]');

    expect(sectorTab.attributes("disabled")).toBeDefined();
    expect(currencyTab.attributes("disabled")).toBeUndefined();

    await currencyTab.trigger("click");

    expect(wrapper.text()).toContain("TWD");
    expect(wrapper.text()).toContain("USD");
  });

  it("shows an empty state when currency allocation is empty", async () => {
    const props = buildProps();
    props.assetCurrencyAllocation = [];
    const wrapper = mount(AssetOverviewPanel, {
      props,
    });

    await wrapper.get('[data-testid="asset-allocation-tab-currency"]').trigger("click");

    expect(wrapper.get('[data-testid="asset-allocation-empty"]').text()).toContain("幣別配置");
  });
});
