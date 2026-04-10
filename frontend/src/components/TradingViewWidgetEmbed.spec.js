import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { describe, expect, it } from "vitest";

import TradingViewWidgetEmbed from "./TradingViewWidgetEmbed.vue";

describe("TradingViewWidgetEmbed", () => {
  it("renders allowed TradingView embed scripts once on mount", async () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js",
        config: { colorTheme: "dark" },
      },
    });

    await nextTick();

    expect(wrapper.find("script").attributes("src")).toBe(
      "https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js",
    );
    expect(wrapper.findAll("script")).toHaveLength(1);
    expect(wrapper.find(".tv-widget-warning").exists()).toBe(false);
  });

  it("blocks unexpected script sources", () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://example.com/embed-widget-stock-heatmap.js",
        config: { colorTheme: "dark" },
      },
    });

    expect(wrapper.find("script").exists()).toBe(false);
    expect(wrapper.text()).toContain("未在允許清單");
  });

  it("re-renders only when the widget config changes", async () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js",
        config: { colorTheme: "dark" },
      },
    });

    await nextTick();
    expect(wrapper.findAll("script")).toHaveLength(1);

    await wrapper.setProps({ config: { colorTheme: "light" } });
    await nextTick();

    expect(wrapper.findAll("script")).toHaveLength(1);
    expect(wrapper.find("script").element.text).toContain('"colorTheme":"light"');
  });
});
