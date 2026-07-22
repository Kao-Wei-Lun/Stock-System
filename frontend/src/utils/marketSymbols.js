export const TIMEFRAME_OPTIONS = [
  { tf: "1d", iv: "1m", label: "1m" },
  { tf: "5d", iv: "5m", label: "5m" },
  { tf: "1mo", iv: "15m", label: "15m" },
  { tf: "3mo", iv: "60m", label: "60m" },
  { tf: "5d", iv: "1h", label: "5D" },
  { tf: "1mo", iv: "1d", label: "1M" },
  { tf: "3mo", iv: "1d", label: "3M" },
  { tf: "1y", iv: "1d", label: "1Y" },
  { tf: "2y", iv: "1d", label: "2Y" },
  { tf: "5y", iv: "1d", label: "5Y" },
  { tf: "10y", iv: "1d", label: "10Y" },
  { tf: "max", iv: "1d", label: "MAX" },
];

export const FUTOPT_TIMEFRAME_OPTIONS = [
  { tf: "1d", iv: "1m", label: "1m" },
  { tf: "5d", iv: "5m", label: "5m" },
  { tf: "1mo", iv: "15m", label: "15m" },
  { tf: "1mo", iv: "30m", label: "30m" },
  { tf: "3mo", iv: "60m", label: "60m" },
];

export const FUTOPT_REST_POLL_MS = 15_000;
export const FUTOPT_WS_STALE_MS = 12_000;

const FUTOPT_BASE_ALIASES = new Set(["TX", "TXF", "MTX", "MXF", "TMF", "*TXFF", "*TMFF"]);
const FUTOPT_FUTURE_CONTRACT_RE = /^[A-Z]{2,5}[A-Z]\d$/;
const FUTOPT_OPTION_CONTRACT_RE = /^[A-Z]{2,5}\d{3,6}[A-Z]\d$/;
const FUTOPT_ALLOWED_PERIODS = new Set(["1d", "5d", "1mo", "3mo", "6mo"]);
const FUTOPT_DEFAULT_PERIODS = {
  "1m": "1d", "5m": "5d", "15m": "1mo", "30m": "1mo", "60m": "3mo", "1h": "3mo",
};

export function isIntradayInterval(interval) {
  return ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"]
    .includes(String(interval || "").toLowerCase());
}

export function resolveTimeframeInterval(period, interval) {
  const normalizedInterval = String(interval || "").toLowerCase();
  if (isIntradayInterval(normalizedInterval)) return normalizedInterval;
  return String(period || "").toLowerCase() === "5d" ? "1h" : "1d";
}

export function normalizeTicker(ticker) {
  const raw = (ticker || "").trim().toUpperCase();
  if (!raw || raw.startsWith("^") || raw.includes(".") || raw.includes("-") || raw.includes("=")) return raw;
  if (
    FUTOPT_BASE_ALIASES.has(raw)
    || FUTOPT_FUTURE_CONTRACT_RE.test(raw)
    || FUTOPT_OPTION_CONTRACT_RE.test(raw)
  ) return raw;
  if (!/^[A-Z]+$/.test(raw)) return `${raw}.TW`;
  return raw;
}

export function isFutoptTicker(ticker) {
  const normalized = normalizeTicker(ticker);
  return (
    FUTOPT_BASE_ALIASES.has(normalized)
    || FUTOPT_FUTURE_CONTRACT_RE.test(normalized)
    || FUTOPT_OPTION_CONTRACT_RE.test(normalized)
  );
}

export function shouldPollFutoptRestFallback({
  ticker, interval, lastRealtimeAt = 0, now = Date.now(), staleMs = FUTOPT_WS_STALE_MS,
} = {}) {
  if (!isFutoptTicker(ticker) || !isIntradayInterval(interval)) return false;
  return !lastRealtimeAt || now - lastRealtimeAt >= staleMs;
}

export function resolveFutoptInterval(interval) {
  const normalized = String(interval || "").toLowerCase();
  return ["1m", "5m", "15m", "30m", "60m", "1h"].includes(normalized) ? normalized : "1m";
}

export function resolveFutoptPeriod(period, interval) {
  const normalizedPeriod = String(period || "").toLowerCase();
  if (FUTOPT_ALLOWED_PERIODS.has(normalizedPeriod)) return normalizedPeriod;
  return FUTOPT_DEFAULT_PERIODS[resolveFutoptInterval(interval)] || "1d";
}

export function getTimeframeOptionsForTicker(ticker) {
  return isFutoptTicker(ticker) ? FUTOPT_TIMEFRAME_OPTIONS : TIMEFRAME_OPTIONS;
}

export function resolveDashboardTimeframeForTicker(ticker, period, interval) {
  const normalizedTicker = normalizeTicker(ticker);
  const requestedPeriod = String(period || "1y").toLowerCase();
  if (isFutoptTicker(normalizedTicker)) {
    const resolvedInterval = resolveFutoptInterval(interval);
    return { period: resolveFutoptPeriod(requestedPeriod, resolvedInterval), interval: resolvedInterval };
  }
  return { period: requestedPeriod, interval: resolveTimeframeInterval(requestedPeriod, interval) };
}

export function inferMarketFromTicker(ticker) {
  const normalized = normalizeTicker(ticker);
  if (isFutoptTicker(normalized)) return "FUTOPT";
  if (normalized.endsWith(".TW") || normalized.endsWith(".TWO")) return "TW";
  if (normalized.endsWith(".HK")) return "HK";
  if (normalized.startsWith("^")) return "INDEX";
  return "US";
}
