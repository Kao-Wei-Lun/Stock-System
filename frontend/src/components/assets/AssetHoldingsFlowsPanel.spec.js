import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AssetHoldingsFlowsPanel from "./AssetHoldingsFlowsPanel.vue";

function buildProps() {
  return {
    assetBaseCurrency: "TWD",
    assetAccountsSummary: [
      { account_id: 1, account_name: "Broker A", account_type: "brokerage", base_currency: "USD", cash_total_base: 32000, include_in_total: true },
      { account_id: 2, account_name: "Bank B", account_type: "bank", base_currency: "TWD", cash_total_base: 18000, include_in_total: true },
    ],
    assetHoldings: [
      {
        account_id: 1,
        account_name: "Broker A",
        ticker: "AAPL",
        display_name: "Apple",
        market: "US",
        quantity: 10,
        avg_cost: 180,
        last_price: 190,
        market_value_base: 60000,
        unrealized_pnl_base: 4000,
        realized_pnl_base: 1000,
      },
      {
        account_id: 2,
        account_name: "Bank B",
        ticker: "0050.TW",
        display_name: "ETF",
        market: "TW",
        quantity: 20,
        avg_cost: 120,
        last_price: 130,
        market_value_base: 26000,
        unrealized_pnl_base: 2000,
        realized_pnl_base: 0,
      },
    ],
    assetCashEntries: [
      { id: 21, account_id: 1, flow_type: "deposit", flow_date: "2026-04-03T10:00:00Z", amount: 15000, currency: "USD" },
      { id: 22, account_id: 2, flow_type: "deposit", flow_date: "2026-03-01T10:00:00Z", amount: 8000, currency: "TWD" },
    ],
    assetTradeEntries: [
      { id: 31, account_id: 1, ticker: "AAPL", side: "buy", trade_date: "2026-04-02T09:00:00Z", quantity: 10, price: 180, market: "US" },
      { id: 32, account_id: 2, ticker: "0050.TW", side: "buy", trade_date: "2026-03-02T09:00:00Z", quantity: 20, price: 120, market: "TW" },
    ],
    assetFilter: {
      accountKey: "Broker A",
      marketKey: "US",
      ticker: "AAPL",
      month: "2026-04",
    },
  };
}

describe("AssetHoldingsFlowsPanel", () => {
  it("applies drilldown filters to holdings and flow lists", () => {
    const wrapper = mount(AssetHoldingsFlowsPanel, {
      props: buildProps(),
    });

    expect(wrapper.text()).toContain("帳戶：Broker A");
    expect(wrapper.text()).toContain("市場：US");
    expect(wrapper.text()).toContain("標的：AAPL");
    expect(wrapper.text()).toContain("月份：2026-04");
    expect(wrapper.text()).toContain("AAPL");
    expect(wrapper.text()).not.toContain("0050.TW");

    const rows = wrapper.findAll("tbody tr");
    expect(rows).toHaveLength(1);
    expect(rows[0].text()).toContain("AAPL");
  });

  it("lets the user clear drilldown filters", async () => {
    const wrapper = mount(AssetHoldingsFlowsPanel, {
      props: buildProps(),
    });

    await wrapper.findAll(".asset-holdings-head-actions .asset-inline-btn")[0].trigger("click");

    expect(wrapper.emitted("clear-filter")).toBeTruthy();
  });
});
