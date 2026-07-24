import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import NotificationPanel from "./NotificationPanel.vue";
import { NOTIFICATION_LAYOUT_STORAGE_KEY } from "../utils/floatingPanelLayout";

async function openPanel(wrapper) {
  await wrapper.get('[data-testid="notif-center-toggle"]').trigger("click");
}

describe("NotificationPanel", () => {
  beforeEach(() => {
    window.localStorage.removeItem(NOTIFICATION_LAYOUT_STORAGE_KEY);
  });

  afterEach(() => {
    window.localStorage.removeItem(NOTIFICATION_LAYOUT_STORAGE_KEY);
  });

  it("filters notifications and emits read toggles", async () => {
    const wrapper = mount(NotificationPanel, {
      props: {
        notifications: [
          {
            id: "remote-1",
            icon: "!",
            title: "AAPL alert",
            msg: "AAPL price breakout",
            time: "2026/04/02 09:30",
            createdAt: "2026-04-02T09:30:00+08:00",
            read: false,
            persisted: true,
            category: "alert",
            source: "yahoo_finance",
            ticker: "AAPL",
            contextTags: ["優先候選", "Q4"],
            macroSummary: {
              overall_risk: "medium",
              trade_posture: "selective",
              decision_hint: "環境偏震盪，只做最強標的。",
            },
          },
          {
            id: "remote-2",
            icon: "i",
            title: "Bootstrap",
            msg: "System ready",
            time: "2026/04/02 09:00",
            createdAt: "2026-04-02T09:00:00+08:00",
            read: true,
            persisted: true,
            category: "system",
            source: "local_db",
            ticker: null,
          },
        ],
      },
    });

    await openPanel(wrapper);

    expect(wrapper.text()).toContain("AAPL alert");
    expect(wrapper.text()).toContain("Bootstrap");

    await wrapper.findAll(".notif-filter-btn")[1].trigger("click");
    expect(wrapper.text()).toContain("AAPL alert");
    expect(wrapper.text()).not.toContain("Bootstrap");

    await wrapper.find(".notif-search").setValue("Q4");
    expect(wrapper.text()).toContain("AAPL alert");

    await wrapper.find(".notif-search").setValue("selective");
    expect(wrapper.text()).toContain("AAPL alert");

    await wrapper.find(".notif-search").setValue("breakout");
    await wrapper.findAll(".notif-action-btn").find((node) => node.text() === "標記已讀").trigger("click");

    expect(wrapper.emitted("toggle-read")[0]).toEqual([{ id: "remote-1", read: true }]);
  });

  it("opens tickers and dismisses session notifications", async () => {
    const wrapper = mount(NotificationPanel, {
      props: {
        notifications: [
          {
            id: "remote-1",
            icon: "!",
            title: "AAPL alert",
            msg: "AAPL price breakout",
            time: "2026/04/02 09:30",
            createdAt: "2026-04-02T09:30:00+08:00",
            read: false,
            persisted: true,
            category: "alert",
            source: "yahoo_finance",
            ticker: "AAPL",
            contextSource: "watchlist",
            contextTags: ["優先候選", "Q4"],
            thresholdValue: 210,
            triggerValue: 212,
            macroSummary: {
              overall_risk: "medium",
              trade_posture: "selective",
              decision_hint: "環境偏震盪，只做最強標的。",
            },
          },
          {
            id: "local-1",
            icon: "i",
            title: "Saved",
            msg: "Workspace stored",
            time: "2026/04/02 09:31",
            createdAt: "2026-04-02T09:31:00+08:00",
            read: false,
            persisted: false,
            category: "session",
            source: "session",
            ticker: null,
          },
        ],
      },
    });

    await openPanel(wrapper);

    await wrapper.findAll(".notif-chip").find((node) => node.text() === "本次操作").trigger("click");
    expect(wrapper.text()).toContain("Saved");
    expect(wrapper.text()).not.toContain("AAPL alert");

    await wrapper.find(".notif-search").setValue("");
    await wrapper.findAll(".notif-chip").find((node) => node.text() === "全部類別").trigger("click");
    await wrapper.findAll(".notif-action-btn").find((node) => node.text() === "開啟 AAPL").trigger("click");
    await wrapper.findAll(".notif-action-btn").find((node) => node.text() === "寫入日誌").trigger("click");
    await wrapper.findAll(".notif-action-btn").find((node) => node.text() === "存成模板").trigger("click");
    await wrapper.findAll(".notif-action-btn").find((node) => node.text() === "關閉").trigger("click");

    expect(wrapper.emitted("open-ticker")[0]).toEqual(["AAPL"]);
    expect(wrapper.emitted("open-journal-entry")[0]).toEqual([
      {
        ticker: "AAPL",
        name: "AAPL",
        entry_reason: "通知回寫：AAPL alert",
        review_notes: "AAPL price breakout | 門檻:210 | 觸發:212 | 來源：觀察池 | 風險：中 | 選擇性出手 | 環境偏震盪，只做最強標的。",
        tags: ["優先候選", "Q4", "市場:選擇性出手", "來源:警報通知"],
      },
    ]);
    expect(wrapper.emitted("save-journal-filter-preset")[0]).toEqual([
      {
        name: "通知：AAPL",
        description: "由通知中心快速建立",
        scope: "all",
        filters: {
          market: "",
          strategy_code: "",
          tag: "市場:選擇性出手",
          search: "AAPL",
        },
      },
    ]);
    expect(wrapper.emitted("dismiss")[0]).toEqual(["local-1"]);
  });

  it("routes market alerts back to the macro workspace", async () => {
    const wrapper = mount(NotificationPanel, {
      props: {
        notifications: [
          {
            id: "remote-3",
            icon: "!",
            title: "Market risk alert triggered",
            msg: "市場風險警報觸發：進入高風險",
            time: "2026/04/02 10:15",
            createdAt: "2026-04-02T10:15:00+08:00",
            read: false,
            persisted: true,
            category: "alert",
            source: "local_db",
            ticker: null,
            workspaceTarget: "macro",
          },
        ],
      },
    });

    await openPanel(wrapper);

    await wrapper.findAll(".notif-action-btn").find((node) => node.text() === "開啟宏觀").trigger("click");

    expect(wrapper.emitted("open-workspace")[0]).toEqual(["macro"]);
  });

  it("shows notification context tags for persisted alert cards", async () => {
    const wrapper = mount(NotificationPanel, {
      props: {
        notifications: [
          {
            id: "remote-4",
            icon: "!",
            title: "Watchlist alert",
            msg: "AAPL price breakout",
            time: "2026/04/02 10:45",
            createdAt: "2026-04-02T10:45:00+08:00",
            read: false,
            persisted: true,
            category: "alert",
            source: "yahoo_finance",
            ticker: "AAPL",
            contextSource: "watchlist",
            contextTags: ["優先候選", "Q4"],
            macroSummary: {
              overall_risk: "medium",
              trade_posture: "selective",
              decision_hint: "環境偏震盪，只做最強標的。",
            },
          },
        ],
      },
    });

    await openPanel(wrapper);

    expect(wrapper.text()).toContain("來源：觀察池");
    expect(wrapper.text()).toContain("風險：中");
    expect(wrapper.text()).toContain("選擇性出手");
    expect(wrapper.text()).toContain("優先候選");
    expect(wrapper.text()).toContain("Q4");
  });
  it("surfaces watch group context and emits watch-group shortcuts", async () => {
    const wrapper = mount(NotificationPanel, {
      props: {
        notifications: [
          {
            id: "remote-5",
            icon: "!",
            title: "Group alert",
            msg: "AAPL reclaimed intraday pivot",
            time: "2026/04/02 11:05",
            createdAt: "2026-04-02T11:05:00+08:00",
            read: false,
            persisted: true,
            category: "alert",
            source: "yahoo_finance",
            ticker: "AAPL",
            contextSource: "watchlist_group",
            contextGroupName: "Journal Flow",
            contextTags: ["å„ªå…ˆå€™é¸"],
            thresholdValue: 210,
            triggerValue: 212,
            payload: {
              snapshot_price: 210.5,
              snapshot_source: "yahoo_finance",
              snapshot_timestamp: "2026-04-02T11:00:00+08:00",
            },
          },
        ],
      },
    });

    await openPanel(wrapper);

    expect(wrapper.text()).toContain("Journal Flow");

    const actionButtons = wrapper.findAll(".notif-action-btn");
    await actionButtons[1].trigger("click");
    await actionButtons[2].trigger("click");
    await actionButtons[3].trigger("click");

    expect(wrapper.emitted("open-watch-group")[0]).toEqual([
      { groupName: "Journal Flow", ticker: "AAPL" },
    ]);
    expect(wrapper.emitted("open-journal-entry")[0][0].review_notes).toContain("Journal Flow");
    expect(wrapper.emitted("open-journal-entry")[0][0].review_notes).toContain("210.5");
    expect(wrapper.emitted("open-journal-entry")[0][0].tags.some((tag) => tag.includes("Journal Flow"))).toBe(true);
    expect(wrapper.emitted("open-journal-entry")[0][0].tags.some((tag) => tag.includes("警報"))).toBe(true);
    expect(wrapper.emitted("save-journal-filter-preset")[0][0].filters.tag).toContain("Journal Flow");
  });

  it("can collapse and reopen the floating notification center", async () => {
    const wrapper = mount(NotificationPanel, {
      props: {
        notifications: [
          {
            id: "local-1",
            icon: "i",
            title: "Saved",
            msg: "Workspace stored",
            time: "2026/04/02 09:31",
            createdAt: "2026-04-02T09:31:00+08:00",
            read: false,
            persisted: false,
            category: "session",
            source: "session",
            ticker: null,
          },
        ],
      },
    });

    expect(wrapper.find('[data-testid="notif-center-panel"]').exists()).toBe(false);

    await openPanel(wrapper);
    expect(wrapper.find('[data-testid="notif-center-panel"]').exists()).toBe(true);

    await wrapper.get('[data-testid="notif-center-collapse"]').trigger("click");
    expect(wrapper.find('[data-testid="notif-center-panel"]').exists()).toBe(false);
  });
});
