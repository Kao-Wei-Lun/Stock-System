import { describe, expect, it } from "vitest";

import { buildAppRouteLocation, mapRouteToAppState } from "./appRouteState";

describe("appRouteState", () => {
  it("maps dashboard routes into chart state", () => {
    expect(mapRouteToAppState({
      name: "dashboard",
      params: { ticker: "msft" },
    })).toEqual({
      routeWorkspaceTab: "chart",
      routeRightTab: "indicators",
      routeTicker: "MSFT",
    });
  });

  it("maps workspace and right-tab routes into app state", () => {
    expect(mapRouteToAppState({
      name: "events",
      params: { ticker: "nvda" },
    })).toEqual({
      routeWorkspaceTab: "events",
      routeRightTab: "indicators",
      routeTicker: "NVDA",
    });

    expect(mapRouteToAppState({
      name: "journal",
      params: { ticker: "aapl" },
    })).toEqual({
      routeWorkspaceTab: "chart",
      routeRightTab: "journal",
      routeTicker: "AAPL",
    });
  });

  it("builds route locations from current dashboard state", () => {
    expect(buildAppRouteLocation({
      workspaceTab: "chart",
      rightTab: "backtest",
      currentTicker: "tsla",
    })).toEqual({
      name: "backtest",
      params: { ticker: "TSLA" },
    });

    expect(buildAppRouteLocation({
      workspaceTab: "macro",
      rightTab: "indicators",
      currentTicker: "spy",
    })).toEqual({
      name: "macro",
      params: { ticker: "SPY" },
    });
  });
});
