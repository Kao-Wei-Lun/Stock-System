import { reactive, ref } from "vue";

export function createDashboardAlerting({
  dashboardApi,
  currentTicker,
  institutionalFuturesCommodity,
  institutionalOptionsCommodity,
  institutionalHistoryDays,
  institutionalOverlay,
  pushNotification,
  normalizeTicker,
}) {
  const alerts = ref([]);
  const alertTriggerLogs = ref({});
  const alertLogLoading = ref({});
  const expandedAlertLogId = ref(null);
  const alertModalOpen = ref(false);
  const alertForm = reactive({
    ticker: "AAPL",
    type: "price",
    cond: "大於",
    value: "",
    metric: "",
    futures_commodity: "",
    options_commodity: "",
    event_type: "",
    event_title: "",
    importance: "",
    event_scope: "",
    target_label: "",
    prefill_hint: "",
    context_tags: [],
    context_source: "",
    context_group_name: "",
    snapshot_price: null,
    snapshot_source: "",
    snapshot_timestamp: "",
  });

  function mapAlertRecord(alert) {
    return {
      ...alert,
      cond: alert.condition || alert.cond,
    };
  }

  function mapAlertTriggerLog(record) {
    const payload = record?.payload || {};
    const evaluation = payload.evaluation || {};
    return {
      ...record,
      trigger_value: record?.trigger_value ?? evaluation.current_value ?? null,
      threshold_value: record?.threshold_value ?? evaluation.threshold_value ?? null,
      payload,
    };
  }

  function pruneAlertArtifacts(nextAlerts) {
    const validIds = new Set((nextAlerts || []).map((item) => String(item.id)));
    alertTriggerLogs.value = Object.fromEntries(
      Object.entries(alertTriggerLogs.value).filter(([key]) => validIds.has(String(key))),
    );
    alertLogLoading.value = Object.fromEntries(
      Object.entries(alertLogLoading.value).filter(([key]) => validIds.has(String(key))),
    );
    if (expandedAlertLogId.value != null && !validIds.has(String(expandedAlertLogId.value))) {
      expandedAlertLogId.value = null;
    }
  }

  function alertRequiresNumericValue(type, condition) {
    const normalizedType = String(type || "").toLowerCase();
    const normalizedCondition = String(condition || "").toLowerCase();
    if (["market_risk", "institutional"].includes(normalizedType)) return false;
    if (normalizedType !== "macd") return true;
    return !["上穿", "下穿", "cross_up", "cross_down"].includes(normalizedCondition);
  }

  function defaultAlertCondition(type) {
    const normalizedType = String(type || "").toLowerCase();
    if (normalizedType === "market_risk") return "high";
    if (normalizedType === "institutional") return "medium_or_high";
    if (normalizedType === "event") return "within_days";
    return normalizedType === "macd" ? "上穿" : "大於";
  }

  function resetAlertForm() {
    alertForm.ticker = normalizeTicker(currentTicker.value || "AAPL");
    alertForm.type = "price";
    alertForm.cond = "大於";
    alertForm.value = "";
    alertForm.metric = "";
    alertForm.futures_commodity = "";
    alertForm.options_commodity = "";
    alertForm.event_type = "";
    alertForm.event_title = "";
    alertForm.importance = "";
    alertForm.event_scope = "";
    alertForm.target_label = "";
    alertForm.prefill_hint = "";
    alertForm.context_tags = [];
    alertForm.context_source = "";
    alertForm.context_group_name = "";
    alertForm.snapshot_price = null;
    alertForm.snapshot_source = "";
    alertForm.snapshot_timestamp = "";
  }

  function formatAlertConditionLabel(condition, type = "") {
    const normalizedType = String(type || "").toLowerCase();
    const normalizedCondition = String(condition || "").toLowerCase();
    if (normalizedType === "institutional") {
      const labels = {
        high: "高異常",
        medium_or_high: "中度以上異常",
      };
      return labels[normalizedCondition] || String(condition || "");
    }
    if (normalizedType === "event") {
      const labels = {
        within_days: "事件前提醒",
      };
      return labels[normalizedCondition] || String(condition || "");
    }
    const labels = {
      gt: "大於",
      lt: "小於",
      eq: "等於",
      大於: "大於",
      小於: "小於",
      等於: "等於",
      cross_up: "黃金交叉",
      cross_down: "死亡交叉",
      上穿: "黃金交叉",
      下穿: "死亡交叉",
      high: "進入高風險",
      medium_or_high: "進入中風險以上",
      risk_off: "進入 risk-off",
      offensive: "進入偏進攻",
    };
    return labels[normalizedCondition] || labels[String(condition || "")] || String(condition || "");
  }

  function buildAlertCreatePayload(draft = {}) {
    const type = String(draft.type || alertForm.type || "price").toLowerCase();
    const condition = draft.condition || draft.cond || defaultAlertCondition(type);
    const requiresNumericValue = alertRequiresNumericValue(type, condition);
    const numericValue = requiresNumericValue ? Number(draft.value) : null;
    const normalizedTicker = type === "market_risk"
      ? "MARKET"
      : normalizeTicker(draft.ticker || currentTicker.value);
    const futuresCommodity = draft.futures_commodity
      || institutionalFuturesCommodity.value
      || institutionalOverlay.value?.commodity
      || "";
    const optionsCommodity = draft.options_commodity || institutionalOptionsCommodity.value || "";
    if (!normalizedTicker || (requiresNumericValue && Number.isNaN(numericValue))) {
      return null;
    }
    return {
      ticker: normalizedTicker,
      type,
      condition,
      value: numericValue,
      timeframe: "1d",
      condition_payload: {
        operator: condition,
        metric: type === "volume"
          ? "volume_ratio"
          : type === "basis"
            ? (draft.metric || "basis_pct")
            : type === "institutional"
              ? (draft.metric || "anomaly_score")
              : null,
        spot_ticker: type === "basis" ? normalizedTicker : null,
        futures_commodity: ["basis", "institutional"].includes(type) ? futuresCommodity || null : null,
        options_commodity: type === "institutional" ? optionsCommodity || null : null,
        event_type: type === "event" ? (draft.event_type || null) : null,
        event_title: type === "event" ? (draft.event_title || null) : null,
        importance: type === "event" ? (draft.importance || null) : null,
        event_scope: type === "event" ? (draft.event_scope || "ticker") : null,
        target_label: draft.target_label
          || (type === "basis" && futuresCommodity
            ? `${futuresCommodity} / ${normalizedTicker}`
            : type === "institutional"
              ? (futuresCommodity || normalizedTicker)
              : normalizedTicker),
        history_days: type === "institutional" ? institutionalHistoryDays.value : null,
        context_source: draft.context_source || null,
        context_group_name: draft.context_group_name || null,
        context_tags: Array.isArray(draft.context_tags) && draft.context_tags.length ? draft.context_tags : null,
        snapshot_price: draft.snapshot_price ?? null,
        snapshot_source: draft.snapshot_source || null,
        snapshot_timestamp: draft.snapshot_timestamp || null,
        prefill_hint: draft.prefill_hint || null,
      },
      active: true,
    };
  }

  function getAlertSignature(source = {}) {
    const type = String(source.type || "").toLowerCase();
    const ticker = type === "market_risk" ? "MARKET" : normalizeTicker(source.ticker || "");
    const condition = String(source.condition || source.cond || "").trim();
    if (!ticker || !type || !condition) return "";
    const rawValue = source.value;
    const valueKey = rawValue == null || rawValue === ""
      ? "null"
      : Number.isFinite(Number(rawValue))
        ? String(Number(rawValue))
        : String(rawValue).trim();
    return [ticker, type, condition, valueKey].join("|");
  }

  async function loadAlerts({ silent = true } = {}) {
    try {
      const response = await dashboardApi.listAlerts();
      const nextAlerts = Array.isArray(response?.items) ? response.items.map((item) => mapAlertRecord(item)) : [];
      alerts.value = nextAlerts;
      pruneAlertArtifacts(nextAlerts);
    } catch (error) {
      console.error(error);
      if (!silent) {
        pushNotification({ icon: "⚠️", title: "警報載入失敗", msg: "請稍後再試", type: "error" });
      }
    }
  }

  function openAlertModal(ticker = currentTicker.value, overrides = {}) {
    const options = ticker && typeof ticker === "object" && !Array.isArray(ticker)
      ? ticker
      : { ticker, ...overrides };
    resetAlertForm();
    alertForm.ticker = normalizeTicker(options.ticker || currentTicker.value || "AAPL");
    if (options.type) updateAlertField("type", options.type);
    if (options.condition) updateAlertField("cond", options.condition);
    if ("value" in options) {
      alertForm.value = options.value == null ? "" : String(options.value);
    }
    alertForm.metric = options.metric || "";
    alertForm.futures_commodity = options.futures_commodity || "";
    alertForm.options_commodity = options.options_commodity || "";
    alertForm.event_type = options.event_type || "";
    alertForm.event_title = options.event_title || "";
    alertForm.importance = options.importance || "";
    alertForm.event_scope = options.event_scope || "";
    alertForm.target_label = options.target_label || "";
    alertForm.prefill_hint = options.prefill_hint || "";
    alertForm.context_tags = Array.isArray(options.context_tags) ? options.context_tags.filter(Boolean) : [];
    alertForm.context_source = options.context_source || "";
    alertForm.context_group_name = options.context_group_name || "";
    alertForm.snapshot_price = options.snapshot_price ?? null;
    alertForm.snapshot_source = options.snapshot_source || "";
    alertForm.snapshot_timestamp = options.snapshot_timestamp || "";
    alertModalOpen.value = true;
  }

  function closeAlertModal() {
    alertModalOpen.value = false;
  }

  function updateAlertField(key, value) {
    if (key === "type") {
      const previousType = String(alertForm.type || "").toLowerCase();
      const nextType = String(value || "").toLowerCase();
      alertForm.type = value;
      alertForm.cond = defaultAlertCondition(value);
      if (nextType === "market_risk") {
        alertForm.ticker = "MARKET";
      } else if (previousType === "market_risk" && (!alertForm.ticker || String(alertForm.ticker).toUpperCase() === "MARKET")) {
        alertForm.ticker = normalizeTicker(currentTicker.value || "AAPL");
      }
      if (!alertRequiresNumericValue(value, alertForm.cond)) {
        alertForm.value = "";
      }
      return;
    }
    if (key === "cond") {
      alertForm.cond = value;
      if (!alertRequiresNumericValue(alertForm.type, value)) {
        alertForm.value = "";
      }
      return;
    }
    alertForm[key] = value;
  }

  async function saveAlert() {
    const payload = buildAlertCreatePayload({
      ticker: alertForm.ticker,
      type: alertForm.type,
      condition: alertForm.cond,
      value: alertForm.value,
      metric: alertForm.metric,
      futures_commodity: alertForm.futures_commodity,
      options_commodity: alertForm.options_commodity,
      event_type: alertForm.event_type,
      event_title: alertForm.event_title,
      importance: alertForm.importance,
      event_scope: alertForm.event_scope,
      target_label: alertForm.target_label,
      context_source: alertForm.context_source,
      context_group_name: alertForm.context_group_name,
      context_tags: alertForm.context_tags,
      snapshot_price: alertForm.snapshot_price,
      snapshot_source: alertForm.snapshot_source,
      snapshot_timestamp: alertForm.snapshot_timestamp,
      prefill_hint: alertForm.prefill_hint,
    });
    if (!payload) {
      pushNotification({ icon: "⚠️", title: "警報設定失敗", msg: "請完整填寫警報所需欄位", type: "error" });
      return;
    }
    try {
      const record = await dashboardApi.createAlert(payload);
      alerts.value = [mapAlertRecord(record), ...alerts.value];
      alertModalOpen.value = false;
      resetAlertForm();
      const displayValue = record.value == null ? "" : ` ${record.value}`;
      const targetLabel = String(record.type || "").toLowerCase() === "market_risk" ? "市場" : record.condition_payload?.target_label || record.ticker;
      const conditionLabel = formatAlertConditionLabel(record.condition, record.type);
      pushNotification({ icon: "🔔", title: "警報已設定", msg: `${targetLabel} ${conditionLabel}${displayValue}`.trim(), type: "success" });
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "警報設定失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  async function createAlertsBatch(inputs) {
    const drafts = Array.isArray(inputs) ? inputs : [inputs];
    if (!drafts.length) return { created: 0, skipped: 0, invalid: 0, failed: 0 };

    const existingSignatures = new Set(alerts.value.map((item) => getAlertSignature(item)).filter(Boolean));
    const stagedSignatures = new Set();
    const payloads = [];
    let skipped = 0;
    let invalid = 0;

    drafts.forEach((draft) => {
      const payload = buildAlertCreatePayload(draft);
      if (!payload) {
        invalid += 1;
        return;
      }
      const signature = getAlertSignature(payload);
      if (!signature || existingSignatures.has(signature) || stagedSignatures.has(signature)) {
        skipped += 1;
        return;
      }
      stagedSignatures.add(signature);
      payloads.push(payload);
    });

    const createdRecords = [];
    let failed = 0;
    let lastError = null;
    for (const payload of payloads) {
      try {
        const record = await dashboardApi.createAlert(payload);
        createdRecords.push(record);
        existingSignatures.add(getAlertSignature(record));
      } catch (error) {
        failed += 1;
        lastError = error;
      }
    }

    if (createdRecords.length) {
      alerts.value = [...createdRecords.map((item) => mapAlertRecord(item)), ...alerts.value];
      const summary = [`已建立 ${createdRecords.length} 筆`];
      if (skipped) summary.push(`略過 ${skipped} 筆重複`);
      if (invalid) summary.push(`略過 ${invalid} 筆缺少快照`);
      if (failed) summary.push(`失敗 ${failed} 筆`);
      pushNotification({ icon: "🔔", title: "批次警報已建立", msg: summary.join(" · "), type: failed ? "warning" : "success" });
      return { created: createdRecords.length, skipped, invalid, failed };
    }

    const failureSummary = [];
    if (skipped) failureSummary.push(`重複 ${skipped} 筆`);
    if (invalid) failureSummary.push(`缺少快照 ${invalid} 筆`);
    if (failed) failureSummary.push(`失敗 ${failed} 筆`);
    pushNotification({ icon: "⚠️", title: "批次警報未建立", msg: failureSummary.join(" · ") || lastError?.message || "請稍後再試", type: "error" });
    return { created: 0, skipped, invalid, failed };
  }

  async function loadAlertTriggerLogs(alertId, { force = false } = {}) {
    const cacheKey = String(alertId);
    if (!force && Array.isArray(alertTriggerLogs.value[cacheKey])) {
      return alertTriggerLogs.value[cacheKey];
    }
    alertLogLoading.value = { ...alertLogLoading.value, [cacheKey]: true };
    try {
      const response = await dashboardApi.listAlertTriggers(alertId, { limit: 20 });
      const logs = Array.isArray(response?.items) ? response.items.map((item) => mapAlertTriggerLog(item)) : [];
      alertTriggerLogs.value = { ...alertTriggerLogs.value, [cacheKey]: logs };
      return logs;
    } catch (error) {
      pushNotification({ icon: "!", title: "Alert log load failed", msg: error.message || "Please try again later", type: "error" });
      return [];
    } finally {
      alertLogLoading.value = { ...alertLogLoading.value, [cacheKey]: false };
    }
  }

  async function toggleAlertLog(alertId) {
    if (alertId == null) return;
    if (String(expandedAlertLogId.value) === String(alertId)) {
      expandedAlertLogId.value = null;
      return;
    }
    expandedAlertLogId.value = alertId;
    await loadAlertTriggerLogs(alertId);
  }

  async function toggleAlertActive(alertId) {
    if (alertId == null) return;
    const target = alerts.value.find((item) => String(item.id) === String(alertId));
    if (!target) return;
    const nextActive = !target.active;
    const payload = nextActive ? { active: true, triggered: false, triggered_at: null } : { active: false };
    try {
      const record = await dashboardApi.updateAlert(alertId, payload);
      alerts.value = alerts.value.map((item) => (String(item.id) === String(alertId) ? mapAlertRecord(record) : item));
      pushNotification({ icon: nextActive ? ">" : "||", title: nextActive ? "Alert resumed" : "Alert paused", msg: `${record.ticker} ${record.condition || record.cond}`, type: "success" });
    } catch (error) {
      pushNotification({ icon: "!", title: nextActive ? "Resume alert failed" : "Pause alert failed", msg: error.message || "Please try again later", type: "error" });
    }
  }

  async function deleteAlert(alertId) {
    if (alertId == null) return;
    const target = alerts.value.find((item) => String(item.id) === String(alertId));
    try {
      await dashboardApi.deleteAlert(alertId);
      alerts.value = alerts.value.filter((item) => String(item.id) !== String(alertId));
      pruneAlertArtifacts(alerts.value);
      pushNotification({ icon: "🗑", title: "警報已刪除", msg: target ? `${target.ticker} ${target.condition || target.cond}` : "已移除警報", type: "success" });
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "警報刪除失敗", msg: error.message || "請稍後再試", type: "error" });
    }
  }

  return {
    alerts,
    alertTriggerLogs,
    alertLogLoading,
    expandedAlertLogId,
    alertModalOpen,
    alertForm,
    loadAlerts,
    openAlertModal,
    closeAlertModal,
    updateAlertField,
    saveAlert,
    createAlertsBatch,
    toggleAlertLog,
    toggleAlertActive,
    deleteAlert,
  };
}
