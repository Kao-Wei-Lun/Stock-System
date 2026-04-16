import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import InstitutionalStructuredQueryPanel from "./InstitutionalStructuredQueryPanel.vue";

function createProps(overrides = {}) {
  return {
    query: {
      section: "futures",
      dateMode: "range",
      exactDate: "2026-04-15",
      startDate: "2026-04-01",
      endDate: "2026-04-15",
      commodity: "臺股期貨",
      institution: "",
      optionSide: "",
      limit: 300,
      autoSync: false,
    },
    data: {
      section: "futures",
      count: 4,
      filters: {},
      items: [
        {
          resolved_date: "2026-04-10",
          commodity: "臺股期貨",
          institution: "外資",
          trade_net_volume: 1200,
          oi_net_volume: 6400,
          trade_net_amount: 320000000,
          oi_net_amount: 1440000000,
          oi_net_volume_change: 800,
        },
        {
          resolved_date: "2026-04-10",
          commodity: "臺股期貨",
          institution: "投信",
          trade_net_volume: -240,
          oi_net_volume: 1200,
          trade_net_amount: -56000000,
          oi_net_amount: 280000000,
          oi_net_volume_change: -120,
        },
        {
          resolved_date: "2026-04-11",
          commodity: "臺股期貨",
          institution: "外資",
          trade_net_volume: 1560,
          oi_net_volume: 7100,
          trade_net_amount: 390000000,
          oi_net_amount: 1580000000,
          oi_net_volume_change: 700,
        },
        {
          resolved_date: "2026-04-11",
          commodity: "臺股期貨",
          institution: "投信",
          trade_net_volume: -160,
          oi_net_volume: 980,
          trade_net_amount: -32000000,
          oi_net_amount: 248000000,
          oi_net_volume_change: -220,
        },
      ],
    },
    loading: false,
    error: "",
    selectedDate: "2026-04-15",
    selectedFuturesCommodity: "臺股期貨",
    selectedOptionsCommodity: "臺指選擇權",
    ...overrides,
  };
}

describe("InstitutionalStructuredQueryPanel", () => {
  it("renders the structured query summary, chart, and table rows", () => {
    const wrapper = mount(InstitutionalStructuredQueryPanel, {
      props: createProps(),
    });

    expect(wrapper.text()).toContain("TAIFEX 結構化查詢面板");
    expect(wrapper.text()).toContain("結構化時間序列");
    expect(wrapper.text()).toContain("查詢結果");
    expect(wrapper.findAll("tbody tr")).toHaveLength(4);
  });

  it("emits query patch, refresh, and reset actions", async () => {
    const wrapper = mount(InstitutionalStructuredQueryPanel, {
      props: createProps(),
    });

    await wrapper.find("select").setValue("cash_summary");
    await wrapper.findAll("button")[0].trigger("click");
    await wrapper.findAll("button")[1].trigger("click");

    expect(wrapper.emitted("update-query")?.[0]).toEqual([{ section: "cash_summary" }]);
    expect(wrapper.emitted("reset")).toHaveLength(1);
    expect(wrapper.emitted("refresh")).toHaveLength(1);
  });
});
