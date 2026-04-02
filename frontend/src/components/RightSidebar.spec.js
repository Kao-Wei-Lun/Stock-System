import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import RightSidebar from "./RightSidebar.vue";

describe("RightSidebar", () => {
  it("renders persisted alerts, trigger logs, and emits alert actions", async () => {
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
            condition_payload: {
              context_source: "watchlist",
              context_tags: ["優先候選", "Q4"],
              snapshot_price: 210.5,
            },
          },
        ],
        alertTriggerLogs: {
          7: [
            {
              id: 99,
              alert_id: 7,
              created_at: "2026-04-02T09:15:00+08:00",
              trigger_value: 212,
              threshold_value: 210,
              payload: {
                quote: {
                  source: "yahoo_finance",
                },
                macro_summary: {
                  overall_risk: "medium",
                  trade_posture: "selective",
                },
              },
            },
          ],
        },
        alertLogLoading: {},
        expandedAlertLogId: 7,
        backtestForm: {},
        backtestResult: null,
        backtestHistory: [],
        backtestLoading: false,
        journalForm: {
          id: null,
          ticker: "AAPL",
          market: "US",
          direction: "long",
          strategy_code: "",
          entry_time: "2026-04-01T09:00",
          entry_price: "",
          exit_time: "",
          exit_price: "",
          size: 1,
          stop_loss: "",
          take_profit: "",
          entry_reason: "",
          exit_reason: "",
          emotion_tag: "",
          review_notes: "",
          tags_text: "",
          attachment_path: "",
          attachment_type: "",
          attachments: [],
        },
        journalEntries: [],
        journalStats: null,
        journalLoading: false,
        journalFilterScope: "ticker",
        journalFilters: {
          market: "",
          strategy_code: "",
          tag: "",
          search: "",
        },
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    expect(wrapper.text()).toContain("AAPL");
    expect(wrapper.text()).toContain("MySQL / alerts");
    expect(wrapper.text()).toContain("來源：觀察池");
    expect(wrapper.text()).toContain("優先候選");
    expect(wrapper.text()).toContain("Q4");
    expect(wrapper.text()).toContain("快照 210.5");
    expect(wrapper.text()).toContain("yahoo_finance");
    expect(wrapper.text()).toContain("市場 中風險 / 選擇性出手");
    expect(wrapper.text()).toContain("監控中");

    await wrapper.find(".alert-action-btn.pause").trigger("click");
    await wrapper.find(".alert-action-btn.log").trigger("click");
    await wrapper.find(".alert-action-btn.delete").trigger("click");

    expect(wrapper.emitted("toggle-alert-active")[0]).toEqual([7]);
    expect(wrapper.emitted("toggle-alert-log")[0]).toEqual([7]);
    expect(wrapper.emitted("delete-alert")[0]).toEqual([7]);
  });

  it("renders market risk alerts with readable labels", () => {
    const wrapper = mount(RightSidebar, {
      props: {
        rightTab: "alerts",
        indicatorSnapshot: {},
        activeInd: {},
        activePanels: {},
        indicatorSettings: {},
        alerts: [
          {
            id: 8,
            ticker: "MARKET",
            type: "market_risk",
            condition: "high",
            value: null,
            active: true,
            triggered: true,
          },
        ],
        alertTriggerLogs: {
          8: [
            {
              id: 108,
              alert_id: 8,
              created_at: "2026-04-02T10:05:00+08:00",
              trigger_value: "high",
              threshold_value: "high",
              payload: {
                quote: {
                  source: "local_db",
                },
              },
            },
          ],
        },
        alertLogLoading: {},
        expandedAlertLogId: 8,
        backtestForm: {},
        backtestResult: null,
        backtestHistory: [],
        backtestLoading: false,
        journalForm: {
          id: null,
          ticker: "AAPL",
          market: "US",
          direction: "long",
          strategy_code: "",
          entry_time: "2026-04-01T09:00",
          entry_price: "",
          exit_time: "",
          exit_price: "",
          size: 1,
          stop_loss: "",
          take_profit: "",
          entry_reason: "",
          exit_reason: "",
          emotion_tag: "",
          review_notes: "",
          tags_text: "",
          attachment_path: "",
          attachment_type: "",
          attachments: [],
        },
        journalEntries: [],
        journalStats: null,
        journalLoading: false,
        journalFilterScope: "ticker",
        journalFilters: {
          market: "",
          strategy_code: "",
          tag: "",
          search: "",
        },
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    expect(wrapper.text()).toContain("市場");
    expect(wrapper.text()).toContain("市場風險");
    expect(wrapper.text()).toContain("進入高風險");
    expect(wrapper.text()).toContain("觸發值 高風險");
    expect(wrapper.text()).toContain("門檻 高風險");
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
        journalForm: {
          id: null,
          ticker: "AAPL",
          market: "US",
          direction: "long",
          strategy_code: "",
          entry_time: "2026-04-01T09:00",
          entry_price: "",
          exit_time: "",
          exit_price: "",
          size: 1,
          stop_loss: "",
          take_profit: "",
          entry_reason: "",
          exit_reason: "",
          emotion_tag: "",
          review_notes: "",
          tags_text: "",
          attachment_path: "",
          attachment_type: "",
          attachments: [],
        },
        journalEntries: [],
        journalStats: null,
        journalLoading: false,
        journalFilterScope: "ticker",
        journalFilters: {
          market: "",
          strategy_code: "",
          tag: "",
          search: "",
        },
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

  it("emits journal actions", async () => {
    const wrapper = mount(RightSidebar, {
      props: {
        rightTab: "journal",
        indicatorSnapshot: {},
        activeInd: {},
        activePanels: {},
        indicatorSettings: {},
        alerts: [],
        backtestForm: {},
        backtestResult: null,
        backtestHistory: [],
        backtestLoading: false,
        journalForm: {
          id: null,
          ticker: "AAPL",
          market: "US",
          direction: "long",
          strategy_code: "",
          entry_time: "2026-04-01T09:00",
          entry_price: 210,
          exit_time: "",
          exit_price: "",
          size: 10,
          stop_loss: "",
          take_profit: "",
          entry_reason: "",
          exit_reason: "",
          emotion_tag: "",
          review_notes: "",
          tags_text: "breakout",
          attachment_path: "C:/shots/aapl.png",
          attachment_type: "image/png",
          attachments: [],
        },
        journalEntries: [
          {
            id: 5,
            ticker: "AAPL",
            direction: "long",
            strategy_code: "breakout",
            entry_time: "2026-04-01T09:00",
            tags: ["breakout"],
            result: { pnl: 500 },
          },
        ],
        journalStats: {
          total_entries: 1,
          closed_entries: 1,
          open_entries: 0,
          win_rate: 100,
          net_pnl: 500,
          avg_return_pct: 2.5,
          source_breakdown: [
            {
              key: "警報通知",
              count: 1,
              closed_count: 1,
              win_rate: 100,
              net_pnl: 500,
              avg_return_pct: 2.5,
            },
          ],
          strategy_breakdown: [
            {
              key: "breakout",
              count: 1,
              closed_count: 1,
              win_rate: 100,
              net_pnl: 500,
              avg_return_pct: 2.5,
            },
          ],
          market_posture_breakdown: [
            {
              key: "選擇性出手",
              count: 1,
              closed_count: 1,
              win_rate: 100,
              net_pnl: 500,
              avg_return_pct: 2.5,
            },
          ],
          tag_breakdown: [
            {
              key: "breakout",
              count: 1,
              closed_count: 1,
              win_rate: 100,
              net_pnl: 500,
              avg_return_pct: 2.5,
            },
          ],
        },
        journalLoading: false,
        journalFilterScope: "ticker",
        journalFilters: {
          market: "",
          strategy_code: "",
          tag: "",
          search: "",
        },
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    expect(wrapper.text()).toContain("交易日誌");
    expect(wrapper.text()).toContain("統計摘要");
    expect(wrapper.text()).toContain("來源拆解");
    expect(wrapper.text()).toContain("警報通知");
    expect(wrapper.text()).toContain("策略拆解");
    expect(wrapper.text()).toContain("市場情境");
    expect(wrapper.text()).toContain("選擇性出手");
    expect(wrapper.text()).toContain("高頻標籤");
    expect(wrapper.text()).toContain("breakout");

    await wrapper.find(".journal-card .add-btn").trigger("click");
    await wrapper.findAll(".bt-history-row")[0].trigger("click");
    await wrapper.get('[data-testid="journal-source-警報通知"]').trigger("click");
    await wrapper.get('[data-testid="journal-source-save-警報通知"]').trigger("click");
    await wrapper.get('[data-testid="journal-strategy-breakout"]').trigger("click");
    await wrapper.get('[data-testid="journal-strategy-save-breakout"]').trigger("click");
    await wrapper.get('[data-testid="journal-posture-選擇性出手"]').trigger("click");
    await wrapper.get('[data-testid="journal-posture-save-選擇性出手"]').trigger("click");
    await wrapper.get('[data-testid="journal-tag-breakout"]').trigger("click");
    await wrapper.get('[data-testid="journal-tag-save-breakout"]').trigger("click");
    await wrapper.get('[data-testid="journal-entry-tag-5-breakout"]').trigger("click");
    await wrapper.find(".journal-action-row .run-btn").trigger("click");

    expect(wrapper.emitted("add-journal-attachment")).toBeTruthy();
    expect(wrapper.emitted("select-journal-entry")[0]).toEqual([5]);
    expect(wrapper.emitted("apply-journal-filter-preset")[0]).toEqual([{ tag: "來源:警報通知", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[1]).toEqual([{ strategy_code: "breakout", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[2]).toEqual([{ tag: "市場:選擇性出手", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[3]).toEqual([{ tag: "breakout", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[4]).toEqual([{ tag: "breakout", search: "" }]);
    expect(wrapper.emitted("save-journal-filter-preset")[0]).toEqual([{
      name: "來源：警報通知",
      description: "由來源拆解快速建立",
      scope: "ticker",
      filters: {
        market: "",
        strategy_code: "",
        tag: "來源:警報通知",
        search: "",
      },
    }]);
    expect(wrapper.emitted("save-journal-filter-preset")[1]).toEqual([{
      name: "策略：breakout",
      description: "由策略拆解快速建立",
      scope: "ticker",
      filters: {
        market: "",
        strategy_code: "breakout",
        tag: "",
        search: "",
      },
    }]);
    expect(wrapper.emitted("save-journal-filter-preset")[2]).toEqual([{
      name: "市場：選擇性出手",
      description: "由市場情境快速建立",
      scope: "ticker",
      filters: {
        market: "",
        strategy_code: "",
        tag: "市場:選擇性出手",
        search: "",
      },
    }]);
    expect(wrapper.emitted("save-journal-filter-preset")[3]).toEqual([{
      name: "標籤：breakout",
      description: "由高頻標籤快速建立",
      scope: "ticker",
      filters: {
        market: "",
        strategy_code: "",
        tag: "breakout",
        search: "",
      },
    }]);
    expect(wrapper.emitted("save-journal-entry")).toBeTruthy();
  });

  it("shows active journal filters and lets the user clear them", async () => {
    const wrapper = mount(RightSidebar, {
      props: {
        rightTab: "journal",
        indicatorSnapshot: {},
        activeInd: {},
        activePanels: {},
        indicatorSettings: {},
        alerts: [],
        backtestForm: {},
        backtestResult: null,
        backtestHistory: [],
        backtestLoading: false,
        journalForm: {
          id: null,
          ticker: "AAPL",
          market: "US",
          direction: "long",
          strategy_code: "",
          entry_time: "2026-04-01T09:00",
          entry_price: "",
          exit_time: "",
          exit_price: "",
          size: 1,
          stop_loss: "",
          take_profit: "",
          entry_reason: "",
          exit_reason: "",
          emotion_tag: "",
          review_notes: "",
          tags_text: "",
          attachment_path: "",
          attachment_type: "",
          attachments: [],
        },
        journalEntries: [],
        journalStats: null,
        journalLoading: false,
        journalFilterScope: "all",
        journalFilters: {
          market: "TW",
          strategy_code: "breakout",
          tag: "來源:警報通知",
          search: "selective",
        },
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    expect(wrapper.text()).toContain("目前篩選");
    expect(wrapper.text()).toContain("範圍：全部紀錄");
    expect(wrapper.text()).toContain("標籤：來源:警報通知");

    await wrapper.get('[data-testid="journal-filter-scope"]').trigger("click");
    await wrapper.get('[data-testid="journal-filter-tag"]').trigger("click");
    await wrapper.get('[data-testid="journal-filter-reset"]').trigger("click");

    expect(wrapper.emitted("update-journal-filter")[0]).toEqual([{ key: "scope", value: "ticker" }]);
    expect(wrapper.emitted("update-journal-filter")[1]).toEqual([{ key: "tag", value: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[0]).toEqual([{
      scope: "ticker",
      market: "",
      strategy_code: "",
      tag: "",
      search: "",
    }]);
  });

  it("emits journal preset save, load, and delete actions", async () => {
    const wrapper = mount(RightSidebar, {
      props: {
        rightTab: "journal",
        indicatorSnapshot: {},
        activeInd: {},
        activePanels: {},
        indicatorSettings: {},
        alerts: [],
        backtestForm: {},
        backtestResult: null,
        backtestHistory: [],
        backtestLoading: false,
        journalForm: {
          id: null,
          ticker: "AAPL",
          market: "US",
          direction: "long",
          strategy_code: "",
          entry_time: "2026-04-01T09:00",
          entry_price: "",
          exit_time: "",
          exit_price: "",
          size: 1,
          stop_loss: "",
          take_profit: "",
          entry_reason: "",
          exit_reason: "",
          emotion_tag: "",
          review_notes: "",
          tags_text: "",
          attachment_path: "",
          attachment_type: "",
          attachments: [],
        },
        journalEntries: [],
        journalStats: null,
        journalLoading: false,
        journalFilterPresets: [
          {
            id: 7,
            name: "高風險日",
            scope: "all",
            filters: { tag: "市場:防守控倉" },
          },
        ],
        journalFilterScope: "ticker",
        journalFilters: {
          market: "",
          strategy_code: "",
          tag: "",
          search: "",
        },
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    await wrapper.get('[data-testid="journal-preset-name"]').setValue("我的模板");
    await wrapper.get('[data-testid="journal-preset-save"]').trigger("click");
    await wrapper.get('[data-testid="journal-preset-7"]').trigger("click");
    await wrapper.get('[data-testid="journal-preset-delete-7"]').trigger("click");

    expect(wrapper.emitted("save-journal-filter-preset")[0]).toEqual(["我的模板"]);
    expect(wrapper.emitted("load-journal-filter-preset")[0]).toEqual([{
      id: 7,
      name: "高風險日",
      scope: "all",
      filters: { tag: "市場:防守控倉" },
    }]);
    expect(wrapper.emitted("delete-journal-filter-preset")[0]).toEqual([7]);
  });

  it("merges active journal filters into quick-save preset drafts", async () => {
    const wrapper = mount(RightSidebar, {
      props: {
        rightTab: "journal",
        indicatorSnapshot: {},
        activeInd: {},
        activePanels: {},
        indicatorSettings: {},
        alerts: [],
        backtestForm: {},
        backtestResult: null,
        backtestHistory: [],
        backtestLoading: false,
        journalForm: {
          id: null,
          ticker: "AAPL",
          market: "US",
          direction: "long",
          strategy_code: "",
          entry_time: "2026-04-01T09:00",
          entry_price: "",
          exit_time: "",
          exit_price: "",
          size: 1,
          stop_loss: "",
          take_profit: "",
          entry_reason: "",
          exit_reason: "",
          emotion_tag: "",
          review_notes: "",
          tags_text: "",
          attachment_path: "",
          attachment_type: "",
          attachments: [],
        },
        journalEntries: [],
        journalStats: {
          total_entries: 1,
          closed_entries: 1,
          open_entries: 0,
          win_rate: 100,
          net_pnl: 500,
          avg_return_pct: 2.5,
          source_breakdown: [
            {
              key: "警報通知",
              count: 1,
              closed_count: 1,
              win_rate: 100,
              net_pnl: 500,
              avg_return_pct: 2.5,
            },
          ],
        },
        journalLoading: false,
        journalFilterPresets: [],
        journalFilterScope: "all",
        journalFilters: {
          market: "TW",
          strategy_code: "pullback",
          tag: "",
          search: "macro",
        },
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    await wrapper.get('[data-testid="journal-source-save-警報通知"]').trigger("click");

    expect(wrapper.emitted("save-journal-filter-preset")[0]).toEqual([{
      name: "來源：警報通知",
      description: "由來源拆解快速建立",
      scope: "all",
      filters: {
        market: "TW",
        strategy_code: "pullback",
        tag: "來源:警報通知",
        search: "",
      },
    }]);
  });
});
