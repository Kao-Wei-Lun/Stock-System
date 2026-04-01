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
        backtestHistory: [],
        backtestLoading: false,
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

  it("renders backtest results and loads persisted runs", async () => {
    const wrapper = mount(RightSidebar, {
      props: {
        rightTab: "backtest",
        indicatorSnapshot: {},
        activeInd: {},
        activePanels: {},
        indicatorSettings: {},
        alerts: [],
        backtestForm: {
          strategy: "MA 黃金/死亡交叉",
          start: "2024-01-01",
          end: "2024-12-31",
          capital: 100000,
          fee: 0.1,
          slippage: 0,
          sl: 5,
          tp: 10,
        },
        backtestResult: {
          strategy: "MA 黃金/死亡交叉",
          start: "2024-01-01",
          end: "2024-12-31",
          capital: 100000,
          finalEquity: 112000,
          totalReturn: 12,
          sellTrades: 3,
          winRate: 66.7,
          maxDrawdown: 4.2,
          sharpe: 1.4,
          bars: 120,
          slippageRate: 0,
          stopLoss: 0.05,
          takeProfit: 0.1,
          equity_curve: [{ equity: 100000 }, { equity: 112000 }],
          trades: [
            {
              id: 1,
              entry_date: "2024-03-01",
              exit_date: "2024-03-12",
              quantity: 1000,
              net_pnl: 12000,
              exit_reason: "take_profit",
            },
          ],
        },
        backtestHistory: [
          {
            id: 21,
            strategy: "MA 黃金/死亡交叉",
            start: "2024-01-01",
            end: "2024-12-31",
            totalReturn: 12,
          },
        ],
        backtestLoading: false,
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    expect(wrapper.text()).toContain("權益曲線");
    expect(wrapper.text()).toContain("交易明細");
    expect(wrapper.text()).toContain("歷史回測");

    await wrapper.find(".bt-history-row").trigger("click");

    expect(wrapper.emitted("load-backtest")[0]).toEqual([21]);
  });
});
