import { normalizeIndicatorSettings } from "../../utils/indicatorUtils";
import {
  buildWorkspacePayload,
  clearLegacyWorkspacePresets,
  normalizeWorkspaceRecord,
  readLegacyWorkspacePresets,
  toWorkspaceSaveRequest,
} from "../../utils/workspacePresets";

export function sameWorkspaceId(left, right) {
  if (left == null || right == null) return false;
  return String(left) === String(right);
}

export function createDashboardWorkspacePersistence({
  dashboardApi,
  isBrowser,
  workspacePresets,
  activeWorkspacePresetId,
  currentTicker,
  currentName,
  currentPeriod,
  currentInterval,
  klineDisplayMode,
  chartEngineMode,
  cleanChartMode,
  chartLayout,
  compareTickers,
  comparisonMode,
  activeTool,
  leftTab,
  rightTab,
  workspaceTab,
  screenerFilters,
  activeInd,
  activePanels,
  indicatorSettings,
  drawings,
  selectedDrawingId,
  rawOhlcData,
  crosshair,
  defaultActiveInd,
  defaultActivePanels,
  chartLayoutOptions,
  toolOptions,
  workspaceTabOptions,
  normalizeTicker,
  resolveDashboardTimeframeForTicker,
  getEffectiveKlineDisplayMode,
  normalizeChartEngineMode,
  normalizeDashboardRightTab,
  createDrawingEntry,
  applyScreenerFilters,
  clearRealtimeTicker,
  unsubscribeTicker,
  subscribeTicker,
  rememberRecentTicker,
  ensureKline,
  loadEventCalendar,
  loadTickerIntelligence,
  loadMacroDashboard,
  runScreener,
  pushNotification,
  reportError = (error) => console.error(error),
}) {
  async function migrateLegacyWorkspacePresets() {
    if (!isBrowser()) return false;
    const legacyPresets = readLegacyWorkspacePresets(window.localStorage);
    if (!legacyPresets.length) return false;

    let migratedCount = 0;
    for (const preset of legacyPresets.slice(0, 24)) {
      const trimmedName = String(preset?.name || "").trim();
      if (!trimmedName) continue;
      try {
        await dashboardApi.createWorkspace(toWorkspaceSaveRequest(trimmedName, preset));
        migratedCount += 1;
      } catch (error) {
        reportError(error);
      }
    }

    if (migratedCount > 0) {
      clearLegacyWorkspacePresets(window.localStorage);
    }
    return migratedCount > 0;
  }

  async function loadWorkspacePresets({ allowLegacyMigration = true, silent = true } = {}) {
    try {
      const response = await dashboardApi.listWorkspaces();
      const items = Array.isArray(response?.items)
        ? response.items.map((item) => normalizeWorkspaceRecord(item))
        : [];

      if (!items.length && allowLegacyMigration) {
        const migrated = await migrateLegacyWorkspacePresets();
        if (migrated) {
          return await loadWorkspacePresets({ allowLegacyMigration: false, silent });
        }
      }

      workspacePresets.value = items;
      if (
        activeWorkspacePresetId.value != null
        && !items.some((item) => sameWorkspaceId(item.id, activeWorkspacePresetId.value))
      ) {
        activeWorkspacePresetId.value = null;
      }
      return items;
    } catch (error) {
      reportError(error);
      workspacePresets.value = [];
      if (!silent) {
        pushNotification({
          icon: "⚠️",
          title: "工作區載入失敗",
          msg: "請稍後再試",
          type: "error",
        });
      }
      return [];
    }
  }

  function buildWorkspaceSnapshot(name) {
    return {
      name,
      savedAt: new Date().toISOString(),
      ...buildWorkspacePayload({
        currentTicker: currentTicker.value,
        currentName: currentName.value,
        currentPeriod: currentPeriod.value,
        currentInterval: currentInterval.value,
        klineDisplayMode: klineDisplayMode.value,
        chartEngineMode: chartEngineMode.value,
        cleanChartMode: cleanChartMode.value,
        chartLayout: chartLayout.value,
        compareTickers: compareTickers.value,
        comparisonMode: comparisonMode.value,
        activeTool: activeTool.value,
        leftTab: leftTab.value,
        rightTab: rightTab.value,
        workspaceTab: workspaceTab.value,
        screenerFilters,
        activeInd,
        activePanels,
        indicatorSettings,
        drawings: drawings.value,
      }),
    };
  }

  async function saveWorkspacePreset(name) {
    const trimmed = (name || "").trim();
    if (!trimmed) return;

    const existing = workspacePresets.value.find(
      (item) => item.name.toLowerCase() === trimmed.toLowerCase(),
    );
    const snapshot = buildWorkspaceSnapshot(trimmed);

    try {
      const persisted = existing
        ? await dashboardApi.updateWorkspace(
          existing.id,
          toWorkspaceSaveRequest(trimmed, snapshot),
        )
        : await dashboardApi.createWorkspace(toWorkspaceSaveRequest(trimmed, snapshot));
      const normalized = normalizeWorkspaceRecord(persisted);
      workspacePresets.value = existing
        ? workspacePresets.value.map((item) =>
          sameWorkspaceId(item.id, existing.id) ? normalized : item,
        )
        : [normalized, ...workspacePresets.value].slice(0, 24);
      activeWorkspacePresetId.value = normalized.id;
      pushNotification({
        icon: existing ? "↻" : "💾",
        title: existing ? "工作區已更新" : "工作區已儲存",
        msg: trimmed,
        type: "success",
      });
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "工作區儲存失敗",
        msg: error.message || "請稍後再試",
        type: "error",
      });
    }
  }

  async function loadWorkspacePreset(presetId) {
    let preset = workspacePresets.value.find((item) => sameWorkspaceId(item.id, presetId));
    if (!preset) {
      try {
        preset = normalizeWorkspaceRecord(await dashboardApi.getWorkspace(presetId));
      } catch (error) {
        pushNotification({
          icon: "⚠️",
          title: "工作區載入失敗",
          msg: error.message || "請稍後再試",
          type: "error",
        });
        return;
      }
    }

    const normalizedTicker = normalizeTicker(preset.currentTicker || currentTicker.value);
    clearRealtimeTicker(currentTicker.value);
    unsubscribeTicker(normalizeTicker(currentTicker.value));
    currentTicker.value = normalizedTicker;
    currentName.value = preset.currentName || normalizedTicker;
    const resolvedTimeframe = resolveDashboardTimeframeForTicker(
      normalizedTicker,
      preset.currentPeriod || currentPeriod.value,
      preset.currentInterval || currentInterval.value,
    );
    currentPeriod.value = resolvedTimeframe.period;
    currentInterval.value = resolvedTimeframe.interval;
    klineDisplayMode.value = getEffectiveKlineDisplayMode(
      preset.klineDisplayMode,
      currentInterval.value,
    );
    chartEngineMode.value = normalizeChartEngineMode(preset.chartEngineMode);
    cleanChartMode.value = Boolean(preset.cleanChartMode);
    chartLayout.value = chartLayoutOptions.includes(preset.chartLayout)
      ? preset.chartLayout
      : "single";
    comparisonMode.value = preset.comparisonMode === "price" ? "price" : "percent";
    activeTool.value = toolOptions.includes(preset.activeTool) ? preset.activeTool : "cursor";
    leftTab.value = preset.leftTab === "market" ? "market" : "watch";
    rightTab.value = normalizeDashboardRightTab(preset.rightTab);
    workspaceTab.value = workspaceTabOptions.includes(preset.workspaceTab)
      ? preset.workspaceTab
      : "chart";
    compareTickers.value = (preset.compareTickers || [])
      .map((ticker) => normalizeTicker(ticker))
      .filter((ticker) => ticker && ticker !== normalizedTicker);
    applyScreenerFilters(preset.screenerFilters || {});
    Object.keys(defaultActiveInd).forEach((key) => {
      activeInd[key] = preset.activeInd?.[key] ?? defaultActiveInd[key];
    });
    Object.keys(defaultActivePanels).forEach((key) => {
      activePanels[key] = preset.activePanels?.[key] ?? defaultActivePanels[key];
    });
    Object.assign(
      indicatorSettings,
      normalizeIndicatorSettings(preset.indicatorSettings || indicatorSettings),
    );
    drawings.value = (preset.drawings || []).map((drawing) => createDrawingEntry(drawing));
    selectedDrawingId.value = null;
    activeWorkspacePresetId.value = preset.id;
    rawOhlcData.value = [];
    crosshair.visible = false;
    rememberRecentTicker(normalizedTicker, preset.currentName || normalizedTicker);
    subscribeTicker(normalizedTicker);
    await ensureKline(
      normalizedTicker,
      currentPeriod.value,
      currentInterval.value,
      { force: true },
    );
    if (workspaceTab.value === "events") {
      await loadEventCalendar();
      await loadTickerIntelligence(normalizedTicker);
    } else if (workspaceTab.value === "macro") {
      await loadMacroDashboard();
    } else if (workspaceTab.value === "screener") {
      await runScreener();
    } else {
      void loadTickerIntelligence(normalizedTicker);
    }
    pushNotification({
      icon: "📂",
      title: "工作區已載入",
      msg: preset.name,
      type: "success",
    });
  }

  async function deleteWorkspacePreset(presetId) {
    const target = workspacePresets.value.find((item) => sameWorkspaceId(item.id, presetId));
    if (!target) return;
    try {
      await dashboardApi.deleteWorkspace(presetId);
      workspacePresets.value = workspacePresets.value.filter(
        (item) => !sameWorkspaceId(item.id, presetId),
      );
      if (sameWorkspaceId(activeWorkspacePresetId.value, presetId)) {
        activeWorkspacePresetId.value = null;
      }
      pushNotification({
        icon: "🗑",
        title: "工作區已刪除",
        msg: target.name,
        type: "success",
      });
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "工作區刪除失敗",
        msg: error.message || "請稍後再試",
        type: "error",
      });
    }
  }

  return {
    buildWorkspaceSnapshot,
    deleteWorkspacePreset,
    loadWorkspacePreset,
    loadWorkspacePresets,
    migrateLegacyWorkspacePresets,
    saveWorkspacePreset,
  };
}
