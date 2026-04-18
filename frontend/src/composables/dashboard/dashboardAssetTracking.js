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
  const assetAccounts = ref([]);
  const assetCashEntries = ref([]);
  const assetTradeEntries = ref([]);
  const assetPortfolio = ref(null);

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
    source: "manual",
    note: "",
  });

  const assetBaseCurrency = computed(() => assetPortfolio.value?.base_currency || "TWD");
  const assetSummary = computed(() => assetPortfolio.value?.summary || {});
  const assetAccountsSummary = computed(() => assetPortfolio.value?.accounts || []);
  const assetHoldings = computed(() => assetPortfolio.value?.holdings || []);
  const assetWarnings = computed(() => assetPortfolio.value?.warnings || []);
  const assetQuoteGaps = computed(() => assetPortfolio.value?.quote_gaps || []);
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
      if (!assetTradeForm.currency) {
        assetTradeForm.currency = getAccountBaseCurrency(primaryAccountId);
      }
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
    assetTradeForm.source = "manual";
    assetTradeForm.note = "";
  }

  async function loadAssetTrackingData({ refresh = true, silent = true } = {}) {
    assetLoading.value = !silent;
    try {
      const [accountsResponse, cashResponse, tradesResponse, portfolioResponse] = await Promise.all([
        dashboardApi.listAssetAccounts(),
        dashboardApi.listAssetCashLedger({ limit: 12 }),
        dashboardApi.listAssetTrades({ limit: 12 }),
        dashboardApi.getAssetPortfolioCurrent({ refresh, allocation_group_by: "account" }),
      ]);
      assetAccounts.value = normalizeAssetAccounts(accountsResponse?.items);
      assetCashEntries.value = normalizeAssetEntries(cashResponse);
      assetTradeEntries.value = normalizeAssetEntries(tradesResponse);
      assetPortfolio.value = portfolioResponse || null;
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
    if (["amount", "fx_rate_to_base"].includes(key)) {
      assetCashForm[key] = value === "" ? "" : Number(value);
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
    if (["quantity", "price", "fee_amount", "tax_amount", "fx_rate_to_base"].includes(key)) {
      assetTradeForm[key] = value === "" ? "" : Number(value);
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
    assetTradeForm.source = record.source || "manual";
    assetTradeForm.note = record.note || "";
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
      pushNotification({
        icon: "🏦",
        title: isEditing ? "資產帳戶已更新" : "資產帳戶已建立",
        msg: payload.name,
        type: "success",
      });
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
      if (String(assetAccountForm.id) === String(accountId)) {
        resetAssetAccountForm();
      }
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
      pushNotification({
        icon: "💵",
        title: isEditing ? "現金事件已更新" : "現金事件已建立",
        msg: `${payload.flow_type} · ${payload.currency}`,
        type: "success",
      });
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
      if (String(assetCashForm.id) === String(entryId)) {
        resetAssetCashForm();
      }
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
      pushNotification({
        icon: "📈",
        title: isEditing ? "交易事件已更新" : "交易事件已建立",
        msg: `${payload.ticker} · ${payload.side}`,
        type: "success",
      });
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
      if (String(assetTradeForm.id) === String(entryId)) {
        resetAssetTradeForm();
      }
      pushNotification({ icon: "🗑", title: "交易事件已刪除", msg: String(entryId), type: "success" });
    } catch (error) {
      console.error(error);
      pushNotification({ icon: "⚠️", title: "交易事件刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  return {
    assetLoading,
    assetAccounts,
    assetCashEntries,
    assetTradeEntries,
    assetPortfolio,
    assetBaseCurrency,
    assetSummary,
    assetAccountsSummary,
    assetHoldings,
    assetWarnings,
    assetQuoteGaps,
    assetAccountAllocation,
    assetMarketAllocation,
    assetContributors,
    assetAccountForm,
    assetCashForm,
    assetTradeForm,
    loadAssetTrackingData,
    updateAssetAccountField,
    updateAssetCashField,
    updateAssetTradeField,
    editAssetAccount,
    editAssetCashEntry,
    editAssetTradeEntry,
    resetAssetAccountForm,
    resetAssetCashForm,
    resetAssetTradeForm,
    saveAssetAccount,
    saveAssetCashEntry,
    saveAssetTradeEntry,
    deleteAssetAccount,
    deleteAssetCashEntry,
    deleteAssetTradeEntry,
  };
}
