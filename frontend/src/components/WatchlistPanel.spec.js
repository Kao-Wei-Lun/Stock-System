import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import WatchlistPanel from "./WatchlistPanel.vue";

function buildWatchItem(timestamp, overrides = {}) {
  return {
    id: 10,
    group_id: 1,
    ticker: "AAPL",
    name: "Apple",
    category: "US",
    close: 210.5,
    change_pct: 2.68,
    source: "yahoo_finance",
    is_delayed: true,
    quote_timestamp: timestamp,
    synced_at: timestamp,
    tags: ["優先候選", "Q4", "市場:選擇性出手"],
    ...overrides,
  };
}

function buildPanelProps(overrides = {}) {
  const freshTimestamp = new Date().toISOString();
  return {
    groups: [
      {
        id: 1,
        name: "Core",
        items: [buildWatchItem(freshTimestamp)],
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
    expect(wrapper.text()).toContain("優先候選");
    expect(wrapper.text()).toContain("Q4");
    expect(wrapper.text()).not.toContain("無時間戳");
  });

  it("marks items without timestamps as stale", async () => {
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
    expect(wrapper.text()).toContain("資料已過期");
    expect(wrapper.text()).toContain("無時間戳");
    expect(wrapper.get('[data-testid="watch-alert-CACHE"]').attributes("disabled")).toBeDefined();

    await wrapper.get('[data-testid="watch-alert-CACHE"]').trigger("click");
    expect(wrapper.emitted("open-alert-modal")).toBeUndefined();
  });

  it("filters and sorts watchlist items by stored screener tags", async () => {
    const freshTimestamp = new Date().toISOString();
    const wrapper = mount(WatchlistPanel, {
      props: buildPanelProps({
        groups: [
          {
            id: 1,
            name: "Core",
            items: [
              buildWatchItem(freshTimestamp, {
                id: 10,
                ticker: "AAPL",
                name: "Apple",
                change_pct: 2.68,
                tags: ["優先候選", "Q4", "市場:選擇性出手"],
              }),
              buildWatchItem(freshTimestamp, {
                id: 11,
                ticker: "NVDA",
                name: "NVIDIA",
                change_pct: 1.82,
                tags: ["觀察名單", "Q3", "市場:選擇性出手"],
              }),
              buildWatchItem(freshTimestamp, {
                id: 12,
                ticker: "MSFT",
                name: "Microsoft",
                change_pct: -0.54,
                tags: ["等待名單", "Q2", "市場:防守控倉"],
              }),
            ],
          },
        ],
      }),
    });

    expect(wrapper.findAll(".wl-op")).toHaveLength(9);
    expect(wrapper.get('[data-testid="watchlist-summary"]').text()).toContain("優先 1");
    expect(wrapper.get('[data-testid="watchlist-summary"]').text()).toContain("觀察 1");
    expect(wrapper.get('[data-testid="watchlist-summary"]').text()).toContain("等待 1");

    await wrapper.get('[data-testid="watch-verdict-filter"]').setValue("priority");

    expect(wrapper.findAll(".wl-item").map((node) => node.attributes("data-ticker"))).toEqual(["AAPL"]);
    expect(wrapper.get('[data-testid="watchlist-summary"]').text()).toContain("顯示 1 / 3 檔");
    expect(wrapper.findAll(".wl-op")).toHaveLength(0);

    await wrapper.get('[data-testid="reset-watch-view"]').trigger("click");
    await wrapper.get('[data-testid="watch-sort-mode"]').setValue("setup_desc");

    expect(wrapper.findAll(".wl-item").map((node) => node.attributes("data-ticker"))).toEqual([
      "AAPL",
      "NVDA",
      "MSFT",
    ]);
  });

  it("emits a journal draft payload from the watchlist item", async () => {
    const wrapper = mount(WatchlistPanel, {
      props: buildPanelProps(),
    });

    await wrapper.get('[data-testid="watch-journal-AAPL"]').trigger("click");

    expect(wrapper.emitted("open-journal-entry")[0]).toEqual([
      {
        ticker: "AAPL",
        name: "Apple",
        entry_price: 210.5,
        entry_reason: "觀察池跟蹤：優先候選 / Q4 / 市場:選擇性出手",
        review_notes: "觀察池快照：優先候選 | Q4 | 市場:選擇性出手 | 來源:觀察池 | 資料源:Yahoo Finance | 狀態:延遲快照",
        tags: ["優先候選", "Q4", "市場:選擇性出手", "來源:觀察池"],
      },
    ]);
  });

  it("emits an alert shortcut payload from the watchlist item", async () => {
    const wrapper = mount(WatchlistPanel, {
      props: buildPanelProps(),
    });

    await wrapper.get('[data-testid="watch-alert-AAPL"]').trigger("click");

    const [payload] = wrapper.emitted("open-alert-modal")[0];

    expect(payload.ticker).toBe("AAPL");
    expect(payload.type).toBe("price");
    expect(payload.condition).toBe("大於");
    expect(payload.value).toBe(210.5);
    expect(payload.context_tags).toEqual(["優先候選", "Q4", "市場:選擇性出手"]);
    expect(payload.context_source).toBe("watchlist");
    expect(payload.snapshot_price).toBe(210.5);
    expect(payload.snapshot_source).toBe("yahoo_finance");
    expect(typeof payload.snapshot_timestamp).toBe("string");
    expect(payload.prefill_hint).toContain("觀察池快捷警報：以 210.50 為基準");
    expect(payload.prefill_hint).toContain("資料源 Yahoo Finance");
  });
  it("emits batch alert payloads for the visible watch group", async () => {
    const freshTimestamp = new Date().toISOString();
    const wrapper = mount(WatchlistPanel, {
      props: buildPanelProps({
        groups: [
          {
            id: 1,
            name: "Journal Flow",
            items: [
              buildWatchItem(freshTimestamp, {
                id: 10,
                ticker: "AAPL",
                close: 210.5,
                change_pct: 2.68,
                tags: ["優先候選", "Q4"],
              }),
              buildWatchItem(freshTimestamp, {
                id: 11,
                ticker: "MSFT",
                close: 410.2,
                change_pct: -1.2,
                tags: ["觀察名單", "Q3"],
              }),
            ],
          },
        ],
      }),
    });

    await wrapper.get('[data-testid="watch-batch-alerts"]').trigger("click");

    const [payloads] = wrapper.emitted("create-alerts-batch")[0];
    expect(payloads).toHaveLength(2);
    expect(payloads[0]).toMatchObject({
      ticker: "AAPL",
      type: "price",
      condition: "大於",
      value: 210.5,
      context_source: "watchlist_group",
      snapshot_price: 210.5,
      snapshot_source: "yahoo_finance",
    });
    expect(payloads[0].context_tags).toContain("觀察群組:Journal Flow");
    expect(payloads[1]).toMatchObject({
      ticker: "MSFT",
      type: "price",
      condition: "小於",
      value: 410.2,
      context_source: "watchlist_group",
      snapshot_price: 410.2,
    });
    expect(payloads[1].prefill_hint).toContain("Journal Flow");
    expect(payloads[1].prefill_hint).toContain("2 檔");
  });

  it("emits group color payloads when creating and renaming groups", async () => {
    const wrapper = mount(WatchlistPanel, {
      props: buildPanelProps(),
    });

    await wrapper.findAll(".group-pill")[1].trigger("click");
    await wrapper.find('input[placeholder="新增觀察群組"]').setValue("Momentum");
    await wrapper.findAll(".group-swatch")[2].trigger("click");
    const createForm = wrapper.findAll(".watchlist-form")[0];
    await createForm.findAll("button").at(-1).trigger("click");

    expect(wrapper.emitted("create-group")[0]).toEqual([
      { name: "Momentum", color: "#ffd166" },
    ]);

    await wrapper.find(".secondary").trigger("click");
    await wrapper.find('input[placeholder="重新命名群組"]').setValue("Core Plus");
    const renameForm = wrapper.findAll(".watchlist-form")[0];
    await renameForm.findAll(".group-swatch")[4].trigger("click");
    await renameForm.findAll("button").find((button) => button.text() === "儲存").trigger("click");

    expect(wrapper.emitted("rename-group")[0]).toEqual([
      1,
      { name: "Core Plus", color: "#9b6dff" },
    ]);
  });
});
