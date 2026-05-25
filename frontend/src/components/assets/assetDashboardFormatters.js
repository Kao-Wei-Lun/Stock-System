export const EMPTY_MARK = "--";

const NEGATIVE_FLOW_TYPES = new Set(["withdraw", "fee", "tax", "fx_fee", "transfer_out"]);

export function parseFiniteNumber(value) {
  if (value === "" || value == null) return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function numberOrZero(value) {
  return parseFiniteNumber(value) ?? 0;
}

export function firstFinite(...values) {
  for (const value of values) {
    const numeric = parseFiniteNumber(value);
    if (numeric != null) return numeric;
  }
  return null;
}

export function toneForValue(value, classNames = {}) {
  const numeric = parseFiniteNumber(value);
  const positive = classNames.positive || "positive";
  const negative = classNames.negative || "negative";
  const neutral = classNames.neutral || "neutral";
  if (numeric == null || numeric === 0) return neutral;
  return numeric > 0 ? positive : negative;
}

export function trendClass(value) {
  return toneForValue(value, { positive: "up", negative: "dn", neutral: "neutral" });
}

export function signedValueForFlow(value, flowType = "") {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return null;
  const normalizedType = String(flowType || "").toLowerCase();
  if (!normalizedType) return numeric;
  return NEGATIVE_FLOW_TYPES.has(normalizedType) ? -Math.abs(numeric) : Math.abs(numeric);
}

export function formatNumber(value, digits = 2, options = {}) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return options.emptyMark || EMPTY_MARK;
  return numeric.toLocaleString("zh-TW", {
    minimumFractionDigits: options.minimumFractionDigits ?? 0,
    maximumFractionDigits: digits,
  });
}

export function formatInteger(value, options = {}) {
  return formatNumber(value, 0, options);
}

export function formatShares(value, digits = 4, options = {}) {
  return formatNumber(value, digits, options);
}

export function formatCurrency(value, currency = "TWD", options = {}) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return options.emptyMark || EMPTY_MARK;
  const prefix = currency ? `${currency} ` : "";
  return `${prefix}${numeric.toLocaleString("zh-TW", {
    minimumFractionDigits: options.minimumFractionDigits ?? 0,
    maximumFractionDigits: options.maximumFractionDigits ?? 2,
  })}`;
}

export function formatSignedCurrency(value, currency = "TWD", flowType = "", options = {}) {
  const signed = signedValueForFlow(value, flowType);
  if (signed == null) return options.emptyMark || EMPTY_MARK;
  const sign = signed > 0 ? "+" : signed < 0 ? "-" : "";
  const prefix = currency ? `${currency} ` : "";
  return `${sign}${prefix}${Math.abs(signed).toLocaleString("zh-TW", {
    minimumFractionDigits: options.minimumFractionDigits ?? 0,
    maximumFractionDigits: options.maximumFractionDigits ?? 2,
  })}`;
}

export function formatPercent(value, digits = 2, options = {}) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return options.emptyMark || EMPTY_MARK;
  return `${numeric.toFixed(digits)}%`;
}

export function formatCompactNumber(value, includeSign = false, options = {}) {
  const numeric = parseFiniteNumber(value);
  if (numeric == null) return options.emptyMark || EMPTY_MARK;
  const sign = includeSign && numeric > 0 ? "+" : includeSign && numeric < 0 ? "-" : "";
  const absolute = Math.abs(numeric);
  if (absolute >= 1_000_000) return `${sign}${(absolute / 1_000_000).toFixed(1)}M`;
  if (absolute >= 1_000) return `${sign}${(absolute / 1_000).toFixed(1)}K`;
  return `${sign}${absolute.toFixed(0)}`;
}

export function formatDateLabel(value, includeTime = false, options = {}) {
  if (!value) return options.emptyMark || EMPTY_MARK;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return options.emptyMark || EMPTY_MARK;
  return parsed.toLocaleString("zh-TW", {
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function formatShortDate(value, options = {}) {
  if (!value) return options.emptyMark || EMPTY_MARK;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return options.emptyMark || EMPTY_MARK;
  return parsed.toLocaleDateString("zh-TW", {
    month: "2-digit",
    day: "2-digit",
  });
}

export function formatMonthLabel(value, options = {}) {
  if (!value) return options.emptyMark || EMPTY_MARK;
  const normalized = String(value);
  const year = normalized.slice(0, 4);
  const month = normalized.slice(5, 7);
  if (!year || !month) return normalized || (options.emptyMark || EMPTY_MARK);
  return `${year}/${month}`;
}

export function formatRangeLabel(value) {
  return String(value || "1y").toUpperCase();
}

export function percentAgainst(value, total) {
  const numerator = parseFiniteNumber(value);
  const denominator = parseFiniteNumber(total);
  if (numerator == null || denominator == null || denominator === 0) return null;
  return (numerator / denominator) * 100;
}

export function formatCalculationMethodLabel(method) {
  const normalized = String(method || "").trim();
  const labels = {
    latest_two_snapshots: "使用最近兩筆績效快照計算",
    sum_holdings_cost_basis_base: "使用目前持倉的成本基礎加總",
    sum_holdings_market_value_and_cash_by_currency: "依持倉市值與現金餘額，按原始幣別聚合",
  };
  return labels[normalized] || "使用系統提供的計算方法";
}

export function formatCalculationLimitation(limitation) {
  const normalized = String(limitation || "").trim();
  const labels = {
    may_include_cash_flows: "可能包含入出金影響",
    may_include_fx_changes: "可能包含匯率變動",
    may_include_recalculation_effects: "可能包含資料重算影響",
  };
  return labels[normalized] || "可能受資料品質或計算條件影響";
}

export function normalizeDataQualitySeverity(severity) {
  const normalized = String(severity || "").trim().toLowerCase();
  if (["ok", "info", "warning", "critical"].includes(normalized)) return normalized;
  return "";
}

export function mergeUserVisibleMessages(...sources) {
  const merged = [];
  sources.flat().forEach((message) => {
    const text = String(message || "").trim();
    if (!text || merged.includes(text)) return;
    merged.push(text);
  });
  return merged;
}
