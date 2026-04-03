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
              context_source: "watchlist_group",
              context_group_name: "Journal Flow",
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
                context_source: "watchlist_group",
                context_group_name: "Journal Flow",
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
    expect(wrapper.text()).toContain("來源：觀察群組");
    expect(wrapper.text()).toContain("Journal Flow");
    expect(wrapper.text()).toContain("優先候選");
    expect(wrapper.text()).toContain("Q4");
    expect(wrapper.text()).toContain("快照 210.5");
    expect(wrapper.text()).toContain("yahoo_finance");
    expect(wrapper.text()).toContain("市場 中風險 / 選擇性出手");
    expect(wrapper.text()).toContain("監控中");

    const alertButtons = wrapper.findAll(".alert-action-btn");
    await alertButtons[0].trigger("click");
    await wrapper.find(".alert-action-btn.pause").trigger("click");
    await alertButtons[2].trigger("click");
    await wrapper.find(".alert-action-btn.delete").trigger("click");

    expect(wrapper.emitted("open-watch-group")[0]).toEqual([{ groupName: "Journal Flow", ticker: "AAPL" }]);
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

  it("renders basis and event alerts with human-readable labels", () => {
    const wrapper = mount(RightSidebar, {
      props: {
        rightTab: "alerts",
        indicatorSnapshot: {},
        activeInd: {},
        activePanels: {},
        indicatorSettings: {},
        alerts: [
          {
            id: 18,
            ticker: "^TWII",
            type: "basis",
            condition: "大於",
            value: 1.8,
            active: true,
            triggered: false,
            condition_payload: {
              metric: "basis_pct",
              target_label: "臺股期貨 / 加權指數",
            },
          },
          {
            id: 19,
            ticker: "AAPL",
            type: "event",
            condition: "within_days",
            value: 3,
            active: true,
            triggered: false,
          },
        ],
        alertTriggerLogs: {},
        alertLogLoading: {},
        expandedAlertLogId: null,
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

    expect(wrapper.text()).toContain("臺股期貨 / 加權指數");
    expect(wrapper.text()).toContain("Basis · 大於 1.80%");
    expect(wrapper.text()).toContain("事件提醒 · 事件前提醒 3 日內");
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
            tags: ["來源:警報通知", "市場:選擇性出手", "breakout"],
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
    await wrapper.get('[data-testid="journal-entry-source-5-警報通知"]').trigger("click");
    await wrapper.get('[data-testid="journal-entry-save-source-5-警報通知"]').trigger("click");
    await wrapper.get('[data-testid="journal-entry-posture-5-選擇性出手"]').trigger("click");
    await wrapper.get('[data-testid="journal-entry-save-posture-5-選擇性出手"]').trigger("click");
    await wrapper.get('[data-testid="journal-entry-strategy-5-breakout"]').trigger("click");
    await wrapper.get('[data-testid="journal-entry-save-strategy-5-breakout"]').trigger("click");
    await wrapper.get('[data-testid="journal-entry-tag-5-breakout"]').trigger("click");
    await wrapper.find(".journal-action-row .run-btn").trigger("click");

    expect(wrapper.emitted("add-journal-attachment")).toBeTruthy();
    expect(wrapper.emitted("select-journal-entry")[0]).toEqual([5]);
    expect(wrapper.emitted("apply-journal-filter-preset")[0]).toEqual([{ tag: "來源:警報通知", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[1]).toEqual([{ strategy_code: "breakout", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[2]).toEqual([{ tag: "市場:選擇性出手", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[3]).toEqual([{ tag: "breakout", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[4]).toEqual([{ tag: "來源:警報通知", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[5]).toEqual([{ tag: "市場:選擇性出手", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[6]).toEqual([{ strategy_code: "breakout", search: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[7]).toEqual([{ tag: "breakout", search: "" }]);
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
    expect(wrapper.emitted("save-journal-filter-preset")[4]).toEqual([{
      name: "來源：警報通知",
      description: "由歷史紀錄快速建立",
      scope: "ticker",
      filters: {
        market: "",
        strategy_code: "",
        tag: "來源:警報通知",
        search: "",
      },
    }]);
    expect(wrapper.emitted("save-journal-filter-preset")[5]).toEqual([{
      name: "市場：選擇性出手",
      description: "由歷史紀錄快速建立",
      scope: "ticker",
      filters: {
        market: "",
        strategy_code: "",
        tag: "市場:選擇性出手",
        search: "",
      },
    }]);
    expect(wrapper.emitted("save-journal-filter-preset")[6]).toEqual([{
      name: "策略：breakout",
      description: "由歷史紀錄快速建立",
      scope: "ticker",
      filters: {
        market: "",
        strategy_code: "breakout",
        tag: "",
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

  it("shows active preset result summary when current filters match a preset", async () => {
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
        journalEntries: [
          { id: 1, ticker: "AAPL", direction: "long", strategy_code: "breakout", entry_time: "2026-04-01T09:00", tags: ["來源:警報通知"], result: { pnl: 500 } },
          { id: 2, ticker: "MSFT", direction: "long", strategy_code: "breakout", entry_time: "2026-04-02T09:00", tags: ["來源:警報通知"], result: { pnl: 250 } },
        ],
        journalStats: {
          total_entries: 3,
          closed_entries: 2,
          open_entries: 1,
          win_rate: 50,
          net_pnl: 750,
          avg_return_pct: 1.75,
          source_breakdown: [],
          strategy_breakdown: [],
          market_posture_breakdown: [],
          tag_breakdown: [],
        },
        journalLoading: false,
        journalFilterPresets: [
          {
            id: 9,
            name: "警報通知模板",
            description: "只看 alert flow",
            scope: "all",
            filters: {
              market: "TW",
              strategy_code: "breakout",
              tag: "來源:警報通知",
              search: "selective",
            },
          },
        ],
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

    expect(wrapper.get('[data-testid="journal-preset-9"]').classes()).toContain("journal-preset-active");
    expect(wrapper.get('[data-testid="journal-preset-result-summary"]').text()).toContain("警報通知模板");
    expect(wrapper.get('[data-testid="journal-preset-result-summary"]').text()).toContain("只看 alert flow");
    expect(wrapper.get('[data-testid="journal-preset-result-summary"]').text()).toContain("命中筆數");
    expect(wrapper.get('[data-testid="journal-preset-result-summary"]').text()).toContain("3");
    expect(wrapper.get('[data-testid="journal-preset-result-summary"]').text()).toContain("2 / 1");
    expect(wrapper.get('[data-testid="journal-preset-result-summary"]').text()).toContain("+$750");
    expect(wrapper.get('[data-testid="journal-preset-latest-entry"]').text()).toContain("最近命中");
    expect(wrapper.get('[data-testid="journal-preset-latest-entry"]').text()).toContain("MSFT");
    expect(wrapper.get('[data-testid="journal-preset-latest-entry"]').text()).toContain("+$250");
    expect(wrapper.get('[data-testid="journal-preset-add-watchlist"]').text()).toContain("加入目前顯示到自選 (2)");
    expect(wrapper.get('[data-testid="journal-preset-open-alert"]').text()).toContain("為最近命中設警報");

    await wrapper.get('[data-testid="journal-preset-latest-entry"]').trigger("click");
    await wrapper.get('[data-testid="journal-preset-add-watchlist"]').trigger("click");
    await wrapper.get('[data-testid="journal-preset-open-alert"]').trigger("click");

    expect(wrapper.emitted("select-journal-entry")[0]).toEqual([2]);
    expect(wrapper.emitted("add-watchlist")[0]).toEqual([[
      {
        ticker: "AAPL",
        tags: ["日誌復盤", "警報通知模板", "來源:警報通知", "策略:breakout"],
      },
      {
        ticker: "MSFT",
        tags: ["日誌復盤", "警報通知模板", "來源:警報通知", "策略:breakout"],
      },
    ]]);
    expect(wrapper.emitted("open-alert-modal")[0]).toEqual([{
      ticker: "MSFT",
      type: "price",
      condition: "大於",
      value: "",
      context_source: "journal_result",
      context_tags: ["日誌復盤", "警報通知模板", "來源:警報通知", "策略:breakout"],
      snapshot_price: null,
      snapshot_timestamp: "2026-04-02T09:00",
      prefill_hint: "警報通知模板 最近命中",
    }]);
  });

  it("emits a dedicated watch-group payload from active preset results", async () => {
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
          market: "TW",
          direction: "long",
          strategy_code: "breakout",
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
        journalEntries: [
          {
            id: 1,
            ticker: "AAPL",
            direction: "long",
            strategy_code: "breakout",
            entry_time: "2026-04-01T09:00",
            tags: ["來源:警報通知"],
            result: { pnl: 500 },
          },
          {
            id: 2,
            ticker: "MSFT",
            direction: "long",
            strategy_code: "breakout",
            entry_time: "2026-04-02T09:00",
            tags: ["來源:警報通知"],
            result: { pnl: 250 },
          },
        ],
        journalStats: {
          total_entries: 3,
          closed_entries: 2,
          open_entries: 1,
          win_rate: 50,
          net_pnl: 750,
          avg_return_pct: 1.75,
          source_breakdown: [],
          strategy_breakdown: [],
          market_posture_breakdown: [],
          tag_breakdown: [],
        },
        journalLoading: false,
        journalFilterPresets: [
          {
            id: 9,
            name: "警報通知模板",
            description: "只看 alert flow",
            scope: "all",
            filters: {
              market: "TW",
              strategy_code: "breakout",
              tag: "來源:警報通知",
              search: "selective",
            },
          },
        ],
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

    expect(wrapper.get('[data-testid="journal-preset-create-watch-group"]').text()).toContain("(2)");
    await wrapper.get('[data-testid="journal-preset-create-watch-group"]').trigger("click");

    expect(wrapper.emitted("create-watch-group")[0]).toEqual([{
      name: "警報通知模板 命中池",
      items: [
        {
          ticker: "AAPL",
          tags: ["日誌復盤", "警報通知模板", "來源:警報通知", "策略:breakout"],
        },
        {
          ticker: "MSFT",
          tags: ["日誌復盤", "警報通知模板", "來源:警報通知", "策略:breakout"],
        },
      ],
    }]);
  });

  it("toggles between condensed and full preset result rows", async () => {
    const entries = Array.from({ length: 13 }, (_, index) => ({
      id: index + 1,
      ticker: `TK${index + 1}`,
      direction: "long",
      strategy_code: "breakout",
      entry_time: `2026-04-${String(index + 1).padStart(2, "0")}T09:00`,
      tags: ["來源:警報通知"],
      result: { pnl: 100 + index },
    }));

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
        journalEntries: entries,
        journalStats: {
          total_entries: 13,
          closed_entries: 13,
          open_entries: 0,
          win_rate: 100,
          net_pnl: 1300,
          avg_return_pct: 2.1,
          source_breakdown: [],
          strategy_breakdown: [],
          market_posture_breakdown: [],
          tag_breakdown: [],
        },
        journalLoading: false,
        journalFilterPresets: [
          {
            id: 20,
            name: "完整命中模板",
            description: "測試展開清單",
            scope: "all",
            filters: {
              market: "US",
              strategy_code: "breakout",
              tag: "來源:警報通知",
              search: "",
            },
          },
        ],
        journalFilterScope: "all",
        journalFilters: {
          market: "US",
          strategy_code: "breakout",
          tag: "來源:警報通知",
          search: "",
        },
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    expect(wrapper.get('[data-testid="journal-preset-toggle-results"]').text()).toContain("查看全部命中 (13)");
    expect(wrapper.findAll('[data-testid^="journal-history-entry-"]')).toHaveLength(12);

    await wrapper.get('[data-testid="journal-preset-toggle-results"]').trigger("click");

    expect(wrapper.get('[data-testid="journal-preset-toggle-results"]').text()).toContain("收合至前 12 筆");
    expect(wrapper.findAll('[data-testid^="journal-history-entry-"]')).toHaveLength(13);

    await wrapper.get('[data-testid="journal-preset-toggle-results"]').trigger("click");

    expect(wrapper.findAll('[data-testid^="journal-history-entry-"]')).toHaveLength(12);
  });

  it("shows empty-result suggestions and emits recovery actions", async () => {
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
          total_entries: 0,
          closed_entries: 0,
          open_entries: 0,
          win_rate: 0,
          net_pnl: 0,
          avg_return_pct: 0,
          source_breakdown: [],
          strategy_breakdown: [],
          market_posture_breakdown: [],
          tag_breakdown: [],
        },
        journalLoading: false,
        journalFilterPresets: [
          {
            id: 11,
            name: "過濾過嚴",
            description: "只看極窄條件",
            scope: "ticker",
            filters: {
              market: "TW",
              strategy_code: "breakout",
              tag: "來源:警報通知",
              search: "macro",
            },
          },
        ],
        journalFilterScope: "ticker",
        journalFilters: {
          market: "TW",
          strategy_code: "breakout",
          tag: "來源:警報通知",
          search: "macro",
        },
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    expect(wrapper.get('[data-testid="journal-preset-result-summary"]').text()).toContain("目前條件沒有命中任何交易紀錄");
    expect(wrapper.get('[data-testid="journal-empty-scope-all"]').text()).toContain("改看全部紀錄");
    expect(wrapper.get('[data-testid="journal-empty-clear-search"]').text()).toContain("清除關鍵字");
    expect(wrapper.get('[data-testid="journal-empty-reset-all"]').text()).toContain("清除全部篩選");

    await wrapper.get('[data-testid="journal-empty-scope-all"]').trigger("click");
    await wrapper.get('[data-testid="journal-empty-clear-search"]').trigger("click");
    await wrapper.get('[data-testid="journal-empty-reset-all"]').trigger("click");

    expect(wrapper.emitted("update-journal-filter")[0]).toEqual([{ key: "scope", value: "all" }]);
    expect(wrapper.emitted("update-journal-filter")[1]).toEqual([{ key: "search", value: "" }]);
    expect(wrapper.emitted("apply-journal-filter-preset")[0]).toEqual([{
      scope: "ticker",
      market: "",
      strategy_code: "",
      tag: "",
      search: "",
    }]);
  });

  it.skip("emits journal preset save, load, and delete actions", async () => {
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

  it("emits journal preset save, edit, load, and delete actions", async () => {
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
            description: "只看防守 setup",
            scope: "all",
            use_count: 3,
            last_used_at: "2026-04-01T09:00:00+08:00",
            filters: {
              market: "TW",
              strategy_code: "",
              tag: "市場:防守控倉",
              search: "",
            },
          },
        ],
        journalFilterScope: "all",
        journalFilters: {
          market: "TW",
          strategy_code: "breakout",
          tag: "watchlist",
          search: "macro",
        },
        dbStats: null,
        dbStatsLoading: false,
        dbStatsError: "",
        syncingAll: false,
      },
    });

    expect(wrapper.text()).toContain("已用 3");

    await wrapper.get('[data-testid="journal-preset-name"]').setValue("我的模板");
    await wrapper.get('[data-testid="journal-preset-description"]').setValue("用於快速回顧");
    await wrapper.get('[data-testid="journal-preset-save"]').trigger("click");
    await wrapper.get('[data-testid="journal-preset-edit-7"]').trigger("click");

    expect(wrapper.get('[data-testid="journal-preset-name"]').element.value).toBe("高風險日");
    expect(wrapper.get('[data-testid="journal-preset-description"]').element.value).toBe("只看防守 setup");

    await wrapper.get('[data-testid="journal-preset-description"]').setValue("更新後說明");
    await wrapper.get('[data-testid="journal-preset-save"]').trigger("click");
    await wrapper.get('[data-testid="journal-preset-edit-7"]').trigger("click");
    await wrapper.get('[data-testid="journal-preset-cancel"]').trigger("click");
    await wrapper.get('[data-testid="journal-preset-7"]').trigger("click");
    await wrapper.get('[data-testid="journal-preset-delete-7"]').trigger("click");

    expect(wrapper.get('[data-testid="journal-preset-name"]').element.value).toBe("");
    expect(wrapper.get('[data-testid="journal-preset-description"]').element.value).toBe("");
    expect(wrapper.emitted("save-journal-filter-preset")[0]).toEqual([{
      id: null,
      name: "我的模板",
      description: "用於快速回顧",
      scope: "all",
      filters: {
        market: "TW",
        strategy_code: "breakout",
        tag: "watchlist",
        search: "macro",
      },
    }]);
    expect(wrapper.emitted("save-journal-filter-preset")[1]).toEqual([{
      id: 7,
      name: "高風險日",
      description: "更新後說明",
      scope: "all",
      filters: {
        market: "TW",
        strategy_code: "breakout",
        tag: "watchlist",
        search: "macro",
      },
    }]);
    expect(wrapper.emitted("load-journal-filter-preset")[0]).toEqual([{
      id: 7,
      name: "高風險日",
      description: "只看防守 setup",
      scope: "all",
      use_count: 3,
      last_used_at: "2026-04-01T09:00:00+08:00",
      filters: {
        market: "TW",
        strategy_code: "",
        tag: "市場:防守控倉",
        search: "",
      },
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
