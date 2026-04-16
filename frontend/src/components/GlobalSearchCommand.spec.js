import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import GlobalSearchCommand from "./GlobalSearchCommand.vue";

function createProps(overrides = {}) {
  return {
    open: true,
    query: "",
    searchResults: [],
    recentTickers: [
      { ticker: "AAPL", name: "Apple", viewedAt: "2026-04-08T01:00:00Z" },
    ],
    currentTicker: "NVDA",
    ...overrides,
  };
}

describe("GlobalSearchCommand", () => {
  it("renders workspace actions and recent tickers when query is empty", () => {
    const wrapper = mount(GlobalSearchCommand, {
      props: createProps(),
    });

    expect(wrapper.text()).toContain("Open Terminal");
    expect(wrapper.text()).toContain("Market Overview");
    expect(wrapper.text()).toContain("AAPL");
    expect(wrapper.text()).toContain("Recent");
  });

  it("emits symbol selection from search results", async () => {
    const wrapper = mount(GlobalSearchCommand, {
      props: createProps({
        query: "AAPL",
        searchResults: [
          { ticker: "AAPL", name: "Apple Inc." },
        ],
      }),
    });

    await wrapper.findAll(".command-item")[4].trigger("click");

    expect(wrapper.emitted("select-symbol")[0]).toEqual([
      { ticker: "AAPL", name: "Apple Inc." },
    ]);
  });

  it("emits workspace navigation from command entries", async () => {
    const wrapper = mount(GlobalSearchCommand, {
      props: createProps(),
    });

    await wrapper.findAll(".command-item")[1].trigger("click");

    expect(wrapper.emitted("navigate")[0]).toEqual(["overview"]);
  });

  it("shows futopt result tags for option contracts", () => {
    const wrapper = mount(GlobalSearchCommand, {
      props: createProps({
        query: "TXO",
        searchResults: [
          {
            ticker: "TXO20000E4",
            name: "臺指選擇權20000買權04",
            asset_class: "futopt",
            instrument_type: "option",
            exchange: "TAIFEX",
          },
        ],
      }),
    });

    expect(wrapper.text()).toContain("選擇權");
    expect(wrapper.text()).toContain("TAIFEX");
  });
});
