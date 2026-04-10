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

    expect(wrapper.find(".search-command-badge").text()).toBe("⌘K");
    await wrapper.find(".search-command-badge").trigger("click");

    expect(wrapper.emitted("open-command-palette")).toHaveLength(1);
  });

  it("adds workspace shortcut hints to navigation titles", () => {
    const wrapper = mount(AppNavbar, { props: createProps() });

    const titles = wrapper.findAll(".workspace-nav-btn").map((button) => button.attributes("title"));
    expect(titles).toContain("總覽 · Alt+1");
    expect(titles).toContain("終端 · Alt+2");
    expect(titles).toContain("設定 · Alt+5");
  });
});
