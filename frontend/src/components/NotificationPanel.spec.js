import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import NotificationPanel from "./NotificationPanel.vue";

describe("NotificationPanel", () => {
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

    expect(wrapper.text()).toContain("AAPL alert");
    expect(wrapper.text()).toContain("Bootstrap");

    await wrapper.findAll(".notif-filter-btn")[1].trigger("click");
    expect(wrapper.text()).toContain("AAPL alert");
    expect(wrapper.text()).not.toContain("Bootstrap");

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

    await wrapper.findAll(".notif-chip").find((node) => node.text() === "本次操作").trigger("click");
    expect(wrapper.text()).toContain("Saved");
    expect(wrapper.text()).not.toContain("AAPL alert");

    await wrapper.find(".notif-search").setValue("");
    await wrapper.findAll(".notif-chip").find((node) => node.text() === "全部類別").trigger("click");
    await wrapper.findAll(".notif-action-btn").find((node) => node.text() === "開啟 AAPL").trigger("click");
    await wrapper.findAll(".notif-action-btn").find((node) => node.text() === "關閉").trigger("click");

    expect(wrapper.emitted("open-ticker")[0]).toEqual(["AAPL"]);
    expect(wrapper.emitted("dismiss")[0]).toEqual(["local-1"]);
  });
});
