import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import TradingViewWidgetEmbed from "./TradingViewWidgetEmbed.vue";

describe("TradingViewWidgetEmbed", () => {
  it("renders allowed TradingView embeds via the official widget iframe page", () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js",
        config: { colorTheme: "dark", locale: "zh_TW" },
      },
    });

    const frame = wrapper.find("iframe.tv-widget-frame");
    const frameUrl = new URL(frame.attributes("src"), "http://localhost:5173");
    const frameConfig = JSON.parse(decodeURIComponent(frameUrl.hash.slice(1)));

    expect(frame.exists()).toBe(true);
    expect(frameUrl.origin).toBe("https://www.tradingview-widget.com");
    expect(frameUrl.pathname).toBe("/embed-widget/stock-heatmap/");
    expect(frameUrl.searchParams.get("locale")).toBe("zh_TW");
    expect(frameConfig.colorTheme).toBe("dark");
    expect(frameConfig.utm_campaign).toBe("stock-heatmap");
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
  });

  it("rebuilds the official widget iframe url when the config changes", async () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js",
        config: { colorTheme: "dark" },
      },
    });

    const originalFrame = wrapper.find("iframe.tv-widget-frame");
    const originalSrc = originalFrame.attributes("src");

    await wrapper.setProps({ config: { colorTheme: "light" } });

    const updatedFrame = wrapper.find("iframe.tv-widget-frame");
    const updatedUrl = new URL(updatedFrame.attributes("src"), "http://localhost:5173");
    const updatedConfig = JSON.parse(decodeURIComponent(updatedUrl.hash.slice(1)));

    expect(updatedFrame.attributes("src")).not.toBe(originalSrc);
    expect(updatedUrl.origin).toBe("https://www.tradingview-widget.com");
    expect(updatedUrl.pathname).toBe("/embed-widget/market-overview/");
    expect(updatedConfig.colorTheme).toBe("light");
    expect(updatedConfig.utm_campaign).toBe("market-overview");
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

    const frame = wrapper.find("iframe.tv-widget-frame");
    expect(frame.classes()).not.toContain("interactive");
    expect(wrapper.text()).toContain("頁面捲動優先");

    await wrapper.find(".tv-widget-overlay-btn").trigger("click");

    expect(frame.classes()).toContain("interactive");
    expect(wrapper.find(".tv-widget-interaction-exit").exists()).toBe(true);

    await wrapper.find(".tv-widget-interaction-exit").trigger("click");

    expect(frame.classes()).not.toContain("interactive");
  });
});
