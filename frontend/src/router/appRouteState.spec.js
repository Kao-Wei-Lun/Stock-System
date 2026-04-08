import { describe, expect, it } from "vitest";

import { buildAppRouteLocation, mapRouteToAppState } from "./appRouteState";

describe("appRouteState", () => {
  it("maps legacy dashboard routes into terminal state", () => {
    expect(mapRouteToAppState({
      name: "dashboard",
      params: { ticker: "msft" },
    })).toEqual({
      routeWorkspaceTab: "terminal",
      routeRightTab: "alerts",
      routeTicker: "MSFT",
    });
  });

  it("maps overview and review routes into app state", () => {
    expect(mapRouteToAppState({
      name: "events",
      params: { ticker: "nvda" },
    })).toEqual({
      routeWorkspaceTab: "overview",
      routeRightTab: "indicators",
      routeTicker: "NVDA",
    });

    expect(mapRouteToAppState({
      name: "journal",
      params: { ticker: "aapl" },
    })).toEqual({
      routeWorkspaceTab: "review",
      routeRightTab: "journal",
      routeTicker: "AAPL",
    });
  });

  it("builds route locations from the four-workspace shell", () => {
    expect(buildAppRouteLocation({
      workspaceTab: "review",
      rightTab: "backtest",
      currentTicker: "tsla",
    })).toEqual({
      name: "backtest",
      params: { ticker: "TSLA" },
    });

    expect(buildAppRouteLocation({
      workspaceTab: "overview",
      rightTab: "indicators",
      currentTicker: "spy",
    })).toEqual({
      name: "overview",
      params: { ticker: "SPY" },
    });
  });
});
