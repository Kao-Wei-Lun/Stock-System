import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import TradingViewWidgetEmbed from "./TradingViewWidgetEmbed.vue";

describe("TradingViewWidgetEmbed", () => {
  it("renders allowed TradingView embeds inside a sandboxed iframe", () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js",
        config: { colorTheme: "dark" },
      },
    });

    const frame = wrapper.find("iframe.tv-widget-frame");
    const srcdoc = frame.attributes("srcdoc");

    expect(frame.exists()).toBe(true);
    expect(frame.attributes("sandbox")).toContain("allow-scripts");
    expect(srcdoc).toContain(
      'src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js"',
    );
    expect(srcdoc).toContain('"colorTheme":"dark"');
    expect(srcdoc).toContain("tradingview-widget-container__widget");
    expect(wrapper.find("script").exists()).toBe(false);
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
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(wrapper.text()).toContain("未在允許清單");
  });

  it("rebuilds the iframe document when the widget config changes", async () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js",
        config: { colorTheme: "dark" },
      },
    });

    const originalSrcdoc = wrapper.find("iframe").attributes("srcdoc");
    expect(wrapper.findAll("iframe")).toHaveLength(1);

    await wrapper.setProps({ config: { colorTheme: "light" } });

    const updatedSrcdoc = wrapper.find("iframe").attributes("srcdoc");
    expect(wrapper.findAll("iframe")).toHaveLength(1);
    expect(updatedSrcdoc).not.toBe(originalSrcdoc);
    expect(updatedSrcdoc).toContain('"colorTheme":"light"');
    expect(wrapper.find("script").exists()).toBe(false);
  });
});
