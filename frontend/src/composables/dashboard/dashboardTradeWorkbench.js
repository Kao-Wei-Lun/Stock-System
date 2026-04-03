import { computed, reactive, ref } from "vue";

export function createDashboardTradeWorkbench({
  dashboardApi,
  currentTicker,
  currentInterval,
  quote,
  rightTab,
  pushNotification,
  normalizeTicker,
  inferMarketFromTicker,
  getCurrentDateTimeInputValue,
  compareLimit = 3,
}) {
  const backtestResult = ref(null);
  const backtestHistory = ref([]);
  const backtestCompareIds = ref([]);
  const backtestCompareRuns = computed(() => {
    const idSet = new Set(backtestCompareIds.value.map((id) => String(id)));
    return backtestHistory.value.filter((item) => idSet.has(String(item.id))).slice(0, compareLimit);
  });
  const backtestLoading = ref(false);
  const journalEntries = ref([]);
  const journalStats = ref(null);
  const journalLoading = ref(false);
  const journalFilterPresets = ref([]);
  const journalFilterScope = ref("ticker");
  const journalFilters = reactive({
    market: "",
    strategy_code: "",
    tag: "",
    search: "",
  });
  const backtestForm = reactive({
    strategy: "MA 黃金/死亡交叉",
    start: "2022-01-01",
    end: new Date().toISOString().slice(0, 10),
    capital: 100000,
    positionSizing: "full_equity",
    fee: 0.1,
    slippage: 0,
    sl: 5,
    tp: 10,
  });
  const journalForm = reactive({
    id: null,
    ticker: "AAPL",
    market: inferMarketFromTicker("AAPL"),
    direction: "long",
    strategy_code: "",
    entry_time: getCurrentDateTimeInputValue(),
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
  });

  function mapBacktestRun(item) {
    if (!item) return null;
    return {
      ...item,
      id: item.id,
      strategy: item.strategy || item.strategy_name || item.strategyKey || item.strategy_key,
      strategy_key: item.strategy_key || item.strategyKey || "",
      start: item.start || item.start_date || "",
      end: item.end || item.end_date || "",
      capital: Number(item.capital ?? item.initial_capital ?? 0),
      finalEquity: Number(item.finalEquity ?? item.final_equity ?? 0),
      totalReturn: Number(item.totalReturn ?? item.total_return_pct ?? 0),
      sellTrades: Number(item.sellTrades ?? item.trade_count ?? 0),
      winRate: Number(item.winRate ?? item.win_rate_pct ?? 0),
      maxDrawdown: Number(item.maxDrawdown ?? item.max_drawdown_pct ?? 0),
      sharpe: Number(item.sharpe ?? item.sharpe_ratio ?? 0),
      bars: Number(item.bars ?? item.bars_count ?? 0),
      feeRate: Number(item.feeRate ?? item.fee_rate ?? 0),
      slippageRate: Number(item.slippageRate ?? item.slippage_rate ?? 0),
      positionSizing: String(item.positionSizing ?? item.position_sizing ?? "full_equity"),
      stopLoss: item.stopLoss ?? item.stop_loss_pct ?? null,
      takeProfit: item.takeProfit ?? item.take_profit_pct ?? null,
      trades: Array.isArray(item.trades) ? item.trades : [],
      equity_curve: Array.isArray(item.equity_curve) ? item.equity_curve : [],
      created_at: item.created_at || null,
    };
  }

  function applyBacktestRunToForm(record) {
    if (!record) return;
    backtestForm.strategy = record.strategy || backtestForm.strategy;
    backtestForm.start = record.start || backtestForm.start;
    backtestForm.end = record.end || backtestForm.end;
    backtestForm.capital = Number(record.capital ?? backtestForm.capital);
    backtestForm.positionSizing = String(record.positionSizing || "full_equity");
    backtestForm.fee = Number((((record.feeRate ?? 0) || 0) * 100).toFixed(4));
    backtestForm.slippage = Number((((record.slippageRate ?? 0) || 0) * 100).toFixed(4));
    backtestForm.sl = record.stopLoss == null ? 0 : Number((Number(record.stopLoss) * 100).toFixed(4));
    backtestForm.tp = record.takeProfit == null ? 0 : Number((Number(record.takeProfit) * 100).toFixed(4));
  }

  function mapJournalEntry(item) {
    if (!item) return null;
    return {
      ...item,
      id: item.id,
      ticker: normalizeTicker(item.ticker),
      tags: Array.isArray(item.tags) ? item.tags : [],
      attachments: Array.isArray(item.attachments) ? item.attachments : [],
      result: item.result || {},
    };
  }

  function applyJournalEntryToForm(entry = null) {
    const normalized = mapJournalEntry(entry);
    journalForm.id = normalized?.id ?? null;
    journalForm.ticker = normalized?.ticker || currentTicker.value;
    journalForm.market = normalized?.market || inferMarketFromTicker(normalized?.ticker || currentTicker.value);
    journalForm.direction = normalized?.direction || "long";
    journalForm.strategy_code = normalized?.strategy_code || "";
    journalForm.entry_time = normalized?.entry_time ? String(normalized.entry_time).slice(0, 16) : getCurrentDateTimeInputValue();
    journalForm.entry_price = normalized?.entry_price ?? quote.price ?? "";
    journalForm.exit_time = normalized?.exit_time ? String(normalized.exit_time).slice(0, 16) : "";
    journalForm.exit_price = normalized?.exit_price ?? "";
    journalForm.size = normalized?.size ?? 1;
    journalForm.stop_loss = normalized?.stop_loss ?? "";
    journalForm.take_profit = normalized?.take_profit ?? "";
    journalForm.entry_reason = normalized?.entry_reason || "";
    journalForm.exit_reason = normalized?.exit_reason || "";
    journalForm.emotion_tag = normalized?.emotion_tag || "";
    journalForm.review_notes = normalized?.review_notes || "";
    journalForm.tags_text = (normalized?.tags || []).join(", ");
    journalForm.attachment_path = "";
    journalForm.attachment_type = "";
    journalForm.attachments = Array.isArray(normalized?.attachments) ? [...normalized.attachments] : [];
  }

  function buildJournalQueryOptions() {
    return {
      ticker: journalFilterScope.value === "ticker" ? currentTicker.value : undefined,
      market: journalFilters.market || undefined,
      strategy_code: journalFilters.strategy_code || undefined,
      tag: journalFilters.tag || undefined,
      search: journalFilters.search || undefined,
      limit: 50,
    };
  }

  async function loadBacktestHistory({ ticker = currentTicker.value, silent = true } = {}) {
    try {
      const response = await dashboardApi.listBacktestRuns({ ticker, limit: 20 });
      backtestHistory.value = Array.isArray(response?.items)
        ? response.items.map((item) => mapBacktestRun(item)).filter(Boolean)
        : [];
      const validIds = new Set(backtestHistory.value.map((item) => String(item.id)));
      backtestCompareIds.value = backtestCompareIds.value.filter((id) => validIds.has(String(id)));
    } catch (error) {
      console.error(error);
      if (!silent) {
        pushNotification({ icon: "⚠️", title: "回測紀錄載入失敗", msg: "請稍後再試", type: "error" });
      }
    }
  }

  async function selectBacktestRun(runId) {
    if (!runId) return;
    backtestLoading.value = true;
    try {
      const record = await dashboardApi.getBacktestRun(runId);
      backtestResult.value = mapBacktestRun(record);
      applyBacktestRunToForm(backtestResult.value);
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "回測紀錄讀取失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      backtestLoading.value = false;
    }
  }

  function toggleBacktestCompare(runId) {
    if (runId == null) return;
    const targetId = String(runId);
    if (backtestCompareIds.value.some((id) => String(id) === targetId)) {
      backtestCompareIds.value = backtestCompareIds.value.filter((id) => String(id) !== targetId);
      return;
    }
    backtestCompareIds.value = [...backtestCompareIds.value.slice(-(compareLimit - 1)), runId];
  }

  function clearBacktestCompare() {
    backtestCompareIds.value = [];
  }

  async function loadJournalData({ silent = true } = {}) {
    journalLoading.value = !silent;
    try {
      const options = buildJournalQueryOptions();
      const [entriesResponse, statsResponse] = await Promise.all([
        dashboardApi.listJournalTrades(options),
        dashboardApi.getJournalTradeStats(options),
      ]);
      journalEntries.value = Array.isArray(entriesResponse?.items)
        ? entriesResponse.items.map((item) => mapJournalEntry(item)).filter(Boolean)
        : [];
      journalStats.value = statsResponse || null;
    } catch (error) {
      console.error(error);
      if (!silent) {
        pushNotification({ icon: "⚠️", title: "交易日誌載入失敗", msg: "請稍後再試", type: "error" });
      }
    } finally {
      journalLoading.value = false;
    }
  }

  async function loadJournalFilterPresets() {
    try {
      const response = await dashboardApi.listJournalFilterPresets();
      journalFilterPresets.value = Array.isArray(response?.items) ? response.items : [];
    } catch (error) {
      console.error(error);
      journalFilterPresets.value = [];
    }
  }

  function updateJournalField(key, value) {
    journalForm[key] = ["entry_price", "exit_price", "size", "stop_loss", "take_profit"].includes(key)
      ? (value === "" ? "" : Number(value))
      : value;
    if (key === "ticker" && value) {
      journalForm.market = inferMarketFromTicker(value);
    }
  }

  async function updateJournalFilter(key, value) {
    if (key === "scope") {
      journalFilterScope.value = value === "all" ? "all" : "ticker";
    } else if (Object.prototype.hasOwnProperty.call(journalFilters, key)) {
      journalFilters[key] = value;
    }
    await loadJournalData();
  }

  function buildJournalFilterPresetPayload() {
    return {
      scope: journalFilterScope.value === "all" ? "all" : "ticker",
      filters: {
        market: journalFilters.market || "",
        strategy_code: journalFilters.strategy_code || "",
        tag: journalFilters.tag || "",
        search: journalFilters.search || "",
      },
    };
  }

  function normalizeJournalFilterPresetDraft(input) {
    if (input && typeof input === "object" && !Array.isArray(input)) {
      const filters = input.filters && typeof input.filters === "object" ? input.filters : {};
      return {
        id: input.id ?? null,
        name: String(input.name || "").trim(),
        description: input.description || "由交易日誌工作區儲存",
        scope: input.scope === "all" ? "all" : "ticker",
        filters: {
          market: filters.market || "",
          strategy_code: filters.strategy_code || "",
          tag: filters.tag || "",
          search: filters.search || "",
        },
      };
    }

    const name = String(input || "").trim();
    return {
      id: null,
      name,
      description: "由交易日誌工作區儲存",
      ...buildJournalFilterPresetPayload(),
    };
  }

  async function applyJournalFilterPreset(preset = {}) {
    const source = preset && typeof preset === "object" ? preset : {};
    const filters = source.filters && typeof source.filters === "object" ? source.filters : source;
    if (Object.prototype.hasOwnProperty.call(source, "scope")) {
      journalFilterScope.value = source.scope === "all" ? "all" : "ticker";
    }
    for (const key of ["market", "strategy_code", "tag", "search"]) {
      if (Object.prototype.hasOwnProperty.call(filters, key)) {
        journalFilters[key] = filters[key] || "";
      }
    }
    await loadJournalData();
  }

  async function saveJournalFilterPreset(name) {
    const draft = normalizeJournalFilterPresetDraft(name);
    if (!draft.name) return;
    try {
      const existing = draft.id
        ? journalFilterPresets.value.find((item) => String(item?.id) === String(draft.id))
        : journalFilterPresets.value.find((item) => String(item?.name || "").trim() === draft.name);
      if (existing?.id || draft.id) {
        await dashboardApi.updateJournalFilterPreset(draft.id || existing.id, {
          name: draft.name,
          description: draft.description,
          scope: draft.scope,
          filters: draft.filters,
        });
      } else {
        await dashboardApi.createJournalFilterPreset({
          name: draft.name,
          description: draft.description,
          scope: draft.scope,
          filters: draft.filters,
        });
      }
      await loadJournalFilterPresets();
      pushNotification({
        icon: existing?.id || draft.id ? "↩️" : "💾",
        title: existing?.id || draft.id ? "日誌篩選模板已更新" : "日誌篩選模板已儲存",
        msg: draft.name,
        type: "success",
      });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "日誌篩選模板儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function loadJournalFilterPreset(preset) {
    if (!preset) return;
    let nextPreset = preset;
    if (preset.id) {
      try {
        const updated = await dashboardApi.markJournalFilterPresetUsed(preset.id);
        if (updated) {
          nextPreset = updated;
          journalFilterPresets.value = journalFilterPresets.value.map((item) =>
            String(item?.id) === String(updated.id) ? updated : item,
          );
        }
      } catch (error) {
        console.error(error);
      }
    }
    await applyJournalFilterPreset(nextPreset);
    pushNotification({ icon: "🧭", title: "已載入日誌篩選模板", msg: preset.name || "preset", type: "success" });
  }

  async function deleteJournalFilterPreset(presetId) {
    if (!presetId) return;
    try {
      await dashboardApi.deleteJournalFilterPreset(presetId);
      await loadJournalFilterPresets();
      pushNotification({ icon: "🗑", title: "日誌篩選模板已刪除", msg: String(presetId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "日誌篩選模板刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  function resetJournalForm() {
    applyJournalEntryToForm({
      ticker: currentTicker.value,
      market: inferMarketFromTicker(currentTicker.value),
      entry_price: quote.price ?? "",
      size: 1,
    });
  }

  function addJournalAttachment() {
    if (!journalForm.attachment_path) return;
    journalForm.attachments = [
      ...journalForm.attachments,
      {
        file_path: journalForm.attachment_path,
        file_type: journalForm.attachment_type || null,
      },
    ];
    journalForm.attachment_path = "";
    journalForm.attachment_type = "";
  }

  function removeJournalAttachment(index) {
    journalForm.attachments = journalForm.attachments.filter((_, itemIndex) => itemIndex !== index);
  }

  function startJournalEntry(seed = {}) {
    rightTab.value = "journal";
    applyJournalEntryToForm({
      ticker: seed.ticker || currentTicker.value,
      market: seed.market || inferMarketFromTicker(seed.ticker || currentTicker.value),
      entry_price: seed.entry_price ?? quote.price ?? "",
      strategy_code: seed.strategy_code || backtestResult.value?.strategy_key || "",
      entry_reason: seed.entry_reason || "",
      review_notes: seed.review_notes || "",
      tags: Array.isArray(seed.tags) ? seed.tags : [],
      size: 1,
    });
    void loadJournalData();
  }

  async function selectJournalEntry(entryId) {
    if (!entryId) return;
    journalLoading.value = true;
    try {
      const entry = await dashboardApi.getJournalTrade(entryId);
      applyJournalEntryToForm(entry);
      rightTab.value = "journal";
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易紀錄讀取失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      journalLoading.value = false;
    }
  }

  async function saveJournalEntry() {
    journalLoading.value = true;
    try {
      const isEditing = Boolean(journalForm.id);
      const payload = {
        ticker: normalizeTicker(journalForm.ticker),
        market: journalForm.market || inferMarketFromTicker(journalForm.ticker),
        direction: journalForm.direction,
        strategy_code: journalForm.strategy_code || null,
        entry_time: journalForm.entry_time,
        entry_price: Number(journalForm.entry_price),
        exit_time: journalForm.exit_time || null,
        exit_price: journalForm.exit_price === "" ? null : Number(journalForm.exit_price),
        size: Number(journalForm.size),
        stop_loss: journalForm.stop_loss === "" ? null : Number(journalForm.stop_loss),
        take_profit: journalForm.take_profit === "" ? null : Number(journalForm.take_profit),
        entry_reason: journalForm.entry_reason || null,
        exit_reason: journalForm.exit_reason || null,
        emotion_tag: journalForm.emotion_tag || null,
        review_notes: journalForm.review_notes || null,
        tags: journalForm.tags_text
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        attachments: journalForm.attachments.map((item) => ({
          file_path: item.file_path,
          file_type: item.file_type || null,
        })),
      };
      const record = journalForm.id
        ? await dashboardApi.updateJournalTrade(journalForm.id, payload)
        : await dashboardApi.createJournalTrade(payload);
      applyJournalEntryToForm(record);
      await loadJournalData();
      pushNotification({
        icon: "📝",
        title: isEditing ? "交易日誌已更新" : "交易日誌已建立",
        msg: `${record.ticker} · ${record.direction}`,
        type: "success",
      });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易日誌儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      journalLoading.value = false;
    }
  }

  async function deleteJournalEntry(entryId = journalForm.id) {
    if (!entryId) return;
    journalLoading.value = true;
    try {
      await dashboardApi.deleteJournalTrade(entryId);
      if (journalForm.id === entryId) {
        resetJournalForm();
      }
      await loadJournalData();
      pushNotification({ icon: "🗑", title: "交易紀錄已刪除", msg: String(entryId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易紀錄刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      journalLoading.value = false;
    }
  }

  function updateBacktestField(key, value) {
    backtestForm[key] = ["capital", "fee", "slippage", "sl", "tp"].includes(key) ? Number(value) : value;
  }

  async function runBacktest() {
    backtestLoading.value = true;
    try {
      const result = await dashboardApi.createBacktestRun({
        ticker: currentTicker.value,
        strategy: backtestForm.strategy,
        start: backtestForm.start,
        end: backtestForm.end,
        interval: currentInterval.value,
        capital: Number(backtestForm.capital),
        position_sizing: backtestForm.positionSizing,
        fee: Number(backtestForm.fee),
        slippage: Number(backtestForm.slippage),
        sl: Number(backtestForm.sl),
        tp: Number(backtestForm.tp),
      });
      backtestResult.value = mapBacktestRun(result);
      await loadBacktestHistory({ ticker: currentTicker.value });
      pushNotification({
        icon: "📊",
        title: "回測完成",
        msg: `${backtestResult.value.strategy} — ${backtestResult.value.totalReturn >= 0 ? "+" : ""}${backtestResult.value.totalReturn.toFixed(2)}%`,
        type: "success",
      });
    } catch (error) {
      backtestResult.value = null;
      pushNotification({ icon: "⚠️", title: "回測失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      backtestLoading.value = false;
    }
  }

  return {
    backtestForm,
    backtestResult,
    backtestHistory,
    backtestCompareIds,
    backtestCompareRuns,
    backtestLoading,
    journalForm,
    journalEntries,
    journalStats,
    journalLoading,
    journalFilterPresets,
    journalFilterScope,
    journalFilters,
    loadBacktestHistory,
    selectBacktestRun,
    toggleBacktestCompare,
    clearBacktestCompare,
    loadJournalData,
    loadJournalFilterPresets,
    updateJournalField,
    updateJournalFilter,
    applyJournalFilterPreset,
    saveJournalFilterPreset,
    loadJournalFilterPreset,
    deleteJournalFilterPreset,
    resetJournalForm,
    addJournalAttachment,
    removeJournalAttachment,
    startJournalEntry,
    selectJournalEntry,
    saveJournalEntry,
    deleteJournalEntry,
    updateBacktestField,
    runBacktest,
  };
}
