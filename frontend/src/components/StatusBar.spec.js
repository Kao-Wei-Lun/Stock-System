import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import StatusBar from "./StatusBar.vue";

describe("StatusBar", () => {
  it("shows stale quote warnings when timestamps are old", () => {
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

    expect(wrapper.text()).toContain("資料較舊");
  });

  it("shows missing timestamp warnings when no quote time is available", () => {
    const wrapper = mount(StatusBar, {
      props: {
        connected: false,
        backendUrl: "http://127.0.0.1:8001",
        latency: "—",
        quoteSource: "local_cache",
        quoteMode: "延遲快照",
        quoteTimestamp: null,
        quoteSyncedAt: null,
        quoteDelayed: true,
        lastUpdate: "—",
        clockTime: "2026/04/02 10:00:00",
      },
    });

    expect(wrapper.text()).toContain("無時間戳");
  });
});
