import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AssetWorkspace from "./AssetWorkspace.vue";

function buildProps() {
  return {
    currentTicker: "AAPL",
    assetLoading: false,
    assetPerformanceRange: "1y",
    assetBaseCurrency: "TWD",
    assetSummary: {},
    assetAccounts: [],
    assetAccountsSummary: [],
    assetHoldings: [],
    assetWarnings: [],
    assetQuoteGaps: [],
    assetReconciliation: { items: [], summary: {} },
    assetPriceOverrides: [],
    assetFxRates: [],
    assetAdjustments: [],
    assetPerformanceSummary: {},
    assetPerformanceSeries: [],
    assetMonthlyHeatmap: [],
    assetRealizedVsUnrealized: [],
    assetAlerts: [],
    assetTradeImportResult: null,
    assetCashImportResult: null,
    assetJournalImportPreview: null,
    assetLastRecompute: null,
    assetAccountAllocation: [],
    assetMarketAllocation: [],
    assetContributors: { top_gainers: [], top_losers: [] },
    assetCashEntries: [],
    assetTradeEntries: [],
    assetReconciliationEntries: [],
    assetAccountForm: {
      id: null,
      name: "",
      institution: "",
      account_type: "brokerage",
      base_currency: "TWD",
      include_in_total: true,
      sort_order: 0,
      notes: "",
    },
    assetCashForm: {
      id: null,
      account_id: "",
      flow_date: "",
      flow_type: "deposit",
      amount: "",
      currency: "TWD",
      fx_rate_to_base: 1,
      counterparty: "",
      note: "",
    },
    assetTradeForm: {
      id: null,
      account_id: "",
      trade_date: "",
      ticker: "",
      display_name: "",
      market: "US",
      asset_type: "stock",
      currency: "USD",
      side: "buy",
      quantity: "",
      price: "",
      fee_amount: 0,
      tax_amount: 0,
      fx_rate_to_base: 1,
      source: "manual",
      note: "",
    },
    assetReconciliationForm: {
      account_id: "",
      snapshot_date: "",
      cash_actual: "",
      market_value_actual: "",
      note: "",
    },
    assetPriceOverrideForm: {
      id: null,
      account_id: "",
      ticker: "",
      override_date: "",
      price: "",
      currency: "TWD",
      note: "",
    },
    assetFxRateForm: {
      id: null,
      rate_date: "",
      source_currency: "USD",
      target_currency: "TWD",
      rate: "",
      provider: "",
      note: "",
    },
    assetAdjustmentForm: {
      id: null,
      account_id: "",
      ticker: "",
      event_type: "manual",
      event_date: "",
      quantity_delta: "",
      cost_basis_delta: "",
      split_ratio: "",
      target_ticker: "",
      note: "",
    },
    assetTradeImportForm: {
      account_id: "",
      csv_text: "",
      has_header: true,
      date_format: "auto",
      source: "manual_csv",
    },
    assetCashImportForm: {
      account_id: "",
      csv_text: "",
      has_header: true,
      date_format: "auto",
      source: "manual_csv",
    },
    assetJournalImportForm: {
      account_id: "",
      include_open_positions: false,
      source: "journal",
    },
  };
}

function mountWorkspace() {
  return mount(AssetWorkspace, {
    props: buildProps(),
    global: {
      stubs: {
        AssetOverviewPanel: {
          name: "AssetOverviewPanel",
          template: `
            <div class="overview-panel-stub">
              <button data-testid="overview-to-holdings" @click="$emit('open-tab', 'holdings')">
                to holdings
              </button>
              <button data-testid="overview-focus-holdings" @click="$emit('focus-holdings', { ticker: 'AAPL' })">
                focus holdings
              </button>
              <button data-testid="overview-focus-maintenance" @click="$emit('focus-maintenance', 'reconciliation')">
                focus maintenance
              </button>
            </div>
          `,
        },
        AssetHoldingsFlowsPanel: {
          name: "AssetHoldingsFlowsPanel",
          template: `
            <div class="holdings-panel-stub">
              <button data-testid="holdings-to-maintenance" @click="$emit('open-tab', 'maintenance')">
                to maintenance
              </button>
            </div>
          `,
        },
        AssetTrackingPanel: {
          name: "AssetTrackingPanel",
          props: ["panelMode"],
          template: "<div class='maintenance-panel-stub'>{{ panelMode }}</div>",
        },
      },
    },
  });
}

describe("AssetWorkspace", () => {
  it("defaults to overview and switches tabs from the workspace nav", async () => {
    const wrapper = mountWorkspace();

    expect(wrapper.find(".overview-panel-stub").exists()).toBe(true);
    expect(wrapper.find(".asset-tab.active").text()).toContain("總覽");

    await wrapper.findAll(".asset-tab")[1].trigger("click");

    expect(wrapper.find(".holdings-panel-stub").exists()).toBe(true);
    expect(wrapper.find(".asset-tab.active").text()).toContain("持倉");

    await wrapper.findAll(".asset-tab")[2].trigger("click");

    expect(wrapper.find(".maintenance-panel-stub").text()).toBe("maintenance");
    expect(wrapper.find(".asset-tab.active").text()).toContain("資料維護");
  });

  it("responds to child panel navigation shortcuts", async () => {
    const wrapper = mountWorkspace();

    await wrapper.get('[data-testid="overview-to-holdings"]').trigger("click");
    expect(wrapper.find(".holdings-panel-stub").exists()).toBe(true);

    await wrapper.get('[data-testid="holdings-to-maintenance"]').trigger("click");
    expect(wrapper.find(".maintenance-panel-stub").exists()).toBe(true);
  });

  it("routes overview drilldowns into holdings and maintenance tabs", async () => {
    const wrapper = mountWorkspace();

    await wrapper.get('[data-testid="overview-focus-holdings"]').trigger("click");
    expect(wrapper.find(".holdings-panel-stub").exists()).toBe(true);

    await wrapper.findAll(".asset-tab")[0].trigger("click");
    await wrapper.get('[data-testid="overview-focus-maintenance"]').trigger("click");
    expect(wrapper.find(".maintenance-panel-stub").exists()).toBe(true);
  });
});
