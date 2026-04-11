import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import StatusBar from "./StatusBar.vue";

describe("StatusBar", () => {
  it("marks stale quote timestamps with the stale badge state", () => {
    const wrapper = mount(StatusBar, {
      props: {
        connected: true,
        backendUrl: "http://127.0.0.1:8001",
        latency: "15ms",
        quoteSource: "yahoo_finance",
        quoteMode: "延遲快照",
        quoteTimestamp: "2020-03-29T04:00:00+00:00",
        quoteSyncedAt: "2020-03-29T04:00:05+00:00",
        quoteDelayed: true,
        lastUpdate: "2020/03/29 12:00:00",
        clockTime: "2026/04/02 10:00:00",
      },
    });

    expect(wrapper.find(".status-badge.stale").exists()).toBe(true);
    expect(wrapper.text()).toContain("資料較舊");
  });

  it("marks missing quote timestamps with the missing badge state", () => {
    const wrapper = mount(StatusBar, {
      props: {
        connected: false,
        backendUrl: "http://127.0.0.1:8001",
        latency: "-",
        quoteSource: "local_cache",
        quoteMode: "延遲快照",
        quoteTimestamp: null,
        quoteSyncedAt: null,
        quoteDelayed: true,
        lastUpdate: "-",
        clockTime: "2026/04/02 10:00:00",
      },
    });

    expect(wrapper.find(".status-badge.missing").exists()).toBe(true);
    expect(wrapper.text()).toContain("無時間戳");
  });

  it("shows live quote labels for fresh realtime payloads", () => {
    const timestamp = new Date(Date.now() - 4 * 60 * 1000).toISOString();
    const wrapper = mount(StatusBar, {
      props: {
        connected: true,
        backendUrl: "http://127.0.0.1:8001",
        latency: "15ms",
        quoteSource: "fubon_neo",
        quoteMode: "最新快照",
        quoteTimestamp: timestamp,
        quoteSyncedAt: timestamp,
        quoteDelayed: false,
        lastUpdate: "2026/04/02 10:00:00",
        clockTime: "2026/04/02 10:00:00",
      },
    });

    expect(wrapper.find(".status-badge.live").exists()).toBe(true);
    expect(wrapper.text()).toContain("即時資料");
    expect(wrapper.text()).toContain("4");
  });
});
