import { computed, reactive, ref } from "vue";

function resolveAssetTradeCurrency(market) {
  return String(market || "").toUpperCase() === "US" ? "USD" : "TWD";
}

function normalizeAssetAccounts(items) {
  return Array.isArray(items) ? items : [];
}

function normalizeAssetEntries(response) {
  return Array.isArray(response?.items) ? response.items : [];
}

function normalizeHeatmapItems(items) {
  return Array.isArray(items) ? items : [];
}

function coerceNumber(value) {
  return value === "" || value == null ? "" : Number(value);
}

export function createDashboardAssetTracking({
  dashboardApi,
  currentTicker,
  currentName,
  quote,
  pushNotification,
  normalizeTicker,
  inferMarketFromTicker,
  getCurrentDateTimeInputValue,
}) {
  const assetLoading = ref(false);
  const assetPerformanceRange = ref("1y");
  const assetAccounts = ref([]);
  const assetCashEntries = ref([]);
  const assetTradeEntries = ref([]);
  const assetReconciliationEntries = ref([]);
  const assetPriceOverrides = ref([]);
  const assetFxRates = ref([]);
  const assetAdjustments = ref([]);
  const assetPortfolio = ref(null);
  const assetPerformance = ref(null);
  const assetAlerts = ref([]);
  const assetTradeImportResult = ref(null);
  const assetCashImportResult = ref(null);
  const assetJournalImportPreview = ref(null);
  const assetLastRecompute = ref(null);

  const assetAccountForm = reactive({
    id: null,
    name: "",
    institution: "",
    account_type: "brokerage",
    base_currency: "TWD",
    include_in_total: true,
    sort_order: 0,
    notes: "",
  });
  const assetCashForm = reactive({
    id: null,
    account_id: "",
    flow_date: getCurrentDateTimeInputValue(),
    flow_type: "deposit",
    amount: "",
    currency: "TWD",
    fx_rate_to_base: 1,
    is_initial_balance: false,
    counterparty: "",
    note: "",
  });
  const assetTradeForm = reactive({
    id: null,
    account_id: "",
    trade_date: getCurrentDateTimeInputValue(),
    ticker: normalizeTicker(currentTicker.value),
    display_name: currentName.value || normalizeTicker(currentTicker.value),
    market: inferMarketFromTicker(currentTicker.value),
    asset_type: "stock",
    currency: resolveAssetTradeCurrency(inferMarketFromTicker(currentTicker.value)),
    side: "buy",
    quantity: "",
    price: quote.price ?? "",
    fee_amount: 0,
    tax_amount: 0,
    fx_rate_to_base: inferMarketFromTicker(currentTicker.value) === "US" ? 32 : 1,
    is_initial_balance: false,
    source: "manual",
    note: "",
  });
  const assetReconciliationForm = reactive({
    account_id: "",
    snapshot_date: getCurrentDateTimeInputValue(),
    cash_actual: "",
    market_value_actual: "",
    note: "",
  });
  const assetPriceOverrideForm = reactive({
    id: null,
    account_id: "",
    ticker: normalizeTicker(currentTicker.value),
    effective_at: getCurrentDateTimeInputValue(),
    price: quote.price ?? "",
    currency: resolveAssetTradeCurrency(inferMarketFromTicker(currentTicker.value)),
    fx_rate_to_base: inferMarketFromTicker(currentTicker.value) === "US" ? 32 : "",
    force_override: false,
    note: "",
  });
  const assetFxRateForm = reactive({
    id: null,
    snapshot_date: getCurrentDateTimeInputValue().slice(0, 10),
    from_currency: "USD",
    to_currency: "TWD",
    rate: 32,
    source: "manual",
    note: "",
  });
  const assetAdjustmentForm = reactive({
    id: null,
    account_id: "",
    event_date: getCurrentDateTimeInputValue(),
    ticker: normalizeTicker(currentTicker.value),
    event_type: "adjustment",
    quantity_delta: "",
    cost_basis_delta: "",
    cash_delta: "",
    currency: resolveAssetTradeCurrency(inferMarketFromTicker(currentTicker.value)),
    split_ratio: "",
    target_ticker: "",
    target_display_name: "",
    target_market: inferMarketFromTicker(currentTicker.value),
    target_asset_type: "stock",
    note: "",
  });
  const assetTradeImportForm = reactive({
    default_account_id: "",
    csv_text: "",
    dry_run: true,
  });
  const assetCashImportForm = reactive({
    default_account_id: "",
    csv_text: "",
    dry_run: true,
  });
  const assetJournalImportForm = reactive({
    account_id: "",
    ticker: "",
    market: "",
    strategy_code: "",
    tag: "",
    search: "",
    limit: 20,
  });

  const assetBaseCurrency = computed(() => assetPortfolio.value?.base_currency || "TWD");
  const assetSummary = computed(() => assetPortfolio.value?.summary || {});
  const assetAccountsSummary = computed(() => assetPortfolio.value?.accounts || []);
  const assetHoldings = computed(() => assetPortfolio.value?.holdings || []);
  const assetWarnings = computed(() => assetPortfolio.value?.warnings || []);
  const assetQuoteGaps = computed(() => assetPortfolio.value?.quote_gaps || []);
  const assetReconciliation = computed(() => assetPortfolio.value?.reconciliation || { items: [], summary: {} });
  const assetAccountAllocation = computed(() => assetPortfolio.value?.allocation?.items || []);
  const assetMarketAllocation = computed(() => {
    const grouped = new Map();
    (assetHoldings.value || []).forEach((holding) => {
      const key = String(holding?.market || "UNKNOWN").toUpperCase() || "UNKNOWN";
      grouped.set(key, Number(grouped.get(key) || 0) + Number(holding?.market_value_base || 0));
    });
    const total = Array.from(grouped.values()).reduce((sum, value) => sum + Number(value || 0), 0);
    return Array.from(grouped.entries())
      .map(([key, value]) => ({
        key,
        value_base: Number(value.toFixed(6)),
        weight_pct: total ? Number(((value / total) * 100).toFixed(4)) : 0,
      }))
      .sort((left, right) => right.value_base - left.value_base);
  });
  const assetContributors = computed(() => {
    const holdings = [...(assetHoldings.value || [])];
    return {
      top_gainers: holdings
        .sort((left, right) => Number(right?.unrealized_pnl_base || 0) - Number(left?.unrealized_pnl_base || 0))
        .slice(0, 3),
      top_losers: holdings
        .sort((left, right) => Number(left?.unrealized_pnl_base || 0) - Number(right?.unrealized_pnl_base || 0))
        .slice(0, 3),
    };
  });
  const assetPerformanceSummary = computed(() => assetPerformance.value?.summary || {});
  const assetPerformanceSeries = computed(() => normalizeHeatmapItems(assetPerformance.value?.series));
  const assetMonthlyHeatmap = computed(() => normalizeHeatmapItems(assetPerformance.value?.monthly_heatmap));
  const assetRealizedVsUnrealized = computed(() => normalizeHeatmapItems(assetPerformance.value?.realized_vs_unrealized));

  function getPrimaryAccountId() {
    return assetAccounts.value[0]?.id || "";
  }

  function getAccountBaseCurrency(accountId) {
    return assetAccounts.value.find((item) => String(item.id) === String(accountId))?.base_currency || "TWD";
  }

  function ensureAssetFormAccountDefaults() {
    const primaryAccountId = getPrimaryAccountId();
    if (primaryAccountId && !assetCashForm.account_id) {
      assetCashForm.account_id = primaryAccountId;
      assetCashForm.currency = getAccountBaseCurrency(primaryAccountId);
    }
    if (primaryAccountId && !assetTradeForm.account_id) {
      assetTradeForm.account_id = primaryAccountId;
    }
    if (primaryAccountId && !assetReconciliationForm.account_id) {
      assetReconciliationForm.account_id = primaryAccountId;
    }
    if (primaryAccountId && !assetPriceOverrideForm.account_id) {
      assetPriceOverrideForm.account_id = primaryAccountId;
    }
    if (primaryAccountId && !assetAdjustmentForm.account_id) {
      assetAdjustmentForm.account_id = primaryAccountId;
    }
    if (primaryAccountId && !assetTradeImportForm.default_account_id) {
      assetTradeImportForm.default_account_id = primaryAccountId;
    }
    if (primaryAccountId && !assetCashImportForm.default_account_id) {
      assetCashImportForm.default_account_id = primaryAccountId;
    }
    if (primaryAccountId && !assetJournalImportForm.account_id) {
      assetJournalImportForm.account_id = primaryAccountId;
    }
  }

  function resetAssetAccountForm() {
    assetAccountForm.id = null;
    assetAccountForm.name = "";
    assetAccountForm.institution = "";
    assetAccountForm.account_type = "brokerage";
    assetAccountForm.base_currency = "TWD";
    assetAccountForm.include_in_total = true;
    assetAccountForm.sort_order = 0;
    assetAccountForm.notes = "";
  }

  function resetAssetCashForm() {
    const primaryAccountId = getPrimaryAccountId();
    assetCashForm.id = null;
    assetCashForm.account_id = primaryAccountId;
    assetCashForm.flow_date = getCurrentDateTimeInputValue();
    assetCashForm.flow_type = "deposit";
    assetCashForm.amount = "";
    assetCashForm.currency = getAccountBaseCurrency(primaryAccountId);
    assetCashForm.fx_rate_to_base = assetCashForm.currency === "USD" ? 32 : 1;
    assetCashForm.is_initial_balance = false;
    assetCashForm.counterparty = "";
    assetCashForm.note = "";
  }

  function resetAssetTradeForm() {
    const inferredMarket = inferMarketFromTicker(currentTicker.value);
    const primaryAccountId = getPrimaryAccountId();
    assetTradeForm.id = null;
    assetTradeForm.account_id = primaryAccountId;
    assetTradeForm.trade_date = getCurrentDateTimeInputValue();
    assetTradeForm.ticker = normalizeTicker(currentTicker.value);
    assetTradeForm.display_name = currentName.value || normalizeTicker(currentTicker.value);
    assetTradeForm.market = inferredMarket;
    assetTradeForm.asset_type = "stock";
    assetTradeForm.currency = resolveAssetTradeCurrency(inferredMarket);
    assetTradeForm.side = "buy";
    assetTradeForm.quantity = "";
    assetTradeForm.price = quote.price ?? "";
    assetTradeForm.fee_amount = 0;
    assetTradeForm.tax_amount = 0;
    assetTradeForm.fx_rate_to_base = inferredMarket === "US" ? 32 : 1;
    assetTradeForm.is_initial_balance = false;
    assetTradeForm.source = "manual";
    assetTradeForm.note = "";
  }

  function resetAssetReconciliationForm() {
    const primaryAccountId = getPrimaryAccountId();
    assetReconciliationForm.account_id = primaryAccountId;
    assetReconciliationForm.snapshot_date = getCurrentDateTimeInputValue();
    assetReconciliationForm.cash_actual = "";
    assetReconciliationForm.market_value_actual = "";
    assetReconciliationForm.note = "";
  }

  function resetAssetPriceOverrideForm() {
    const inferredMarket = inferMarketFromTicker(currentTicker.value);
    assetPriceOverrideForm.id = null;
    assetPriceOverrideForm.account_id = getPrimaryAccountId();
    assetPriceOverrideForm.ticker = normalizeTicker(currentTicker.value);
    assetPriceOverrideForm.effective_at = getCurrentDateTimeInputValue();
    assetPriceOverrideForm.price = quote.price ?? "";
    assetPriceOverrideForm.currency = resolveAssetTradeCurrency(inferredMarket);
    assetPriceOverrideForm.fx_rate_to_base = inferredMarket === "US" ? 32 : "";
    assetPriceOverrideForm.force_override = false;
    assetPriceOverrideForm.note = "";
  }

  function resetAssetFxRateForm() {
    assetFxRateForm.id = null;
    assetFxRateForm.snapshot_date = getCurrentDateTimeInputValue().slice(0, 10);
    assetFxRateForm.from_currency = "USD";
    assetFxRateForm.to_currency = "TWD";
    assetFxRateForm.rate = 32;
    assetFxRateForm.source = "manual";
    assetFxRateForm.note = "";
  }

  function resetAssetAdjustmentForm() {
    const inferredMarket = inferMarketFromTicker(currentTicker.value);
    assetAdjustmentForm.id = null;
    assetAdjustmentForm.account_id = getPrimaryAccountId();
    assetAdjustmentForm.event_date = getCurrentDateTimeInputValue();
    assetAdjustmentForm.ticker = normalizeTicker(currentTicker.value);
    assetAdjustmentForm.event_type = "adjustment";
    assetAdjustmentForm.quantity_delta = "";
    assetAdjustmentForm.cost_basis_delta = "";
    assetAdjustmentForm.cash_delta = "";
    assetAdjustmentForm.currency = resolveAssetTradeCurrency(inferredMarket);
    assetAdjustmentForm.split_ratio = "";
    assetAdjustmentForm.target_ticker = "";
    assetAdjustmentForm.target_display_name = "";
    assetAdjustmentForm.target_market = inferredMarket;
    assetAdjustmentForm.target_asset_type = "stock";
    assetAdjustmentForm.note = "";
  }

  function resetAssetImportForms() {
    assetTradeImportForm.default_account_id = getPrimaryAccountId();
    assetTradeImportForm.csv_text = "";
    assetTradeImportForm.dry_run = true;
    assetCashImportForm.default_account_id = getPrimaryAccountId();
    assetCashImportForm.csv_text = "";
    assetCashImportForm.dry_run = true;
    assetTradeImportResult.value = null;
    assetCashImportResult.value = null;
  }

  function resetAssetJournalImportForm() {
    assetJournalImportForm.account_id = getPrimaryAccountId();
    assetJournalImportForm.ticker = "";
    assetJournalImportForm.market = "";
    assetJournalImportForm.strategy_code = "";
    assetJournalImportForm.tag = "";
    assetJournalImportForm.search = "";
    assetJournalImportForm.limit = 20;
    assetJournalImportPreview.value = null;
  }

  async function loadAssetPerformance({ refresh = false } = {}) {
    const [performanceResponse, alertsResponse] = await Promise.all([
      dashboardApi.getAssetPerformance({ range: assetPerformanceRange.value, refresh }),
      dashboardApi.getAssetAlertsCurrent({ refresh, performance_range: assetPerformanceRange.value }),
    ]);
    assetPerformance.value = performanceResponse || null;
    assetAlerts.value = normalizeAssetEntries(alertsResponse);
  }

  async function loadAssetTrackingData({ refresh = true, silent = true } = {}) {
    assetLoading.value = !silent;
    try {
      const [
        accountsResponse,
        cashResponse,
        tradesResponse,
        reconciliationResponse,
        priceOverrideResponse,
        fxRateResponse,
        adjustmentResponse,
        portfolioResponse,
      ] = await Promise.all([
        dashboardApi.listAssetAccounts(),
        dashboardApi.listAssetCashLedger({ limit: 12 }),
        dashboardApi.listAssetTrades({ limit: 12 }),
        dashboardApi.listAssetReconciliation({ limit: 12 }),
        dashboardApi.listAssetPriceOverrides({ limit: 12 }),
        dashboardApi.listAssetFxRates({ limit: 12, refresh_public: refresh }),
        dashboardApi.listAssetAdjustments({ limit: 12 }),
        dashboardApi.getAssetPortfolioCurrent({ refresh, allocation_group_by: "account" }),
      ]);
      assetAccounts.value = normalizeAssetAccounts(accountsResponse?.items);
      assetCashEntries.value = normalizeAssetEntries(cashResponse);
      assetTradeEntries.value = normalizeAssetEntries(tradesResponse);
      assetReconciliationEntries.value = normalizeAssetEntries(reconciliationResponse);
      assetPriceOverrides.value = normalizeAssetEntries(priceOverrideResponse);
      assetFxRates.value = normalizeAssetEntries(fxRateResponse);
      assetAdjustments.value = normalizeAssetEntries(adjustmentResponse);
      assetPortfolio.value = portfolioResponse || null;
      await loadAssetPerformance({ refresh });
      ensureAssetFormAccountDefaults();
    } catch (error) {
      console.error(error);
      if (!silent) {
        pushNotification({
          icon: "⚠️",
          title: "資產追蹤載入失敗",
          msg: error.message || "請稍後再試",
          type: "error",
        });
      }
    } finally {
      assetLoading.value = false;
    }
  }

  function updateAssetAccountField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetAccountForm, key)) return;
    assetAccountForm[key] = key === "include_in_total"
      ? Boolean(value)
      : key === "sort_order"
        ? Number(value)
        : value;
  }

  function updateAssetCashField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetCashForm, key)) return;
    if (key === "is_initial_balance") {
      assetCashForm.is_initial_balance = Boolean(value);
      return;
    }
    if (["amount", "fx_rate_to_base"].includes(key)) {
      assetCashForm[key] = coerceNumber(value);
      return;
    }
    if (key === "account_id") {
      assetCashForm.account_id = value === "" ? "" : Number(value);
      assetCashForm.currency = getAccountBaseCurrency(assetCashForm.account_id);
      return;
    }
    assetCashForm[key] = value;
  }

  function updateAssetTradeField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetTradeForm, key)) return;
    if (key === "is_initial_balance") {
      assetTradeForm.is_initial_balance = Boolean(value);
      return;
    }
    if (["quantity", "price", "fee_amount", "tax_amount", "fx_rate_to_base"].includes(key)) {
      assetTradeForm[key] = coerceNumber(value);
      return;
    }
    if (key === "account_id") {
      assetTradeForm.account_id = value === "" ? "" : Number(value);
      return;
    }
    if (key === "ticker") {
      const ticker = normalizeTicker(value);
      assetTradeForm.ticker = ticker;
      assetTradeForm.market = inferMarketFromTicker(ticker);
      if (!assetTradeForm.display_name || assetTradeForm.display_name === currentName.value) {
        assetTradeForm.display_name = ticker;
      }
      assetTradeForm.currency = resolveAssetTradeCurrency(assetTradeForm.market);
      if (assetTradeForm.currency === "TWD") {
        assetTradeForm.fx_rate_to_base = 1;
      }
      return;
    }
    if (key === "market") {
      assetTradeForm.market = value;
      assetTradeForm.currency = resolveAssetTradeCurrency(value);
      if (assetTradeForm.currency === "TWD") {
        assetTradeForm.fx_rate_to_base = 1;
      }
      return;
    }
    assetTradeForm[key] = value;
  }

  function updateAssetReconciliationField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetReconciliationForm, key)) return;
    if (["cash_actual", "market_value_actual"].includes(key)) {
      assetReconciliationForm[key] = coerceNumber(value);
      return;
    }
    if (key === "account_id") {
      assetReconciliationForm.account_id = value === "" ? "" : Number(value);
      return;
    }
    assetReconciliationForm[key] = value;
  }

  function updateAssetPriceOverrideField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetPriceOverrideForm, key)) return;
    if (["price", "fx_rate_to_base"].includes(key)) {
      assetPriceOverrideForm[key] = coerceNumber(value);
      return;
    }
    if (key === "account_id") {
      assetPriceOverrideForm.account_id = value === "" ? "" : Number(value);
      return;
    }
    if (key === "ticker") {
      assetPriceOverrideForm.ticker = normalizeTicker(value);
      return;
    }
    if (key === "force_override") {
      assetPriceOverrideForm.force_override = Boolean(value);
      return;
    }
    assetPriceOverrideForm[key] = value;
  }

  function updateAssetFxRateField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetFxRateForm, key)) return;
    if (key === "rate") {
      assetFxRateForm.rate = coerceNumber(value);
      return;
    }
    assetFxRateForm[key] = value;
  }

  function updateAssetAdjustmentField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetAdjustmentForm, key)) return;
    if (["quantity_delta", "cost_basis_delta", "cash_delta", "split_ratio"].includes(key)) {
      assetAdjustmentForm[key] = coerceNumber(value);
      return;
    }
    if (key === "account_id") {
      assetAdjustmentForm.account_id = value === "" ? "" : Number(value);
      return;
    }
    if (["ticker", "target_ticker"].includes(key)) {
      assetAdjustmentForm[key] = normalizeTicker(value);
      return;
    }
    assetAdjustmentForm[key] = value;
  }

  function updateAssetTradeImportField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetTradeImportForm, key)) return;
    assetTradeImportForm[key] = key === "default_account_id"
      ? (value === "" ? "" : Number(value))
      : key === "dry_run"
        ? Boolean(value)
        : value;
  }

  function updateAssetCashImportField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetCashImportForm, key)) return;
    assetCashImportForm[key] = key === "default_account_id"
      ? (value === "" ? "" : Number(value))
      : key === "dry_run"
        ? Boolean(value)
        : value;
  }

  function updateAssetJournalImportField(key, value) {
    if (!Object.prototype.hasOwnProperty.call(assetJournalImportForm, key)) return;
    assetJournalImportForm[key] = key === "account_id"
      ? (value === "" ? "" : Number(value))
      : key === "limit"
        ? Number(value)
        : value;
  }

  function editAssetAccount(record) {
    if (!record) return;
    assetAccountForm.id = record.id;
    assetAccountForm.name = record.name || "";
    assetAccountForm.institution = record.institution || "";
    assetAccountForm.account_type = record.account_type || "brokerage";
    assetAccountForm.base_currency = record.base_currency || "TWD";
    assetAccountForm.include_in_total = Boolean(record.include_in_total);
    assetAccountForm.sort_order = Number(record.sort_order || 0);
    assetAccountForm.notes = record.notes || "";
  }

  function editAssetCashEntry(record) {
    if (!record) return;
    assetCashForm.id = record.id;
    assetCashForm.account_id = Number(record.account_id || "");
    assetCashForm.flow_date = String(record.flow_date || "").slice(0, 16);
    assetCashForm.flow_type = record.flow_type || "deposit";
    assetCashForm.amount = record.amount ?? "";
    assetCashForm.currency = record.currency || "TWD";
    assetCashForm.fx_rate_to_base = record.fx_rate_to_base ?? 1;
    assetCashForm.is_initial_balance = Boolean(record.is_initial_balance);
    assetCashForm.counterparty = record.counterparty || "";
    assetCashForm.note = record.note || "";
  }

  function editAssetTradeEntry(record) {
    if (!record) return;
    assetTradeForm.id = record.id;
    assetTradeForm.account_id = Number(record.account_id || "");
    assetTradeForm.trade_date = String(record.trade_date || "").slice(0, 16);
    assetTradeForm.ticker = record.ticker || "";
    assetTradeForm.display_name = record.display_name || record.ticker || "";
    assetTradeForm.market = record.market || inferMarketFromTicker(record.ticker);
    assetTradeForm.asset_type = record.asset_type || "stock";
    assetTradeForm.currency = record.currency || resolveAssetTradeCurrency(record.market);
    assetTradeForm.side = record.side || "buy";
    assetTradeForm.quantity = record.quantity ?? "";
    assetTradeForm.price = record.price ?? "";
    assetTradeForm.fee_amount = record.fee_amount ?? 0;
    assetTradeForm.tax_amount = record.tax_amount ?? 0;
    assetTradeForm.fx_rate_to_base = record.fx_rate_to_base ?? 1;
    assetTradeForm.is_initial_balance = Boolean(record.is_initial_balance);
    assetTradeForm.source = record.source || "manual";
    assetTradeForm.note = record.note || "";
  }

  function editAssetPriceOverride(record) {
    if (!record) return;
    assetPriceOverrideForm.id = record.id;
    assetPriceOverrideForm.account_id = record.account_id == null ? "" : Number(record.account_id);
    assetPriceOverrideForm.ticker = record.ticker || "";
    assetPriceOverrideForm.effective_at = String(record.effective_at || "").slice(0, 16);
    assetPriceOverrideForm.price = record.price ?? "";
    assetPriceOverrideForm.currency = record.currency || "TWD";
    assetPriceOverrideForm.fx_rate_to_base = record.fx_rate_to_base ?? "";
    assetPriceOverrideForm.force_override = Boolean(record.force_override);
    assetPriceOverrideForm.note = record.note || "";
  }

  function editAssetFxRate(record) {
    if (!record) return;
    assetFxRateForm.id = record.id;
    assetFxRateForm.snapshot_date = String(record.snapshot_date || "").slice(0, 10);
    assetFxRateForm.from_currency = record.from_currency || "USD";
    assetFxRateForm.to_currency = record.to_currency || "TWD";
    assetFxRateForm.rate = record.rate ?? "";
    assetFxRateForm.source = record.source || "manual";
    assetFxRateForm.note = record.note || "";
  }

  function editAssetAdjustment(record) {
    if (!record) return;
    assetAdjustmentForm.id = record.id;
    assetAdjustmentForm.account_id = Number(record.account_id || "");
    assetAdjustmentForm.event_date = String(record.event_date || "").slice(0, 16);
    assetAdjustmentForm.ticker = record.ticker || "";
    assetAdjustmentForm.event_type = record.event_type || "adjustment";
    assetAdjustmentForm.quantity_delta = record.quantity_delta ?? "";
    assetAdjustmentForm.cost_basis_delta = record.cost_basis_delta ?? "";
    assetAdjustmentForm.cash_delta = record.cash_delta ?? "";
    assetAdjustmentForm.currency = record.currency || "TWD";
    assetAdjustmentForm.split_ratio = record.split_ratio ?? "";
    assetAdjustmentForm.target_ticker = record.target_ticker || "";
    assetAdjustmentForm.target_display_name = record.target_display_name || "";
    assetAdjustmentForm.target_market = record.target_market || inferMarketFromTicker(record.target_ticker || record.ticker);
    assetAdjustmentForm.target_asset_type = record.target_asset_type || "stock";
    assetAdjustmentForm.note = record.note || "";
  }

  async function saveAssetAccount() {
    try {
      const isEditing = Boolean(assetAccountForm.id);
      const payload = {
        name: String(assetAccountForm.name || "").trim(),
        institution: String(assetAccountForm.institution || "").trim() || null,
        account_type: assetAccountForm.account_type || "brokerage",
        base_currency: String(assetAccountForm.base_currency || "TWD").toUpperCase(),
        include_in_total: Boolean(assetAccountForm.include_in_total),
        sort_order: Number(assetAccountForm.sort_order || 0),
        notes: String(assetAccountForm.notes || "").trim() || null,
      };
      if (assetAccountForm.id) {
        await dashboardApi.updateAssetAccount(assetAccountForm.id, payload);
      } else {
        await dashboardApi.createAssetAccount(payload);
      }
      await loadAssetTrackingData({ refresh: false, silent: false });
      resetAssetAccountForm();
      pushNotification({ icon: "🏦", title: isEditing ? "資產帳戶已更新" : "資產帳戶已建立", msg: payload.name, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "資產帳戶儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function deleteAssetAccount(accountId = assetAccountForm.id) {
    if (!accountId) return;
    try {
      await dashboardApi.deleteAssetAccount(accountId);
      await loadAssetTrackingData({ refresh: true, silent: false });
      if (String(assetAccountForm.id) === String(accountId)) resetAssetAccountForm();
      pushNotification({ icon: "🗑", title: "資產帳戶已刪除", msg: String(accountId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "資產帳戶刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function saveAssetCashEntry() {
    try {
      const isEditing = Boolean(assetCashForm.id);
      const payload = {
        account_id: Number(assetCashForm.account_id),
        flow_date: assetCashForm.flow_date,
        flow_type: assetCashForm.flow_type,
        amount: Number(assetCashForm.amount),
        currency: assetCashForm.currency,
        fx_rate_to_base: Number(assetCashForm.fx_rate_to_base || 1),
        is_initial_balance: Boolean(assetCashForm.is_initial_balance),
        counterparty: String(assetCashForm.counterparty || "").trim() || null,
        note: String(assetCashForm.note || "").trim() || null,
      };
      if (assetCashForm.id) {
        await dashboardApi.updateAssetCashEntry(assetCashForm.id, payload);
      } else {
        await dashboardApi.createAssetCashEntry(payload);
      }
      await loadAssetTrackingData({ refresh: true, silent: false });
      resetAssetCashForm();
      pushNotification({ icon: "💵", title: isEditing ? "現金事件已更新" : "現金事件已建立", msg: `${payload.flow_type} · ${payload.currency}`, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "現金事件儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function deleteAssetCashEntry(entryId = assetCashForm.id) {
    if (!entryId) return;
    try {
      await dashboardApi.deleteAssetCashEntry(entryId);
      await loadAssetTrackingData({ refresh: true, silent: false });
      if (String(assetCashForm.id) === String(entryId)) resetAssetCashForm();
      pushNotification({ icon: "🗑", title: "現金事件已刪除", msg: String(entryId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "現金事件刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function saveAssetTradeEntry() {
    try {
      const isEditing = Boolean(assetTradeForm.id);
      const payload = {
        account_id: Number(assetTradeForm.account_id),
        trade_date: assetTradeForm.trade_date,
        ticker: normalizeTicker(assetTradeForm.ticker),
        display_name: String(assetTradeForm.display_name || "").trim() || null,
        market: assetTradeForm.market || inferMarketFromTicker(assetTradeForm.ticker),
        asset_type: assetTradeForm.asset_type || "stock",
        currency: assetTradeForm.currency || resolveAssetTradeCurrency(assetTradeForm.market),
        side: assetTradeForm.side || "buy",
        quantity: Number(assetTradeForm.quantity),
        price: Number(assetTradeForm.price),
        fee_amount: Number(assetTradeForm.fee_amount || 0),
        tax_amount: Number(assetTradeForm.tax_amount || 0),
        fx_rate_to_base: Number(assetTradeForm.fx_rate_to_base || 1),
        is_initial_balance: Boolean(assetTradeForm.is_initial_balance),
        source: assetTradeForm.source || "manual",
        note: String(assetTradeForm.note || "").trim() || null,
      };
      if (assetTradeForm.id) {
        await dashboardApi.updateAssetTrade(assetTradeForm.id, payload);
      } else {
        await dashboardApi.createAssetTrade(payload);
      }
      await loadAssetTrackingData({ refresh: true, silent: false });
      resetAssetTradeForm();
      pushNotification({ icon: "📈", title: isEditing ? "交易事件已更新" : "交易事件已建立", msg: `${payload.ticker} · ${payload.side}`, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易事件儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function deleteAssetTradeEntry(entryId = assetTradeForm.id) {
    if (!entryId) return;
    try {
      await dashboardApi.deleteAssetTrade(entryId);
      await loadAssetTrackingData({ refresh: true, silent: false });
      if (String(assetTradeForm.id) === String(entryId)) resetAssetTradeForm();
      pushNotification({ icon: "🗑", title: "交易事件已刪除", msg: String(entryId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易事件刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function saveAssetReconciliation() {
    try {
      if (!assetReconciliationForm.account_id) throw new Error("請先選擇帳戶");
      if (assetReconciliationForm.cash_actual === "" && assetReconciliationForm.market_value_actual === "") {
        throw new Error("請至少輸入現金或持倉市值");
      }
      const payload = {
        account_id: Number(assetReconciliationForm.account_id),
        snapshot_date: assetReconciliationForm.snapshot_date,
        note: String(assetReconciliationForm.note || "").trim() || null,
      };
      if (assetReconciliationForm.cash_actual !== "") payload.cash_actual = Number(assetReconciliationForm.cash_actual);
      if (assetReconciliationForm.market_value_actual !== "") payload.market_value_actual = Number(assetReconciliationForm.market_value_actual);
      await dashboardApi.createAssetReconciliation(payload, { refresh: true });
      await loadAssetTrackingData({ refresh: true, silent: false });
      resetAssetReconciliationForm();
      pushNotification({ icon: "🧾", title: "對帳快照已記錄", msg: `帳戶 #${payload.account_id}`, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "對帳快照儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function deleteAssetReconciliation(snapshotId) {
    if (!snapshotId) return;
    try {
      await dashboardApi.deleteAssetReconciliation(snapshotId);
      await loadAssetTrackingData({ refresh: false, silent: false });
      pushNotification({ icon: "🗑", title: "對帳快照已刪除", msg: String(snapshotId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "對帳快照刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function saveAssetPriceOverride() {
    try {
      const isEditing = Boolean(assetPriceOverrideForm.id);
      const payload = {
        account_id: assetPriceOverrideForm.account_id === "" ? null : Number(assetPriceOverrideForm.account_id),
        ticker: normalizeTicker(assetPriceOverrideForm.ticker),
        effective_at: assetPriceOverrideForm.effective_at,
        price: Number(assetPriceOverrideForm.price),
        currency: String(assetPriceOverrideForm.currency || "TWD").toUpperCase(),
        force_override: Boolean(assetPriceOverrideForm.force_override),
        note: String(assetPriceOverrideForm.note || "").trim() || null,
      };
      if (assetPriceOverrideForm.fx_rate_to_base !== "" && assetPriceOverrideForm.fx_rate_to_base != null) {
        payload.fx_rate_to_base = Number(assetPriceOverrideForm.fx_rate_to_base);
      }
      if (assetPriceOverrideForm.id) {
        await dashboardApi.updateAssetPriceOverride(assetPriceOverrideForm.id, payload);
      } else {
        await dashboardApi.createAssetPriceOverride(payload);
      }
      await loadAssetTrackingData({ refresh: true, silent: false });
      resetAssetPriceOverrideForm();
      pushNotification({ icon: "🪙", title: isEditing ? "手動價格已更新" : "手動價格已建立", msg: payload.ticker, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "手動價格儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function deleteAssetPriceOverride(overrideId = assetPriceOverrideForm.id) {
    if (!overrideId) return;
    try {
      await dashboardApi.deleteAssetPriceOverride(overrideId);
      await loadAssetTrackingData({ refresh: true, silent: false });
      if (String(assetPriceOverrideForm.id) === String(overrideId)) resetAssetPriceOverrideForm();
      pushNotification({ icon: "🗑", title: "手動價格已刪除", msg: String(overrideId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "手動價格刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function saveAssetFxRate() {
    try {
      const isEditing = Boolean(assetFxRateForm.id);
      const payload = {
        snapshot_date: assetFxRateForm.snapshot_date,
        from_currency: String(assetFxRateForm.from_currency || "USD").toUpperCase(),
        to_currency: String(assetFxRateForm.to_currency || "TWD").toUpperCase(),
        rate: Number(assetFxRateForm.rate),
        source: String(assetFxRateForm.source || "manual"),
        note: String(assetFxRateForm.note || "").trim() || null,
      };
      if (assetFxRateForm.id) {
        await dashboardApi.updateAssetFxRate(assetFxRateForm.id, payload);
      } else {
        await dashboardApi.createAssetFxRate(payload);
      }
      await loadAssetTrackingData({ refresh: true, silent: false });
      resetAssetFxRateForm();
      pushNotification({ icon: "💱", title: isEditing ? "匯率已更新" : "匯率已建立", msg: `${payload.from_currency}/${payload.to_currency}`, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "匯率儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function deleteAssetFxRate(fxRateId = assetFxRateForm.id) {
    if (!fxRateId) return;
    try {
      await dashboardApi.deleteAssetFxRate(fxRateId);
      await loadAssetTrackingData({ refresh: true, silent: false });
      if (String(assetFxRateForm.id) === String(fxRateId)) resetAssetFxRateForm();
      pushNotification({ icon: "🗑", title: "匯率已刪除", msg: String(fxRateId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "匯率刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function saveAssetAdjustment() {
    try {
      const isEditing = Boolean(assetAdjustmentForm.id);
      const payload = {
        account_id: Number(assetAdjustmentForm.account_id),
        event_date: assetAdjustmentForm.event_date,
        ticker: normalizeTicker(assetAdjustmentForm.ticker),
        event_type: assetAdjustmentForm.event_type || "adjustment",
        currency: String(assetAdjustmentForm.currency || "TWD").toUpperCase(),
        target_ticker: assetAdjustmentForm.target_ticker ? normalizeTicker(assetAdjustmentForm.target_ticker) : null,
        target_display_name: String(assetAdjustmentForm.target_display_name || "").trim() || null,
        target_market: String(assetAdjustmentForm.target_market || "").trim() || null,
        target_asset_type: String(assetAdjustmentForm.target_asset_type || "").trim() || null,
        note: String(assetAdjustmentForm.note || "").trim() || null,
      };
      ["quantity_delta", "cost_basis_delta", "cash_delta", "split_ratio"].forEach((key) => {
        if (assetAdjustmentForm[key] !== "" && assetAdjustmentForm[key] != null) {
          payload[key] = Number(assetAdjustmentForm[key]);
        }
      });
      if (assetAdjustmentForm.id) {
        await dashboardApi.updateAssetAdjustment(assetAdjustmentForm.id, payload);
      } else {
        await dashboardApi.createAssetAdjustment(payload);
      }
      await loadAssetTrackingData({ refresh: true, silent: false });
      resetAssetAdjustmentForm();
      pushNotification({ icon: "🧩", title: isEditing ? "調整事件已更新" : "調整事件已建立", msg: payload.ticker, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "調整事件儲存失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function deleteAssetAdjustment(adjustmentId = assetAdjustmentForm.id) {
    if (!adjustmentId) return;
    try {
      await dashboardApi.deleteAssetAdjustment(adjustmentId);
      await loadAssetTrackingData({ refresh: true, silent: false });
      if (String(assetAdjustmentForm.id) === String(adjustmentId)) resetAssetAdjustmentForm();
      pushNotification({ icon: "🗑", title: "調整事件已刪除", msg: String(adjustmentId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "調整事件刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function importAssetTradesCsv({ dryRun = assetTradeImportForm.dry_run } = {}) {
    try {
      const result = await dashboardApi.importAssetTradesCsv({
        csv_text: assetTradeImportForm.csv_text,
        default_account_id: assetTradeImportForm.default_account_id || null,
        dry_run: Boolean(dryRun),
      });
      assetTradeImportResult.value = result;
      if (!dryRun) {
        await loadAssetTrackingData({ refresh: true, silent: false });
      }
      pushNotification({
        icon: dryRun ? "📄" : "📥",
        title: dryRun ? "交易 CSV 預覽完成" : "交易 CSV 已匯入",
        msg: `成功 ${result?.summary?.created_count ?? result?.summary?.row_count ?? 0} 筆`,
        type: "success",
      });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易 CSV 匯入失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function importAssetCashCsv({ dryRun = assetCashImportForm.dry_run } = {}) {
    try {
      const result = await dashboardApi.importAssetCashCsv({
        csv_text: assetCashImportForm.csv_text,
        default_account_id: assetCashImportForm.default_account_id || null,
        dry_run: Boolean(dryRun),
      });
      assetCashImportResult.value = result;
      if (!dryRun) {
        await loadAssetTrackingData({ refresh: true, silent: false });
      }
      pushNotification({
        icon: dryRun ? "📄" : "📥",
        title: dryRun ? "現金 CSV 預覽完成" : "現金 CSV 已匯入",
        msg: `成功 ${result?.summary?.created_count ?? result?.summary?.row_count ?? 0} 筆`,
        type: "success",
      });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "現金 CSV 匯入失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function previewAssetJournalImport() {
    try {
      const payload = {
        account_id: Number(assetJournalImportForm.account_id),
        limit: Number(assetJournalImportForm.limit || 20),
      };
      ["ticker", "market", "strategy_code", "tag", "search"].forEach((key) => {
        const value = String(assetJournalImportForm[key] || "").trim();
        if (value) payload[key] = key === "ticker" ? normalizeTicker(value) : value;
      });
      assetJournalImportPreview.value = await dashboardApi.previewAssetJournalImport(payload);
      pushNotification({ icon: "🔎", title: "Journal 匯入預覽已更新", msg: `可匯入 ${assetJournalImportPreview.value?.summary?.importable_count || 0} 筆`, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "Journal 預覽失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function importAssetJournalEntries() {
    try {
      const payload = {
        account_id: Number(assetJournalImportForm.account_id),
        limit: Number(assetJournalImportForm.limit || 20),
      };
      ["ticker", "market", "strategy_code", "tag", "search"].forEach((key) => {
        const value = String(assetJournalImportForm[key] || "").trim();
        if (value) payload[key] = key === "ticker" ? normalizeTicker(value) : value;
      });
      const result = await dashboardApi.importAssetJournal(payload);
      await loadAssetTrackingData({ refresh: true, silent: false });
      await previewAssetJournalImport();
      pushNotification({ icon: "📘", title: "Journal 已匯入資產流水", msg: `新增 ${result?.summary?.created_count || 0} 筆`, type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "Journal 匯入失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function recomputeAssetTracking() {
    try {
      assetLastRecompute.value = await dashboardApi.recomputeAssetTracking({
        refresh: true,
        performance_range: assetPerformanceRange.value,
      });
      await loadAssetTrackingData({ refresh: true, silent: false });
      pushNotification({ icon: "🧮", title: "資產重算完成", msg: "已重新整理估值、績效與提醒", type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "資產重算失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function setAssetPerformanceRange(range) {
    assetPerformanceRange.value = String(range || "1y");
    try {
      await loadAssetPerformance({ refresh: false });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "績效資料載入失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  return {
    assetLoading,
    assetPerformanceRange,
    assetAccounts,
    assetCashEntries,
    assetTradeEntries,
    assetReconciliationEntries,
    assetPriceOverrides,
    assetFxRates,
    assetAdjustments,
    assetPortfolio,
    assetPerformance,
    assetAlerts,
    assetTradeImportResult,
    assetCashImportResult,
    assetJournalImportPreview,
    assetLastRecompute,
    assetBaseCurrency,
    assetSummary,
    assetAccountsSummary,
    assetHoldings,
    assetWarnings,
    assetQuoteGaps,
    assetReconciliation,
    assetAccountAllocation,
    assetMarketAllocation,
    assetContributors,
    assetPerformanceSummary,
    assetPerformanceSeries,
    assetMonthlyHeatmap,
    assetRealizedVsUnrealized,
    assetAccountForm,
    assetCashForm,
    assetTradeForm,
    assetReconciliationForm,
    assetPriceOverrideForm,
    assetFxRateForm,
    assetAdjustmentForm,
    assetTradeImportForm,
    assetCashImportForm,
    assetJournalImportForm,
    loadAssetTrackingData,
    loadAssetPerformance,
    setAssetPerformanceRange,
    updateAssetAccountField,
    updateAssetCashField,
    updateAssetTradeField,
    updateAssetReconciliationField,
    updateAssetPriceOverrideField,
    updateAssetFxRateField,
    updateAssetAdjustmentField,
    updateAssetTradeImportField,
    updateAssetCashImportField,
    updateAssetJournalImportField,
    editAssetAccount,
    editAssetCashEntry,
    editAssetTradeEntry,
    editAssetPriceOverride,
    editAssetFxRate,
    editAssetAdjustment,
    resetAssetAccountForm,
    resetAssetCashForm,
    resetAssetTradeForm,
    resetAssetReconciliationForm,
    resetAssetPriceOverrideForm,
    resetAssetFxRateForm,
    resetAssetAdjustmentForm,
    resetAssetImportForms,
    resetAssetJournalImportForm,
    saveAssetAccount,
    saveAssetCashEntry,
    saveAssetTradeEntry,
    saveAssetReconciliation,
    saveAssetPriceOverride,
    saveAssetFxRate,
    saveAssetAdjustment,
    deleteAssetAccount,
    deleteAssetCashEntry,
    deleteAssetTradeEntry,
    deleteAssetReconciliation,
    deleteAssetPriceOverride,
    deleteAssetFxRate,
    deleteAssetAdjustment,
    importAssetTradesCsv,
    importAssetCashCsv,
    previewAssetJournalImport,
    importAssetJournalEntries,
    recomputeAssetTracking,
  };
}
