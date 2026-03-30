import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import RightSidebar from "./RightSidebar.vue";

describe("RightSidebar", () => {
  it("renders persisted alerts and emits delete actions", async () => {
    const wrapper = mount(RightSidebar, {
      props: {
        rightTab: "alerts",
        indicatorSnapshot: {},
        activeInd: {},
        activePanels: {},
        indicatorSettings: {},
        alerts: [
          {
            id: 7,
            ticker: "AAPL",
            type: "price",
            condition: "大於",
            value: 210,
            active: true,
            triggered: false,
          },
        ],
        backtestForm: {},
        backtestResult: null,
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    expect(wrapper.text()).toContain("AAPL");
    expect(wrapper.text()).toContain("監控中");

    await wrapper.find(".alert-card .add-btn").trigger("click");

    expect(wrapper.emitted("delete-alert")[0]).toEqual([7]);
  });
});
