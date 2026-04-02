import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import EventCenter from "./EventCenter.vue";
import MacroDashboard from "./MacroDashboard.vue";
import ScreenerWorkspace from "./ScreenerWorkspace.vue";


describe("Market workspaces", () => {
  it("renders event center data and emits ticker open actions", async () => {
    const wrapper = mount(EventCenter, {
      props: {
        currentTicker: "AAPL",
        currentName: "Apple",
        calendarEvents: [
          { ticker: "AAPL", title: "AAPL Earnings", event_type: "earnings", event_date: "2026-04-10", importance: "high" },
        ],
        tickerEvents: [
          { ticker: "AAPL", title: "AAPL Earnings", event_type: "earnings", event_date: "2026-04-10", importance: "high" },
        ],
        tickerNews: [
          { title: "Apple expands AI rollout", source: "Reuters", published_at: "2026-04-02T00:00:00+00:00", url: "https://example.com/apple" },
        ],
      },
    });

    expect(wrapper.text()).toContain("事件中心");
    expect(wrapper.text()).toContain("Apple expands AI rollout");

    await wrapper.find(".event-row").trigger("click");
    expect(wrapper.emitted("open-ticker")[0]).toEqual(["AAPL"]);
  });

  it("renders macro dashboard summary", () => {
    const wrapper = mount(MacroDashboard, {
      props: {
        macroDashboard: {
          snapshot_date: "2026-04-02",
          summary: {
            overall_risk: "high",
            regime: "risk_off",
            trade_posture: "defensive",
            decision_hint: "系統性風險升高，今天優先保留現金、降低部位，等待風險收斂。",
            risk_drivers: [{ tone: "risk", label: "VIX 偏高", value: "29.40" }],
            tailwinds: [{ tone: "positive", label: "美元轉弱", value: "-0.80%" }],
          },
          items: [
            {
              metric_code: "VIX",
              metric_name: "CBOE Volatility Index",
              value: 29.4,
              change_pct: 1.1,
              date: "2026-04-02",
              source: "yahoo_finance",
            },
          ],
        },
      },
    });

    expect(wrapper.text()).toContain("高風險");
    expect(wrapper.text()).toContain("Risk-off");
    expect(wrapper.text()).toContain("防守控倉");
    expect(wrapper.text()).toContain("美元轉弱");
    expect(wrapper.text()).toContain("VIX");
  });

  it("renders screener results and emits actions", async () => {
    const wrapper = mount(ScreenerWorkspace, {
      props: {
        currentTicker: "AAPL",
        loading: false,
        filters: {
          market: "ALL",
          search: "",
          sector: "",
          min_price: "",
          min_volume_ratio: "",
          max_pe_ratio: "",
          min_dividend_yield: "",
          near_52w_high_pct: "",
          upcoming_event_days: "",
          chip_bias: "any",
          ma_alignment: "any",
          sort_by: "score",
          limit: 50,
        },
        presets: [
          { id: 1, name: "量增突破", description: "測試模板", filters: { market: "US" } },
        ],
        results: {
          total: 1,
          market_context: {
            overall_risk: "medium",
            trade_posture: "selective",
            decision_hint: "環境偏震盪，只做最強標的，並縮小部位與嚴守停損。",
          },
          items: [
            {
              ticker: "AAPL",
              market: "US",
              name: "Apple",
              close: 210,
              change_pct: 2.3,
              volume_ratio: 1.9,
              score: 88,
              macro_adjustment: 6,
              setup_quality: 4,
              next_event: { event_date: "2026-04-10" },
            },
          ],
        },
      },
    });

    expect(wrapper.text()).toContain("選股器");
    expect(wrapper.text()).toContain("AAPL");
    expect(wrapper.text()).toContain("選擇性出手");
    expect(wrapper.text()).toContain("+6");

    await wrapper.find(".preset-chip").trigger("click");
    expect(wrapper.emitted("load-preset")[0][0].name).toBe("量增突破");

    const actionButtons = wrapper.findAll(".tiny-btn");
    await actionButtons[0].trigger("click");
    await actionButtons[2].trigger("click");

    expect(wrapper.emitted("open-ticker")[0]).toEqual(["AAPL"]);
    expect(wrapper.emitted("add-alert")[0]).toEqual(["AAPL"]);
  });
});
