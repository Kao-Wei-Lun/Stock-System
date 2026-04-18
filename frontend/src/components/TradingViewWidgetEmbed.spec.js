import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import TradingViewWidgetEmbed from "./TradingViewWidgetEmbed.vue";

describe("TradingViewWidgetEmbed", () => {
  it("renders allowed TradingView embeds via the official external-embedding script", () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js",
        config: { colorTheme: "dark", locale: "zh_TW" },
      },
    });

    const scriptHost = wrapper.find(".tv-widget-script-host");
    const script = scriptHost.find("script");

    expect(scriptHost.exists()).toBe(true);
    expect(script.attributes("src")).toBe("https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js");
    expect(script.text()).toContain('"colorTheme": "dark"');
    expect(script.text()).toContain('"locale": "zh_TW"');
    expect(script.text()).toContain('"utm_campaign": "stock-heatmap"');
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
    expect(wrapper.find(".tv-widget-script-host").exists()).toBe(false);
    expect(wrapper.find("iframe").exists()).toBe(false);
    expect(wrapper.text()).toContain("未在允許清單");
  });

  it("uses the local screener wrapper iframe for screener widgets", () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-screener.js",
        config: {
          colorTheme: "dark",
          locale: "zh_TW",
          market: "taiwan",
          defaultColumn: "overview",
          defaultScreen: "top_gainers",
        },
      },
    });

    const frame = wrapper.find("iframe.tv-widget-frame");
    const frameUrl = new URL(frame.attributes("src"), "http://localhost:5173");
    const frameConfig = JSON.parse(decodeURIComponent(frameUrl.hash.slice(1)));

    expect(frame.exists()).toBe(true);
    expect(frameUrl.pathname).toBe("/api/tradingview/widgets/screener");
    expect(frameUrl.searchParams.get("locale")).toBe("zh_TW");
    expect(frameConfig.market).toBe("taiwan");
    expect(frameConfig.utm_campaign).toBe("screener");
    expect(wrapper.find(".tv-widget-script-host").exists()).toBe(false);
  });

  it("rebuilds the embed script when the widget config changes", async () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js",
        config: { colorTheme: "dark" },
      },
    });

    const originalScript = wrapper.find(".tv-widget-script-host script");
    const originalText = originalScript.text();

    await wrapper.setProps({ config: { colorTheme: "light" } });

    const updatedScript = wrapper.find(".tv-widget-script-host script");
    expect(updatedScript.element).not.toBe(originalScript.element);
    expect(updatedScript.text()).not.toBe(originalText);
    expect(updatedScript.text()).toContain('"colorTheme": "light"');
    expect(updatedScript.text()).toContain('"utm_campaign": "market-overview"');
  });

  it("rebuilds the screener wrapper url when the widget config changes", async () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-screener.js",
        config: { colorTheme: "dark", locale: "zh_TW", market: "taiwan" },
      },
    });

    const originalFrame = wrapper.find("iframe.tv-widget-frame");
    const originalSrc = originalFrame.attributes("src");

    await wrapper.setProps({
      config: { colorTheme: "light", locale: "zh_TW", market: "america" },
    });

    const updatedFrame = wrapper.find("iframe.tv-widget-frame");
    const updatedUrl = new URL(updatedFrame.attributes("src"), "http://localhost:5173");
    const updatedConfig = JSON.parse(decodeURIComponent(updatedUrl.hash.slice(1)));

    expect(updatedFrame.attributes("src")).not.toBe(originalSrc);
    expect(updatedConfig.colorTheme).toBe("light");
    expect(updatedConfig.market).toBe("america");
  });

  it("keeps overview scrolling by disabling widget interaction until requested", async () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js",
        config: { colorTheme: "dark" },
      },
    });

    const host = wrapper.find(".tv-widget-script-host");
    expect(host.classes()).not.toContain("interactive");
    expect(wrapper.text()).toContain("頁面捲動優先");

    await wrapper.find(".tv-widget-overlay-btn").trigger("click");

    expect(host.classes()).toContain("interactive");
    expect(wrapper.find(".tv-widget-interaction-exit").exists()).toBe(true);

    await wrapper.find(".tv-widget-interaction-exit").trigger("click");

    expect(host.classes()).not.toContain("interactive");
  });
});
