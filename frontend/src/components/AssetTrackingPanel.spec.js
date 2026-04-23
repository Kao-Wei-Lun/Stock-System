import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AssetTrackingPanel from "./AssetTrackingPanel.vue";

function buildProps() {
  return {
    currentTicker: "AAPL",
    assetLoading: false,
    panelMode: "maintenance",
    assetPerformanceRange: "1y",
    assetBaseCurrency: "TWD",
    assetSummary: {},
    assetAccounts: [
      { id: 1, name: "Main Broker", base_currency: "TWD", auto_sync_trade_settlement: true, settlement_account_id: 2 },
      { id: 2, name: "Settlement Bank", base_currency: "TWD", auto_sync_trade_settlement: false, settlement_account_id: null },
    ],
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
      settlement_account_id: "",
      auto_sync_trade_settlement: false,
      include_in_total: true,
      sort_order: 0,
      notes: "",
    },
    assetCashForm: {
      id: null,
      account_id: 1,
      flow_date: "2026-04-22T09:00",
      flow_type: "deposit",
      amount: "",
      currency: "TWD",
      fx_rate_to_base: 1,
      is_initial_balance: false,
      counterparty: "",
      note: "",
    },
    assetTradeForm: {
      id: null,
      account_id: 1,
      trade_date: "2026-04-22T09:00",
      ticker: "AAPL",
      display_name: "Apple",
      market: "US",
      asset_type: "stock",
      currency: "USD",
      side: "buy",
      quantity: "",
      price: "",
      fee_amount: 0,
      tax_amount: 0,
      fx_rate_to_base: 32,
      is_initial_balance: false,
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
      effective_at: "",
      price: "",
      currency: "TWD",
      fx_rate_to_base: "",
      force_override: false,
      note: "",
    },
    assetFxRateForm: {
      id: null,
      snapshot_date: "",
      from_currency: "USD",
      to_currency: "TWD",
      rate: "",
      source: "manual",
      note: "",
    },
    assetAdjustmentForm: {
      id: null,
      account_id: "",
      event_date: "",
      ticker: "",
      event_type: "adjustment",
      quantity_delta: "",
      cost_basis_delta: "",
      cash_delta: "",
      currency: "TWD",
      split_ratio: "",
      target_ticker: "",
      target_display_name: "",
      target_market: "US",
      target_asset_type: "stock",
      note: "",
    },
    assetTradeImportForm: {
      default_account_id: 1,
      csv_text: "",
      dry_run: true,
    },
    assetCashImportForm: {
      default_account_id: 1,
      csv_text: "",
      dry_run: true,
    },
    assetJournalImportForm: {
      account_id: 1,
      ticker: "",
      market: "",
      strategy_code: "",
      tag: "",
      search: "",
      limit: 20,
    },
  };
}

describe("AssetTrackingPanel", () => {
  it("emits account settlement sync updates", async () => {
    const wrapper = mount(AssetTrackingPanel, { props: buildProps() });

    await wrapper.get('[data-testid="asset-account-settlement-account"]').setValue("2");
    await wrapper.get('[data-testid="asset-account-auto-sync-trade-settlement"]').setValue(true);

    expect(wrapper.emitted("update-asset-account-field")).toEqual([
      [{ key: "settlement_account_id", value: "2" }],
      [{ key: "auto_sync_trade_settlement", value: true }],
    ]);
  });

  it("emits cash initial balance updates", async () => {
    const wrapper = mount(AssetTrackingPanel, { props: buildProps() });

    await wrapper.get('[data-testid="asset-cash-initial-balance"]').setValue(true);

    expect(wrapper.emitted("update-asset-cash-field")).toEqual([
      [{ key: "is_initial_balance", value: true }],
    ]);
  });

  it("emits trade initial balance updates", async () => {
    const wrapper = mount(AssetTrackingPanel, { props: buildProps() });

    await wrapper.get('[data-testid="asset-trade-initial-balance"]').setValue(true);

    expect(wrapper.emitted("update-asset-trade-field")).toEqual([
      [{ key: "is_initial_balance", value: true }],
    ]);
  });
});
