export const LEGACY_WORKSPACE_PRESETS_KEY = "quantvision.workspace.presets.v1";

export function readLegacyWorkspacePresets(storage) {
  if (!storage) return [];
  try {
    const parsed = JSON.parse(storage.getItem(LEGACY_WORKSPACE_PRESETS_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
}

export function clearLegacyWorkspacePresets(storage) {
  if (!storage) return;
  storage.removeItem(LEGACY_WORKSPACE_PRESETS_KEY);
}

export function buildWorkspacePayload(state) {
  return {
    currentTicker: state.currentTicker || null,
    currentName: state.currentName || null,
    currentPeriod: state.currentPeriod || "1y",
    currentInterval: state.currentInterval || "1d",
    klineDisplayMode: state.klineDisplayMode || "day",
    cleanChartMode: Boolean(state.cleanChartMode),
    chartLayout: state.chartLayout || "single",
    compareTickers: Array.isArray(state.compareTickers) ? [...state.compareTickers] : [],
    comparisonMode: state.comparisonMode || "percent",
    activeTool: state.activeTool || "cursor",
    leftTab: state.leftTab || "watch",
    rightTab: state.rightTab || "indicators",
    workspaceTab: state.workspaceTab || "chart",
    screenerFilters: { ...(state.screenerFilters || {}) },
    activeInd: { ...(state.activeInd || {}) },
    activePanels: { ...(state.activePanels || {}) },
    indicatorSettings: { ...(state.indicatorSettings || {}) },
    drawings: Array.isArray(state.drawings)
      ? state.drawings.map(({ id, ...drawing }) => ({ ...drawing }))
      : [],
  };
}

export function toWorkspaceSaveRequest(name, state) {
  const payload = buildWorkspacePayload(state);
  return {
    name,
    chart_layout: payload.chartLayout,
    active_ticker: payload.currentTicker,
    current_period: payload.currentPeriod,
    current_interval: payload.currentInterval,
    workspace_tab: payload.workspaceTab,
    comparison_mode: payload.comparisonMode,
    payload,
  };
}

export function normalizeWorkspaceRecord(record) {
  const payload = record?.payload && typeof record.payload === "object" ? record.payload : {};
  return {
    id: record?.id,
    name: record?.name || "Untitled Workspace",
    savedAt: record?.updated_at || record?.created_at || null,
    currentTicker: payload.currentTicker || record?.active_ticker || null,
    currentName: payload.currentName || payload.currentTicker || record?.active_ticker || null,
    currentPeriod: payload.currentPeriod || record?.current_period || "1y",
    currentInterval: payload.currentInterval || record?.current_interval || "1d",
    klineDisplayMode: payload.klineDisplayMode || "day",
    cleanChartMode: Boolean(payload.cleanChartMode),
    chartLayout: payload.chartLayout || record?.chart_layout || "single",
    compareTickers: Array.isArray(payload.compareTickers) ? payload.compareTickers : [],
    comparisonMode: payload.comparisonMode || record?.comparison_mode || "percent",
    activeTool: payload.activeTool || "cursor",
    leftTab: payload.leftTab || "watch",
    rightTab: payload.rightTab || "indicators",
    workspaceTab: payload.workspaceTab || record?.workspace_tab || "chart",
    screenerFilters: payload.screenerFilters || {},
    activeInd: payload.activeInd || {},
    activePanels: payload.activePanels || {},
    indicatorSettings: payload.indicatorSettings || {},
    drawings: Array.isArray(payload.drawings) ? payload.drawings : [],
    isDefault: Boolean(record?.is_default),
  };
}
