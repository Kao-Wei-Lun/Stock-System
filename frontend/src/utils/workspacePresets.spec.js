import { describe, expect, it } from "vitest";

import {
  LEGACY_WORKSPACE_PRESETS_KEY,
  buildWorkspacePayload,
  clearLegacyWorkspacePresets,
  normalizeWorkspaceRecord,
  readLegacyWorkspacePresets,
  toWorkspaceSaveRequest,
} from "./workspacePresets";

describe("workspacePresets", () => {
  it("builds a backend save request from dashboard state", () => {
    const request = toWorkspaceSaveRequest("Morning Desk", {
      currentTicker: "AAPL",
      currentName: "Apple",
      currentPeriod: "1y",
      currentInterval: "1d",
      klineDisplayMode: "week",
      cleanChartMode: true,
      chartLayout: "double",
      compareTickers: ["MSFT"],
      comparisonMode: "price",
      activeTool: "measure",
      leftTab: "watch",
      rightTab: "alerts",
      workspaceTab: "chart",
      activeInd: { ma20: true },
      activePanels: { macd: true },
      indicatorSettings: { macdFast: 12 },
      drawings: [{ id: "d1", type: "trendline", startPrice: 100, endPrice: 120 }],
    });

    expect(request).toEqual({
      name: "Morning Desk",
      chart_layout: "double",
      active_ticker: "AAPL",
      current_period: "1y",
      current_interval: "1d",
      workspace_tab: "chart",
      comparison_mode: "price",
      payload: {
        currentTicker: "AAPL",
        currentName: "Apple",
        currentPeriod: "1y",
        currentInterval: "1d",
        klineDisplayMode: "week",
        cleanChartMode: true,
        chartLayout: "double",
        compareTickers: ["MSFT"],
        comparisonMode: "price",
        activeTool: "measure",
        leftTab: "watch",
        rightTab: "alerts",
        workspaceTab: "chart",
        activeInd: { ma20: true },
        activePanels: { macd: true },
        indicatorSettings: { macdFast: 12 },
        drawings: [{ type: "trendline", startPrice: 100, endPrice: 120 }],
      },
    });
  });

  it("normalizes persisted backend records into workspace snapshots", () => {
    const workspace = normalizeWorkspaceRecord({
      id: 3,
      name: "Swing Desk",
      active_ticker: "2330.TW",
      current_period: "2y",
      current_interval: "1d",
      chart_layout: "quad",
      comparison_mode: "percent",
      workspace_tab: "chart",
      payload: {
        currentTicker: "2330.TW",
        currentName: "TSMC",
        drawings: [{ type: "hline", price: 950 }],
      },
      created_at: "2026-03-29T01:00:00+00:00",
      updated_at: "2026-03-29T02:00:00+00:00",
      is_default: true,
    });

    expect(workspace.id).toBe(3);
    expect(workspace.currentName).toBe("TSMC");
    expect(workspace.chartLayout).toBe("quad");
    expect(workspace.drawings).toEqual([{ type: "hline", price: 950 }]);
    expect(workspace.isDefault).toBe(true);
  });

  it("reads and clears legacy localStorage presets", () => {
    const storage = {
      value: JSON.stringify([{ id: "legacy-1", name: "Legacy Desk" }]),
      getItem() {
        return this.value;
      },
      removeItem(key) {
        if (key === LEGACY_WORKSPACE_PRESETS_KEY) this.value = null;
      },
    };

    expect(readLegacyWorkspacePresets(storage)).toEqual([{ id: "legacy-1", name: "Legacy Desk" }]);
    clearLegacyWorkspacePresets(storage);
    expect(readLegacyWorkspacePresets(storage)).toEqual([]);
  });

  it("builds workspace payloads without mutating drawings ids", () => {
    const payload = buildWorkspacePayload({
      drawings: [{ id: "draw-1", type: "rect", startPrice: 10, endPrice: 20 }],
    });

    expect(payload.drawings).toEqual([{ type: "rect", startPrice: 10, endPrice: 20 }]);
  });
});
