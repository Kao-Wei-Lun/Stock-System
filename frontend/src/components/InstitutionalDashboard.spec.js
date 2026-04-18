import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import InstitutionalDashboard from "./InstitutionalDashboard.vue";

describe("InstitutionalDashboard", () => {
  it("defaults to the stock chip view for Taiwan stock tickers and can switch tabs", async () => {
    const wrapper = mount(InstitutionalDashboard, {
      props: {
        loading: false,
        selectedDate: "2026-04-18",
        currentTicker: "2330.TW",
        currentName: "台積電",
        taiwanChipRangeDays: 20,
      },
      global: {
        stubs: {
          StockChipWorkspace: { template: "<div data-testid='stock-view'></div>" },
          MarketInstitutionalDashboard: { template: "<div data-testid='market-view'></div>" },
        },
      },
    });

    expect(wrapper.find("[data-testid='stock-view']").exists()).toBe(true);

    const marketButton = wrapper.findAll("button").find((button) => button.text().includes("TAIFEX"));
    await marketButton.trigger("click");

    expect(wrapper.find("[data-testid='market-view']").exists()).toBe(true);
  });

  it("defaults to the market view for unsupported tickers", () => {
    const wrapper = mount(InstitutionalDashboard, {
      props: {
        loading: false,
        selectedDate: "2026-04-18",
        currentTicker: "AAPL",
        currentName: "Apple",
        taiwanChipRangeDays: 20,
      },
      global: {
        stubs: {
          StockChipWorkspace: { template: "<div data-testid='stock-view'></div>" },
          MarketInstitutionalDashboard: { template: "<div data-testid='market-view'></div>" },
        },
      },
    });

    expect(wrapper.find("[data-testid='market-view']").exists()).toBe(true);
  });
});
