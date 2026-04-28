import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AppNavbar from "./AppNavbar.vue";

function createProps(overrides = {}) {
  return {
    workspacePage: "terminal",
    reviewTab: "journal",
    searchQuery: "",
    searchResults: [],
    searchOpen: false,
    timeframeOptions: [
      { tf: "1d", iv: "1m", label: "1m" },
      { tf: "1y", iv: "1d", label: "1Y" },
    ],
    currentPeriod: "1d",
    currentInterval: "1m",
    marketStatus: {
      nyseOpen: false,
      nasdaqOpen: false,
      tseOpen: true,
    },
    wsConnected: true,
    ...overrides,
  };
}

describe("AppNavbar", () => {
  it("exposes the command palette shortcut from search", async () => {
    const wrapper = mount(AppNavbar, { props: createProps() });

    expect(wrapper.find(".search-command-badge").exists()).toBe(true);
    await wrapper.find(".search-command-badge").trigger("click");

    expect(wrapper.emitted("open-command-palette")).toHaveLength(1);
  });

  it("adds workspace shortcut hints to navigation titles", () => {
    const wrapper = mount(AppNavbar, { props: createProps() });

    const titles = wrapper.findAll(".workspace-nav-btn").map((button) => button.attributes("title"));
    titles.forEach((title, index) => {
      expect(title).toContain(`Alt+${index + 1}`);
    });
  });

  it("shows a live quote badge when realtime data is active", () => {
    const wrapper = mount(AppNavbar, {
      props: createProps({
        activeQuote: {
          is_delayed: false,
          quote_type: "realtime",
        },
      }),
    });

    expect(wrapper.find(".quote-badge").classes()).toContain("live");
    expect(wrapper.text()).toContain("即時");
  });

  it("shows the fubon connection badge when a realtime account is connected", () => {
    const wrapper = mount(AppNavbar, {
      props: createProps({
        fubonStatus: "connected",
      }),
    });

    expect(wrapper.find(".fubon-badge").classes()).toContain("connected");
    expect(wrapper.text()).toContain("富邦即時");
  });

  it("shows futopt search result tags in the navbar dropdown", () => {
    const wrapper = mount(AppNavbar, {
      props: createProps({
        searchOpen: true,
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
