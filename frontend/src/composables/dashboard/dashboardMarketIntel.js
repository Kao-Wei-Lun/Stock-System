import { computed, ref } from "vue";

export const INSTITUTIONAL_HISTORY_OPTIONS = [10, 20, 30, 60, 90];
const TAIFEX_STRUCTURED_SECTIONS = new Set(["meta", "overview", "futures", "options", "call_puts", "cash_summary"]);
const TAIFEX_STRUCTURED_COMMODITY_SECTIONS = new Set(["futures", "options", "call_puts"]);
const TAIFEX_STRUCTURED_OPTION_SIDE_SECTIONS = new Set(["call_puts"]);
const TAIFEX_STRUCTURED_LIMITS = {
  meta: 120,
  overview: 200,
  futures: 300,
  options: 300,
  call_puts: 300,
  cash_summary: 200,
};

const FUTURES_OVERLAY_TICKER_MAP = {
  "^TWII": "台股期貨",
  "0050.TW": "台股期貨",
  "^TWOII": "櫃買指數期貨",
};

const FUTURES_DEFAULT_SPOT_TICKER_MAP = {
  "台股期貨": "^TWII",
  "小型台指期貨": "^TWII",
  "微型台指期貨": "^TWII",
  "臺灣永續期貨": "^TWII",
  "臺灣生技期貨": "^TWII",
  "櫃買指數期貨": "^TWOII",
};

function normalizeMacroDashboard(payload) {
  return {
    items: Array.isArray(payload?.items) ? payload.items : [],
    summary: payload?.summary || {},
    snapshot_date: payload?.snapshot_date || null,
  };
}

function formatIsoDate(value) {
  if (!value) return "";
  const date = value instanceof Date ? new Date(value.getTime()) : new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function shiftIsoDate(value, days) {
  const base = formatIsoDate(value);
  if (!base) return "";
  const date = new Date(`${base}T00:00:00`);
  date.setDate(date.getDate() + Number(days || 0));
  return formatIsoDate(date);
}

function normalizeTaifexStructuredSection(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return TAIFEX_STRUCTURED_SECTIONS.has(normalized) ? normalized : "futures";
}

function clampTaifexStructuredLimit(section, value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return TAIFEX_STRUCTURED_LIMITS[normalizeTaifexStructuredSection(section)];
  }
  return Math.max(1, Math.min(1000, Math.round(numeric)));
}

function resolveTaifexStructuredCommodity(section, futuresCommodity, optionsCommodity) {
  const normalizedSection = normalizeTaifexStructuredSection(section);
  if (normalizedSection === "futures") return String(futuresCommodity || "").trim();
  if (normalizedSection === "options" || normalizedSection === "call_puts") {
    return String(optionsCommodity || "").trim();
  }
  return "";
}

export function createDashboardMarketIntel({
  storedPrefs,
  currentTicker,
  dashboardApi,
  apiFetch,
  pushNotification,
  normalizeTicker,
  isFutoptTicker,
} = {}) {
  const calendarEvents = ref([]);
  const tickerEvents = ref([]);
  const tickerNews = ref([]);
  const macroDashboard = ref({ items: [], summary: {}, snapshot_date: null });
  const fundamentalsDetail = ref(null);
  const fundamentalsSummary = ref(null);
  const taiwanChipDetail = ref(null);
  const taiwanChipSummary = ref(null);

  const initialInstitutionalHistoryDays = INSTITUTIONAL_HISTORY_OPTIONS.includes(Number(storedPrefs?.institutionalHistoryDays))
    ? Number(storedPrefs.institutionalHistoryDays)
    : 30;

  const institutionalDate = ref(new Date().toISOString().slice(0, 10));
  const institutionalData = ref(null);
  const institutionalLoading = ref(false);
  const institutionalError = ref("");
  const institutionalInsights = ref(null);
  const institutionalInsightsLoading = ref(false);
  const institutionalInsightsError = ref("");
  const institutionalFuturesCommodity = ref(storedPrefs?.institutionalFuturesCommodity || "");
  const institutionalOptionsCommodity = ref(storedPrefs?.institutionalOptionsCommodity || "");
  const institutionalHistoryDays = ref(initialInstitutionalHistoryDays);
  const taifexStructuredSection = ref("futures");
  const taifexStructuredDateMode = ref("range");
  const taifexStructuredExactDate = ref("");
  const taifexStructuredStartDate = ref("");
  const taifexStructuredEndDate = ref("");
  const taifexStructuredCommodity = ref("");
  const taifexStructuredInstitution = ref("");
  const taifexStructuredOptionSide = ref("");
  const taifexStructuredLimit = ref(TAIFEX_STRUCTURED_LIMITS.futures);
  const taifexStructuredAutoSync = ref(true);
  const taifexStructuredData = ref({
    section: "futures",
    count: 0,
    filters: {},
    items: [],
  });
  const taifexStructuredLoading = ref(false);
  const taifexStructuredError = ref("");

  function syncTaifexStructuredDefaults(
    dateValue = institutionalDate.value,
    futuresCommodity = institutionalFuturesCommodity.value,
    optionsCommodity = institutionalOptionsCommodity.value,
    force = false,
  ) {
    if (!force && !taifexStructuredAutoSync.value) return;
    const section = normalizeTaifexStructuredSection(taifexStructuredSection.value);
    const endDate = formatIsoDate(dateValue) || formatIsoDate(new Date());
    taifexStructuredSection.value = section;
    taifexStructuredDateMode.value = "range";
    taifexStructuredExactDate.value = endDate;
    taifexStructuredStartDate.value = shiftIsoDate(endDate, -30) || endDate;
    taifexStructuredEndDate.value = endDate;
    taifexStructuredCommodity.value = resolveTaifexStructuredCommodity(section, futuresCommodity, optionsCommodity);
    taifexStructuredInstitution.value = "";
    taifexStructuredOptionSide.value = TAIFEX_STRUCTURED_OPTION_SIDE_SECTIONS.has(section)
      ? String(taifexStructuredOptionSide.value || "").trim()
      : "";
    taifexStructuredLimit.value = TAIFEX_STRUCTURED_LIMITS[section];
    taifexStructuredAutoSync.value = true;
  }

  async function loadTaifexStructuredData() {
    const section = normalizeTaifexStructuredSection(taifexStructuredSection.value);
    const query = {
      limit: clampTaifexStructuredLimit(section, taifexStructuredLimit.value),
    };

    if (taifexStructuredDateMode.value === "date") {
      query.date = formatIsoDate(taifexStructuredExactDate.value) || formatIsoDate(institutionalDate.value);
    } else {
      query.start_date = formatIsoDate(taifexStructuredStartDate.value) || shiftIsoDate(institutionalDate.value, -30);
      query.end_date = formatIsoDate(taifexStructuredEndDate.value) || formatIsoDate(institutionalDate.value);
    }

    if (TAIFEX_STRUCTURED_COMMODITY_SECTIONS.has(section) && taifexStructuredCommodity.value) {
      query.commodity = String(taifexStructuredCommodity.value).trim();
    }
    if (taifexStructuredInstitution.value) {
      query.institution = String(taifexStructuredInstitution.value).trim();
    }
    if (TAIFEX_STRUCTURED_OPTION_SIDE_SECTIONS.has(section) && taifexStructuredOptionSide.value) {
      query.option_side = String(taifexStructuredOptionSide.value).trim();
    }

    taifexStructuredLoading.value = true;
    taifexStructuredError.value = "";
    try {
      const payload = await dashboardApi.getTaifexStructured(section, query);
      taifexStructuredData.value = {
        section,
        count: Number(payload?.count || 0),
        filters: payload?.filters || query,
        items: Array.isArray(payload?.items) ? payload.items : [],
      };
    } catch (error) {
      taifexStructuredError.value = error.message || "ç„¡æ³•å–å¾— TAIFEX çµæ§‹åŒ–è³‡æ–™";
    } finally {
      taifexStructuredLoading.value = false;
    }
  }

  function updateTaifexStructuredQuery(patch = {}) {
    const nextPatch = patch && typeof patch === "object" ? patch : {};
    const hasManualKeys = Object.keys(nextPatch).some((key) => key !== "autoSync");

    if (nextPatch.section != null) {
      const nextSection = normalizeTaifexStructuredSection(nextPatch.section);
      taifexStructuredSection.value = nextSection;
      if (!TAIFEX_STRUCTURED_COMMODITY_SECTIONS.has(nextSection)) {
        taifexStructuredCommodity.value = "";
      } else if (!Object.prototype.hasOwnProperty.call(nextPatch, "commodity") && taifexStructuredAutoSync.value) {
        taifexStructuredCommodity.value = resolveTaifexStructuredCommodity(
          nextSection,
          institutionalFuturesCommodity.value,
          institutionalOptionsCommodity.value,
        );
      }
      if (!TAIFEX_STRUCTURED_OPTION_SIDE_SECTIONS.has(nextSection)) {
        taifexStructuredOptionSide.value = "";
      }
      if (!Object.prototype.hasOwnProperty.call(nextPatch, "limit")) {
        taifexStructuredLimit.value = TAIFEX_STRUCTURED_LIMITS[nextSection];
      }
    }
    if (nextPatch.dateMode != null) {
      taifexStructuredDateMode.value = String(nextPatch.dateMode) === "date" ? "date" : "range";
    }
    if (nextPatch.exactDate != null) taifexStructuredExactDate.value = formatIsoDate(nextPatch.exactDate);
    if (nextPatch.startDate != null) taifexStructuredStartDate.value = formatIsoDate(nextPatch.startDate);
    if (nextPatch.endDate != null) taifexStructuredEndDate.value = formatIsoDate(nextPatch.endDate);
    if (nextPatch.commodity != null) taifexStructuredCommodity.value = String(nextPatch.commodity || "").trim();
    if (nextPatch.institution != null) taifexStructuredInstitution.value = String(nextPatch.institution || "").trim();
    if (nextPatch.optionSide != null) taifexStructuredOptionSide.value = String(nextPatch.optionSide || "").trim();
    if (nextPatch.limit != null) {
      taifexStructuredLimit.value = clampTaifexStructuredLimit(taifexStructuredSection.value, nextPatch.limit);
    }
    if (typeof nextPatch.autoSync === "boolean") {
      taifexStructuredAutoSync.value = nextPatch.autoSync;
    } else if (hasManualKeys) {
      taifexStructuredAutoSync.value = false;
    }
  }

  async function resetTaifexStructuredQuery() {
    syncTaifexStructuredDefaults(
      institutionalDate.value,
      institutionalFuturesCommodity.value,
      institutionalOptionsCommodity.value,
      true,
    );
    await loadTaifexStructuredData();
  }

  const institutionalOverlay = computed(() => {
    const mappedCommodity = FUTURES_OVERLAY_TICKER_MAP[currentTicker.value];
    if (!mappedCommodity) return null;

    const insightMatch = institutionalInsights.value?.futures_commodity === mappedCommodity
      ? institutionalInsights.value
      : null;
    const dataMatch = institutionalData.value?.default_futures_commodity === mappedCommodity
      ? institutionalData.value
      : null;
    const futuresCosts = insightMatch?.cost_estimates?.futures || dataMatch?.cost_estimates?.futures || null;
    if (!futuresCosts) return null;

    const bandLow = futuresCosts.band_low == null ? Number.NaN : Number(futuresCosts.band_low);
    const bandHigh = futuresCosts.band_high == null ? Number.NaN : Number(futuresCosts.band_high);
    const institutionPrice = futuresCosts.institution_estimate?.price == null
      ? Number.NaN
      : Number(futuresCosts.institution_estimate.price);
    const retailPrice = futuresCosts.retail_estimate?.price == null
      ? Number.NaN
      : Number(futuresCosts.retail_estimate.price);
    const values = [bandLow, bandHigh, institutionPrice, retailPrice].filter((value) => Number.isFinite(value));
    if (!values.length) return null;

    const spotTicker = FUTURES_DEFAULT_SPOT_TICKER_MAP[mappedCommodity];
    const spot = (institutionalData.value?.spot_reference || []).find((item) => item.ticker === spotTicker) || null;
    const spotPrice = spot?.price == null ? Number.NaN : Number(spot.price);
    const basis = Number.isFinite(spotPrice) && Number.isFinite(institutionPrice)
      ? institutionPrice - spotPrice
      : null;

    return {
      commodity: mappedCommodity,
      label: `${mappedCommodity} 主力成本帶`,
      bandLow: Number.isFinite(bandLow) ? bandLow : null,
      bandHigh: Number.isFinite(bandHigh) ? bandHigh : null,
      institutionPrice: Number.isFinite(institutionPrice) ? institutionPrice : null,
      retailPrice: Number.isFinite(retailPrice) ? retailPrice : null,
      spotTicker: spot?.ticker || null,
      spotLabel: spot?.label || null,
      spotPrice: Number.isFinite(spotPrice) ? spotPrice : null,
      basis,
      basisPct: Number.isFinite(basis) && spotPrice ? (basis / spotPrice) * 100 : null,
      resolvedDate: insightMatch?.resolved_date || dataMatch?.resolved_date || null,
    };
  });

  async function loadEventCalendar(forceRefresh = false) {
    try {
      const response = await dashboardApi.listEventCalendar({ days: 30, limit: 120, refresh: forceRefresh });
      calendarEvents.value = Array.isArray(response?.items) ? response.items : [];
    } catch (error) {
      console.error(error);
      if (forceRefresh) {
        pushNotification({ icon: "⚠️", title: "事件日曆載入失敗", msg: error.message || "請稍後再試", type: "error" });
      }
    }
  }

  async function loadMacroDashboard(forceRefresh = false) {
    try {
      const response = await dashboardApi.getMacroDashboard({ refresh: forceRefresh });
      macroDashboard.value = normalizeMacroDashboard(response);
    } catch (error) {
      console.error(error);
      if (forceRefresh) {
        pushNotification({ icon: "⚠️", title: "宏觀儀表板載入失敗", msg: error.message || "請稍後再試", type: "error" });
      }
    }
  }

  async function loadTickerIntelligence(ticker = currentTicker.value, forceRefresh = false) {
    const normalizedTicker = normalizeTicker(ticker);
    try {
      const futoptTicker = typeof isFutoptTicker === "function" && isFutoptTicker(normalizedTicker);
      const [eventsResponse, newsResponse, fundamentalsResponse, chipsResponse] = futoptTicker
        ? await Promise.all([
          dashboardApi.getTickerEvents(normalizedTicker, { refresh: forceRefresh }),
          dashboardApi.getTickerNews(normalizedTicker, { limit: 10, refresh: forceRefresh }),
        ])
        : await Promise.all([
          dashboardApi.getTickerEvents(normalizedTicker, { refresh: forceRefresh }),
          dashboardApi.getTickerNews(normalizedTicker, { limit: 10, refresh: forceRefresh }),
          dashboardApi.getFundamentals(normalizedTicker, { refresh: forceRefresh }),
          dashboardApi.getTaiwanChips(normalizedTicker, { refresh: forceRefresh }).catch(() => null),
        ]);
      tickerEvents.value = Array.isArray(eventsResponse?.items) ? eventsResponse.items : [];
      tickerNews.value = Array.isArray(newsResponse?.items) ? newsResponse.items : [];
      fundamentalsDetail.value = futoptTicker ? null : (fundamentalsResponse?.detail || null);
      fundamentalsSummary.value = futoptTicker ? null : (fundamentalsResponse?.summary || null);
      taiwanChipDetail.value = futoptTicker ? null : (chipsResponse?.detail || null);
      taiwanChipSummary.value = futoptTicker ? null : (chipsResponse?.summary || null);
    } catch (error) {
      console.error(error);
      if (forceRefresh) {
        pushNotification({ icon: "⚠️", title: "標的資訊載入失敗", msg: error.message || "請稍後再試", type: "error" });
      }
    }
  }

  async function loadInstitutionalInsights(
    dateValue = institutionalDate.value,
    futuresCommodity = institutionalFuturesCommodity.value,
    optionsCommodity = institutionalOptionsCommodity.value,
    days = institutionalHistoryDays.value,
    forceRefresh = false,
  ) {
    if (!futuresCommodity && !optionsCommodity) return;
    institutionalInsightsLoading.value = true;
    institutionalInsightsError.value = "";
    try {
      const params = new URLSearchParams({
        date: dateValue,
        days: String(days),
      });
      if (futuresCommodity) params.set("futures_commodity", futuresCommodity);
      if (optionsCommodity) params.set("options_commodity", optionsCommodity);
      if (forceRefresh) params.set("refresh", "1");
      const payload = await apiFetch(`/api/taifex/institutional/insights?${params.toString()}`, {
        retries: 2,
        retryDelayMs: 1200,
      });
      institutionalInsights.value = payload;
    } catch (error) {
      institutionalInsightsError.value = error.message || "無法取得法人歷史趨勢";
    } finally {
      institutionalInsightsLoading.value = false;
    }
  }

  async function loadInstitutionalData(dateValue = institutionalDate.value, forceRefresh = false) {
    institutionalLoading.value = true;
    institutionalError.value = "";
    institutionalInsightsError.value = "";
    try {
      const params = new URLSearchParams({ date: dateValue });
      if (forceRefresh) params.set("refresh", "1");
      const payload = await apiFetch(`/api/taifex/institutional?${params.toString()}`, {
        retries: 3,
        retryDelayMs: 1200,
      });
      institutionalDate.value = dateValue;
      institutionalData.value = payload;
      const nextFuturesCommodity = (payload?.futures_commodities || []).includes(institutionalFuturesCommodity.value)
        ? institutionalFuturesCommodity.value
        : (payload?.default_futures_commodity || payload?.futures_commodities?.[0] || "");
      const nextOptionsCommodity = (payload?.options_commodities || []).includes(institutionalOptionsCommodity.value)
        ? institutionalOptionsCommodity.value
        : (payload?.default_options_commodity || payload?.options_commodities?.[0] || "");
      institutionalFuturesCommodity.value = nextFuturesCommodity;
      institutionalOptionsCommodity.value = nextOptionsCommodity;
      if (taifexStructuredAutoSync.value || !(taifexStructuredData.value?.items || []).length) {
        syncTaifexStructuredDefaults(dateValue, nextFuturesCommodity, nextOptionsCommodity, true);
        await loadTaifexStructuredData();
      }
      await loadInstitutionalInsights(
        dateValue,
        nextFuturesCommodity,
        nextOptionsCommodity,
        institutionalHistoryDays.value,
        forceRefresh,
      );
    } catch (error) {
      institutionalError.value = error.message || "無法取得期權法人資料";
    } finally {
      institutionalLoading.value = false;
    }
  }

  async function ensureInstitutionalOverlayForTicker(ticker = currentTicker.value) {
    const normalizedTicker = normalizeTicker(ticker);
    const mappedCommodity = FUTURES_OVERLAY_TICKER_MAP[normalizedTicker];
    if (!mappedCommodity) return;

    if (!institutionalData.value && !institutionalLoading.value) {
      await loadInstitutionalData(institutionalDate.value);
    }

    const hasMatchingInsights = institutionalInsights.value?.futures_commodity === mappedCommodity;
    const hasMatchingDefault = institutionalData.value?.default_futures_commodity === mappedCommodity;
    if (hasMatchingInsights || hasMatchingDefault || institutionalInsightsLoading.value) return;

    institutionalFuturesCommodity.value = mappedCommodity;
    await loadInstitutionalInsights(
      institutionalDate.value,
      mappedCommodity,
      institutionalOptionsCommodity.value || institutionalData.value?.default_options_commodity || "",
      institutionalHistoryDays.value,
    );
  }

  async function setInstitutionalDate(value) {
    if (!value) return;
    await loadInstitutionalData(value);
  }

  async function setInstitutionalFuturesCommodity(value) {
    if (!value || value === institutionalFuturesCommodity.value) return;
    institutionalFuturesCommodity.value = value;
    await loadInstitutionalInsights();
    if (taifexStructuredAutoSync.value) {
      syncTaifexStructuredDefaults(institutionalDate.value, value, institutionalOptionsCommodity.value, true);
      await loadTaifexStructuredData();
    }
  }

  async function setInstitutionalOptionsCommodity(value) {
    if (!value || value === institutionalOptionsCommodity.value) return;
    institutionalOptionsCommodity.value = value;
    await loadInstitutionalInsights();
    if (taifexStructuredAutoSync.value) {
      syncTaifexStructuredDefaults(institutionalDate.value, institutionalFuturesCommodity.value, value, true);
      await loadTaifexStructuredData();
    }
  }

  async function setInstitutionalHistoryDays(value) {
    const nextValue = INSTITUTIONAL_HISTORY_OPTIONS.includes(Number(value)) ? Number(value) : 30;
    institutionalHistoryDays.value = nextValue;
    await loadInstitutionalInsights();
  }

  async function shiftInstitutionalDate(days) {
    const base = institutionalDate.value ? new Date(`${institutionalDate.value}T00:00:00`) : new Date();
    base.setDate(base.getDate() + Number(days || 0));
    await loadInstitutionalData(base.toISOString().slice(0, 10));
  }

  return {
    calendarEvents,
    tickerEvents,
    tickerNews,
    macroDashboard,
    fundamentalsDetail,
    fundamentalsSummary,
    taiwanChipDetail,
    taiwanChipSummary,
    institutionalDate,
    institutionalData,
    institutionalLoading,
    institutionalError,
    institutionalInsights,
    institutionalInsightsLoading,
    institutionalInsightsError,
    institutionalFuturesCommodity,
    institutionalOptionsCommodity,
    institutionalHistoryDays,
    taifexStructuredSection,
    taifexStructuredDateMode,
    taifexStructuredExactDate,
    taifexStructuredStartDate,
    taifexStructuredEndDate,
    taifexStructuredCommodity,
    taifexStructuredInstitution,
    taifexStructuredOptionSide,
    taifexStructuredLimit,
    taifexStructuredAutoSync,
    taifexStructuredData,
    taifexStructuredLoading,
    taifexStructuredError,
    institutionalOverlay,
    loadEventCalendar,
    loadMacroDashboard,
    loadTickerIntelligence,
    loadInstitutionalData,
    loadInstitutionalInsights,
    loadTaifexStructuredData,
    ensureInstitutionalOverlayForTicker,
    setInstitutionalDate,
    setInstitutionalFuturesCommodity,
    setInstitutionalOptionsCommodity,
    setInstitutionalHistoryDays,
    shiftInstitutionalDate,
    updateTaifexStructuredQuery,
    resetTaifexStructuredQuery,
  };
}
