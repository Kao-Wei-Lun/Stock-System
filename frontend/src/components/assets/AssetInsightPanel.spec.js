import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AssetInsightPanel from "./AssetInsightPanel.vue";

function buildProps(overrides = {}) {
  return {
    assetLoading: false,
    assetBaseCurrency: "TWD",
    assetSummary: {
      total_asset_value_base: 100000,
      cash_total_base: 25000,
    },
    assetHoldings: [
      { ticker: "AAPL", market_value_base: 20000 },
      { ticker: "TSM", market_value_base: 18000 },
    ],
    assetWarnings: [],
    assetQuoteGaps: [],
    assetReconciliation: { items: [], summary: {} },
    assetAlerts: [],
    ...overrides,
  };
}

describe("AssetInsightPanel", () => {
  it("shows merged user-visible data quality messages and hides debug flags", () => {
    const wrapper = mount(AssetInsightPanel, {
      props: buildProps({
        portfolioDataQualitySummary: {
          severity: "warning",
          user_visible_messages: [
            "有多筆持倉缺少有效報價或匯率，估值可能不完整。",
            "有帳戶存在對帳差異，請確認現金或持倉紀錄。",
            "績效快照不足，無法計算近一日淨值變化。",
          ],
          debug_flags: ["quote_gaps_present", "internal_traceback_should_not_render"],
        },
        performanceDataQualitySummary: {
          severity: "info",
          user_visible_messages: [
            "績效快照不足，無法計算近一日淨值變化。",
            "前一筆資產總值為 0，無法計算百分比。",
          ],
          debug_flags: ["previous_total_asset_zero"],
        },
      }),
    });

    const card = wrapper.get('[data-testid="asset-data-quality-summary"]');
    expect(card.classes()).toContain("warning");
    expect(card.text()).toContain("有多筆持倉缺少有效報價或匯率，估值可能不完整。");
    expect(card.text()).toContain("有帳戶存在對帳差異，請確認現金或持倉紀錄。");
    expect(card.text()).toContain("績效快照不足，無法計算近一日淨值變化。");
    expect(card.text()).toContain("另有 1 項資料品質提醒");
    expect(wrapper.text()).not.toContain("quote_gaps_present");
    expect(wrapper.text()).not.toContain("internal_traceback_should_not_render");
  });

  it("shows a quiet ok state without warning styling", () => {
    const wrapper = mount(AssetInsightPanel, {
      props: buildProps({
        portfolioDataQualitySummary: {
          severity: "ok",
          user_visible_messages: [],
          debug_flags: [],
        },
      }),
    });

    const card = wrapper.get('[data-testid="asset-data-quality-summary"]');
    expect(card.text()).toContain("資料品質目前正常");
    expect(card.classes()).not.toContain("warning");
  });

  it("keeps the existing insight display when metadata is absent", () => {
    const wrapper = mount(AssetInsightPanel, {
      props: buildProps(),
    });

    expect(wrapper.find('[data-testid="asset-data-quality-summary"]').exists()).toBe(false);
    expect(wrapper.text()).toContain("目前沒有需要特別注意的資產提醒");
  });
});
