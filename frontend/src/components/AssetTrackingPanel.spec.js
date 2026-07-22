import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

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
    assetImportBatches: [],
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
      source_name: "",
      csv_text: "",
      dry_run: true,
    },
    assetCashImportForm: {
      default_account_id: 1,
      source_name: "",
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

  it("shows only the selected maintenance tool while preserving stable section ids", () => {
    const wrapper = mount(AssetTrackingPanel, {
      props: { ...buildProps(), maintenanceSection: "trades" },
    });

    expect(wrapper.get('[data-asset-section="trades"]').isVisible()).toBe(true);
    expect(wrapper.get('[data-asset-section="accounts"]').isVisible()).toBe(false);
    expect(wrapper.get('[data-asset-section="cash"]').isVisible()).toBe(false);
    expect(wrapper.findAll('[data-asset-section="imports"]').every((item) => !item.isVisible())).toBe(true);
  });

  it("requires an error-free CSV preview before formal import", async () => {
    const wrapper = mount(AssetTrackingPanel, {
      props: {
        ...buildProps(),
        maintenanceSection: "imports",
        assetTradeImportResult: {
          dry_run: true,
          summary: { input_count: 3, importable_count: 1, duplicate_count: 1, error_count: 1 },
          duplicates: [{ import_row: 3, import_status: "duplicate_in_file", duplicate_of_row: 2 }],
          errors: [{ row: 4, message: "數量必須大於 0" }],
        },
      },
    });

    expect(wrapper.get('[data-testid="asset-trade-import-submit"]').attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("可匯入 1 / 3 筆");
    expect(wrapper.text()).toContain("第 3 列：與第 2 列重複");
    expect(wrapper.text()).toContain("第 4 列：數量必須大於 0");

    await wrapper.setProps({
      assetTradeImportResult: {
        dry_run: true,
        summary: { input_count: 2, importable_count: 1, duplicate_count: 1, error_count: 0 },
        duplicates: [{ import_row: 3, import_status: "duplicate_in_database", existing_id: 9 }],
        errors: [],
      },
    });

    expect(wrapper.get('[data-testid="asset-trade-import-submit"]').attributes("disabled")).toBeUndefined();
    expect(wrapper.text()).toContain("資料庫已存在 #9");
  });

  it("shows auditable import batches and confirms rollback", async () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const wrapper = mount(AssetTrackingPanel, {
      props: {
        ...buildProps(),
        maintenanceSection: "imports",
        assetImportBatches: [
          {
            id: 12,
            import_type: "trade_csv",
            source_name: "broker.csv",
            status: "committed",
            created_count: 3,
            skipped_count: 1,
            error_count: 0,
            created_at: "2026-07-22T09:00:00+08:00",
          },
        ],
      },
    });

    expect(wrapper.text()).toContain("broker.csv");
    expect(wrapper.text()).toContain("新增 3 · 略過 1 · 錯誤 0");
    await wrapper.get('[data-testid="rollback-import-batch-12"]').trigger("click");

    expect(confirm).toHaveBeenCalledOnce();
    expect(wrapper.emitted("rollback-asset-import-batch")).toEqual([[12]]);
  });
});
