import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import EventCenter from "./EventCenter.vue";

describe("EventCenter", () => {
  it("emits a prefilled event reminder shortcut", async () => {
    const wrapper = mount(EventCenter, {
      props: {
        currentTicker: "AAPL",
        currentName: "Apple",
        calendarEvents: [],
        tickerEvents: [
          {
            title: "AAPL Earnings Call",
            event_type: "earnings",
            event_date: "2099-04-05",
            importance: "high",
          },
        ],
        tickerNews: [],
      },
    });

    await wrapper.find(".intel-btn.secondary").trigger("click");

    expect(wrapper.emitted("create-alert")[0][0]).toMatchObject({
      ticker: "AAPL",
      type: "event",
      condition: "within_days",
      event_type: "earnings",
      event_title: "AAPL Earnings Call",
      importance: "high",
      event_scope: "ticker",
      target_label: "Apple",
    });
  });
});
