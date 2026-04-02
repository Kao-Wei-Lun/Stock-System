import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import WatchlistPanel from "./WatchlistPanel.vue";

function buildPanelProps(overrides = {}) {
  const freshTimestamp = new Date().toISOString();
  return {
    groups: [
      {
        id: 1,
        name: "Core",
        items: [
          {
            id: 10,
            group_id: 1,
            ticker: "AAPL",
            name: "Apple",
            category: "US",
            close: 210.5,
            change_pct: 2.68,
            source: "yahoo_finance",
            is_delayed: true,
            quote_timestamp: freshTimestamp,
            synced_at: freshTimestamp,
          },
        ],
      },
    ],
    marketItems: [],
    items: [],
    leftTab: "watch",
    activeGroupId: 1,
    activeTicker: "AAPL",
    loading: false,
    error: false,
    ...overrides,
  };
}

describe("WatchlistPanel", () => {
  it("renders quote source and freshness metadata", () => {
    const wrapper = mount(WatchlistPanel, {
      props: buildPanelProps(),
    });

    expect(wrapper.text()).toContain("Yahoo Finance");
    expect(wrapper.text()).toContain("延遲快照");
    expect(wrapper.text()).not.toContain("無時間戳");
  });

  it("marks items without timestamps as stale", () => {
    const wrapper = mount(WatchlistPanel, {
      props: buildPanelProps({
        groups: [
          {
            id: 1,
            name: "Core",
            items: [
              {
                id: 10,
                group_id: 1,
                ticker: "CACHE",
                name: "Cache Only",
                close: 99,
                change_pct: 0,
                source: "local_cache",
                is_delayed: true,
                quote_timestamp: null,
                synced_at: null,
                date: null,
              },
            ],
          },
        ],
      }),
    });

    expect(wrapper.text()).toContain("Local cache");
    expect(wrapper.text()).toContain("資料較舊");
    expect(wrapper.text()).toContain("無時間戳");
  });
});
