import { reactive, ref } from "vue";

export function createDashboardScreener({
  storedPrefs,
  dashboardApi,
  pushNotification,
} = {}) {
  const screenerResults = ref({ items: [], total: 0, filters: {}, market_context: null, generated_at: null });
  const screenerPresets = ref([]);
  const screenerLoading = ref(false);
  const screenerFilters = reactive({
    search: "",
    market: "ALL",
    sector: "",
    setup_type: "any",
    min_price: "",
    max_price: "",
    min_volume_ratio: "",
    min_setup_quality: "",
    min_accumulation_score: "",
    decision_verdict: "any",
    max_pe_ratio: "",
    min_dividend_yield: "",
    near_52w_high_pct: "",
    upcoming_event_days: "",
    chip_bias: "any",
    ma_alignment: "any",
    sort_by: "score",
    limit: 50,
    ...(storedPrefs?.screenerFilters || {}),
  });

  function buildScreenerPayload() {
    const payload = {};
    Object.entries(screenerFilters).forEach(([key, value]) => {
      if (value === "" || value == null) return;
      if (["min_price", "max_price", "min_volume_ratio", "min_setup_quality", "min_accumulation_score", "max_pe_ratio", "min_dividend_yield", "near_52w_high_pct", "upcoming_event_days", "limit"].includes(key)) {
        payload[key] = Number(value);
        return;
      }
      payload[key] = value;
    });
    return payload;
  }

  function applyScreenerFilters(filters = {}) {
    Object.keys(screenerFilters).forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(filters, key)) {
        screenerFilters[key] = filters[key] ?? "";
      }
    });
  }

  function updateScreenerFilter(key, value) {
    if (!Object.prototype.hasOwnProperty.call(screenerFilters, key)) return;
    screenerFilters[key] = value;
  }

  async function loadScreenerPresets() {
    try {
      const response = await dashboardApi.listScreenerPresets();
      screenerPresets.value = Array.isArray(response?.items) ? response.items : [];
    } catch (error) {
      console.error(error);
      screenerPresets.value = [];
    }
  }

  async function runScreener() {
    screenerLoading.value = true;
    try {
      const payload = await dashboardApi.runScreener({ filters: buildScreenerPayload() });
      screenerResults.value = payload || { items: [], total: 0, filters: {}, market_context: null, generated_at: null };
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "選股器執行失敗", msg: error.message || "請稍後再試", type: "error" });
    } finally {
      screenerLoading.value = false;
    }
  }

  async function saveScreenerPreset(name) {
    const trimmed = String(name || "").trim();
    if (!trimmed) return;
    try {
      await dashboardApi.createScreenerPreset({
        name: trimmed,
        description: "由選股器工作區儲存",
        filters: buildScreenerPayload(),
      });
      await loadScreenerPresets();
      pushNotification({ icon: "💾", title: "選股模板已儲存", msg: trimmed, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "選股模板儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  function loadScreenerPreset(preset) {
    if (!preset?.filters) return;
    applyScreenerFilters(preset.filters);
    pushNotification({ icon: "🧭", title: "已載入選股模板", msg: preset.name || "preset", type: "success" });
    void runScreener();
  }

  async function deleteScreenerPreset(presetId) {
    if (!presetId || String(presetId).startsWith("builtin-")) return;
    try {
      await dashboardApi.deleteScreenerPreset(presetId);
      await loadScreenerPresets();
      pushNotification({ icon: "🗑", title: "選股模板已刪除", msg: String(presetId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "選股模板刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  return {
    screenerResults,
    screenerPresets,
    screenerLoading,
    screenerFilters,
    applyScreenerFilters,
    updateScreenerFilter,
    loadScreenerPresets,
    runScreener,
    saveScreenerPreset,
    loadScreenerPreset,
    deleteScreenerPreset,
  };
}
