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

  it("maps overview, review, and assets routes into app state", () => {
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

    expect(mapRouteToAppState({
      name: "assets",
      params: { ticker: "2330.tw" },
    })).toEqual({
      routeWorkspaceTab: "assets",
      routeRightTab: "assets",
      routeTicker: "2330.TW",
    });
  });

  it("maps settings routes into app state", () => {
    expect(mapRouteToAppState({
      name: "settings",
      params: { ticker: "2330.tw" },
    })).toEqual({
      routeWorkspaceTab: "settings",
      routeRightTab: "settings",
      routeTicker: "2330.TW",
    });
  });

  it("builds route locations from the workspace shell", () => {
    expect(buildAppRouteLocation({
      workspaceTab: "paper-trading",
      currentTicker: "TMF",
    })).toEqual({
      name: "paper-trading",
    });

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

    expect(buildAppRouteLocation({
      workspaceTab: "settings",
      rightTab: "settings",
      currentTicker: "2330.tw",
    })).toEqual({
      name: "settings",
      params: { ticker: "2330.TW" },
    });

    expect(buildAppRouteLocation({
      workspaceTab: "assets",
      rightTab: "assets",
      currentTicker: "nvda",
    })).toEqual({
      name: "assets",
      params: { ticker: "NVDA" },
    });
  });
});
