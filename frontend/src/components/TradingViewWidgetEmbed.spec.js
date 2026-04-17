import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import TradingViewWidgetEmbed from "./TradingViewWidgetEmbed.vue";

describe("TradingViewWidgetEmbed", () => {
  it("renders allowed TradingView embeds as direct sandboxed iframes", () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js",
        config: { colorTheme: "dark", locale: "zh_TW" },
      },
    });

    const frame = wrapper.find("iframe.tv-widget-frame");
    const frameUrl = new URL(frame.attributes("src"));
    const frameConfig = JSON.parse(decodeURIComponent(frameUrl.hash.slice(1)));

    expect(frame.exists()).toBe(true);
    expect(frame.attributes("sandbox")).toContain("allow-scripts");
    expect(frame.attributes("sandbox")).toContain("allow-same-origin");
    expect(frameUrl.origin).toBe("https://www.tradingview-widget.com");
    expect(frameUrl.pathname).toBe("/embed-widget/stock-heatmap/");
    expect(frameUrl.searchParams.get("locale")).toBe("zh_TW");
    expect(frameConfig.colorTheme).toBe("dark");
    expect(frameConfig.locale).toBeUndefined();
    expect(frameConfig.utm_campaign).toBe("stock-heatmap");
    expect(frame.attributes("srcdoc")).toBeUndefined();
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

  it("uses an embedded script iframe for screener widgets and seeds TradingView environment", () => {
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
    const srcdoc = frame.attributes("srcdoc");

    expect(frame.exists()).toBe(true);
    expect(frame.attributes("src")).toBeUndefined();
    expect(srcdoc).toContain('window.environment = "battle"');
    expect(srcdoc).toContain('window.locale = "zh_TW"');
    expect(srcdoc).toContain("embed-widget-screener.js");
    expect(srcdoc).toContain('"market": "taiwan"');
  });

  it("rebuilds the iframe url when the widget config changes", async () => {
    const wrapper = mount(TradingViewWidgetEmbed, {
      props: {
        scriptSrc: "https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js",
        config: { colorTheme: "dark" },
      },
    });

    const originalSrc = wrapper.find("iframe").attributes("src");
    expect(wrapper.findAll("iframe")).toHaveLength(1);

    await wrapper.setProps({ config: { colorTheme: "light" } });

    const updatedSrc = wrapper.find("iframe").attributes("src");
    const frameConfig = JSON.parse(decodeURIComponent(new URL(updatedSrc).hash.slice(1)));

    expect(wrapper.findAll("iframe")).toHaveLength(1);
    expect(updatedSrc).not.toBe(originalSrc);
    expect(frameConfig.colorTheme).toBe("light");
    expect(wrapper.find("script").exists()).toBe(false);
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
