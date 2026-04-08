const OVERVIEW_ROUTE_NAMES = new Set(["overview", "macro", "events", "screener", "db"]);
const TERMINAL_ROUTE_NAMES = new Set(["terminal", "dashboard", "alerts"]);
const REVIEW_ROUTE_NAMES = new Set(["journal", "backtest"]);

function normalizeTickerParam(ticker) {
  return String(ticker || "").trim().toUpperCase();
}

export function mapRouteToAppState(route = {}) {
  const name = String(route?.name || "overview");
  const routeTicker = normalizeTickerParam(route?.params?.ticker);

  if (OVERVIEW_ROUTE_NAMES.has(name)) {
    return {
      routeWorkspaceTab: "overview",
      routeRightTab: "indicators",
      routeTicker,
    };
  }

  if (name === "institutional") {
    return {
      routeWorkspaceTab: "institutional",
      routeRightTab: "indicators",
      routeTicker,
    };
  }

  if (REVIEW_ROUTE_NAMES.has(name)) {
    return {
      routeWorkspaceTab: "review",
      routeRightTab: name === "backtest" ? "backtest" : "journal",
      routeTicker,
    };
  }

  return {
    routeWorkspaceTab: "terminal",
    routeRightTab: "alerts",
    routeTicker,
  };
}

export function buildAppRouteLocation({ workspaceTab, rightTab, currentTicker } = {}) {
  const normalizedWorkspace = String(workspaceTab || "").toLowerCase();
  const normalizedRightTab = String(rightTab || "").toLowerCase();
  const normalizedTicker = normalizeTickerParam(currentTicker);
  const params = normalizedTicker ? { ticker: normalizedTicker } : {};

  if (normalizedWorkspace === "overview") {
    return {
      name: "overview",
      params,
    };
  }

  if (normalizedWorkspace === "institutional") {
    return {
      name: "institutional",
      params,
    };
  }

  if (normalizedWorkspace === "review") {
    return {
      name: normalizedRightTab === "backtest" ? "backtest" : "journal",
      params,
    };
  }

  return {
    name: "terminal",
    params,
  };
}
