const WORKSPACE_ROUTE_NAMES = new Set(["institutional", "events", "macro", "screener"]);
const RIGHT_TAB_ROUTE_NAMES = new Set(["alerts", "backtest", "journal", "db"]);

function normalizeTickerParam(ticker) {
  return String(ticker || "").trim().toUpperCase();
}

export function mapRouteToAppState(route = {}) {
  const name = String(route?.name || "dashboard");
  const routeTicker = normalizeTickerParam(route?.params?.ticker);

  if (WORKSPACE_ROUTE_NAMES.has(name)) {
    return {
      routeWorkspaceTab: name,
      routeRightTab: "indicators",
      routeTicker,
    };
  }

  if (RIGHT_TAB_ROUTE_NAMES.has(name)) {
    return {
      routeWorkspaceTab: "chart",
      routeRightTab: name,
      routeTicker,
    };
  }

  return {
    routeWorkspaceTab: "chart",
    routeRightTab: "indicators",
    routeTicker,
  };
}

export function buildAppRouteLocation({ workspaceTab, rightTab, currentTicker } = {}) {
  const normalizedWorkspace = WORKSPACE_ROUTE_NAMES.has(String(workspaceTab || ""))
    ? String(workspaceTab)
    : "chart";
  const normalizedRightTab = RIGHT_TAB_ROUTE_NAMES.has(String(rightTab || ""))
    ? String(rightTab)
    : "indicators";
  const normalizedTicker = normalizeTickerParam(currentTicker);
  const params = normalizedTicker ? { ticker: normalizedTicker } : {};

  if (normalizedWorkspace !== "chart") {
    return {
      name: normalizedWorkspace,
      params,
    };
  }

  if (normalizedRightTab !== "indicators") {
    return {
      name: normalizedRightTab,
      params,
    };
  }

  return {
    name: "dashboard",
    params,
  };
}
