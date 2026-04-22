const INTRADAY_INTERVAL_MINUTES = {
  "1m": 1,
  "2m": 2,
  "5m": 5,
  "15m": 15,
  "30m": 30,
  "60m": 60,
  "90m": 90,
  "1h": 60,
};
const HIGHER_TIMEFRAME_INTERVALS = new Set(["1wk", "1mo"]);

function toFiniteNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function toPositivePrice(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

function resolveCandleHigh(open, close, high = null) {
  const values = [toPositivePrice(open), toPositivePrice(close), toPositivePrice(high)].filter((value) => value != null);
  return values.length ? Math.max(...values) : null;
}

function resolveCandleLow(open, close, low = null) {
  const values = [toPositivePrice(open), toPositivePrice(close), toPositivePrice(low)].filter((value) => value != null);
  return values.length ? Math.min(...values) : null;
}

function parseDate(value) {
  if (!value) return null;
  const normalized = typeof value === "string" && value.includes(" ") ? value.replace(" ", "T") : value;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

function formatLocalDate(value, includeTime = false) {
  const parsed = parseDate(value);
  if (!parsed) return null;
  const year = parsed.getFullYear();
  const month = pad2(parsed.getMonth() + 1);
  const day = pad2(parsed.getDate());
  if (!includeTime) {
    return `${year}-${month}-${day}`;
  }
  const hour = pad2(parsed.getHours());
  const minute = pad2(parsed.getMinutes());
  const second = pad2(parsed.getSeconds());
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

function isIntradayInterval(interval) {
  return Boolean(INTRADAY_INTERVAL_MINUTES[String(interval || "").toLowerCase()]);
}

function isHigherTimeframeInterval(interval) {
  return HIGHER_TIMEFRAME_INTERVALS.has(String(interval || "").toLowerCase());
}

function formatBucketLabel(dateValue, interval) {
  return formatLocalDate(dateValue, isIntradayInterval(interval));
}

function getWeekStart(date) {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  const weekday = (result.getDay() + 6) % 7;
  result.setDate(result.getDate() - weekday);
  return result;
}

export function getIntervalBucketStart(value, interval) {
  const parsed = parseDate(value);
  if (!parsed) return null;

  const intradayMinutes = INTRADAY_INTERVAL_MINUTES[String(interval || "").toLowerCase()];
  if (intradayMinutes) {
    const result = new Date(parsed);
    result.setSeconds(0, 0);
    const totalMinutes = result.getHours() * 60 + result.getMinutes();
    const bucketMinutes = Math.floor(totalMinutes / intradayMinutes) * intradayMinutes;
    result.setHours(Math.floor(bucketMinutes / 60), bucketMinutes % 60, 0, 0);
    return result;
  }

  if (String(interval || "").toLowerCase() === "1wk") {
    return getWeekStart(parsed);
  }
  if (String(interval || "").toLowerCase() === "1mo") {
    return new Date(parsed.getFullYear(), parsed.getMonth(), 1);
  }
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

function toRealtimeRow(dateValue, price, source, volume = 0, interval = "1m") {
  const normalizedInterval = String(interval || "").toLowerCase();
  return {
    date: formatBucketLabel(dateValue, normalizedInterval),
    open: price,
    high: price,
    low: price,
    close: price,
    volume,
    adj_close: price,
    source: source || "fubon_neo",
  };
}

function normalizeIncomingCandleVolume(value, fallback = 0) {
  const numeric = toFiniteNumber(value);
  return numeric == null ? fallback : Math.max(0, numeric);
}

function resolveIntradayVolumeDelta(quote) {
  const currentTotalVolume = toFiniteNumber(quote?.volume);
  const previousTotalVolume = toFiniteNumber(quote?.previous_total_volume);
  if (currentTotalVolume == null || previousTotalVolume == null) return null;
  if (currentTotalVolume < previousTotalVolume) return null;
  return currentTotalVolume - previousTotalVolume;
}

export function upsertRealtimeOhlcFromQuote(rows, quote, interval) {
  if (!Array.isArray(rows) || !rows.length) return Array.isArray(rows) ? rows : [];

  const price = toPositivePrice(quote?.price);
  if (price == null) return rows;

  const normalizedInterval = String(interval || "1d").toLowerCase();
  const quoteTime = parseDate(quote?.quote_timestamp || quote?.synced_at);
  if (!quoteTime) return rows;

  const nextRows = [...rows];
  const lastRow = nextRows[nextRows.length - 1];
  const lastBucket = getIntervalBucketStart(lastRow?.date, normalizedInterval);
  const quoteBucket = getIntervalBucketStart(quoteTime, normalizedInterval);
  if (!lastBucket || !quoteBucket) return rows;

  const source = quote?.source || lastRow?.source || "fubon_neo";
  const isIntraday = isIntradayInterval(normalizedInterval);
  const isDaily = normalizedInterval === "1d";
  const isHigherTimeframe = isHigherTimeframeInterval(normalizedInterval);
  const isSameBucket = lastBucket.getTime() === quoteBucket.getTime();

  if (quoteBucket.getTime() < lastBucket.getTime()) {
    return rows;
  }

  if (isSameBucket) {
    const quoteOpen = isIntraday
      ? (toPositivePrice(lastRow?.open) ?? price)
      : (toPositivePrice(quote?.open) ?? toPositivePrice(lastRow?.open) ?? price);
    const baseHigh = toPositivePrice(lastRow?.high) ?? price;
    const baseLow = toPositivePrice(lastRow?.low) ?? price;
    const quoteHigh = isIntraday
      ? price
      : (resolveCandleHigh(quoteOpen, price, quote?.high) ?? price);
    const quoteLow = isIntraday
      ? price
      : (resolveCandleLow(quoteOpen, price, quote?.low) ?? price);
    const baseVolume = toFiniteNumber(lastRow?.volume) ?? 0;
    const quoteVolume = toFiniteNumber(quote?.volume);
    const intradayVolumeDelta = resolveIntradayVolumeDelta(quote);
    nextRows[nextRows.length - 1] = {
      ...lastRow,
      close: price,
      high: isIntraday ? Math.max(baseHigh, price) : Math.max(baseHigh, quoteHigh),
      low: isIntraday ? Math.min(baseLow, price) : Math.min(baseLow, quoteLow),
      adj_close: price,
      source,
      date: formatBucketLabel(quoteBucket, normalizedInterval),
      ...(isDaily ? {
        open: quoteOpen,
        volume: quoteVolume ?? baseVolume,
      } : isHigherTimeframe ? {
        open: toPositivePrice(lastRow?.open) ?? toPositivePrice(quote?.open) ?? price,
        volume: quoteVolume == null ? baseVolume : Math.max(baseVolume, quoteVolume),
      } : {
        volume: intradayVolumeDelta == null ? baseVolume : Math.max(0, baseVolume + intradayVolumeDelta),
      }),
    };
    return nextRows;
  }

  if (isDaily || isHigherTimeframe) {
    const nextVolume = toFiniteNumber(quote?.volume) ?? 0;
    const open = toPositivePrice(quote?.open) ?? price;
    nextRows.push({
      date: formatBucketLabel(quoteBucket, normalizedInterval),
      open,
      high: resolveCandleHigh(open, price, quote?.high) ?? price,
      low: resolveCandleLow(open, price, quote?.low) ?? price,
      close: price,
      volume: nextVolume,
      adj_close: price,
      source,
    });
    return nextRows;
  }

  nextRows.push(toRealtimeRow(
    quoteBucket,
    price,
    source,
    Math.max(0, resolveIntradayVolumeDelta(quote) ?? 0),
    normalizedInterval,
  ));
  return nextRows;
}

export function upsertRealtimeOhlcFromCandle(rows, candle, interval = "1m") {
  if (!Array.isArray(rows) || !rows.length || !candle?.date) return Array.isArray(rows) ? rows : [];

  const normalizedInterval = String(interval || "1m").toLowerCase();
  const candleBucket = getIntervalBucketStart(candle.date, normalizedInterval);
  const lastRow = rows[rows.length - 1];
  const lastBucket = getIntervalBucketStart(lastRow?.date, normalizedInterval);
  if (!candleBucket || !lastBucket) return rows;

  const nextRows = [...rows];
  const source = candle.source || lastRow?.source || "fubon_neo";
  const lastIsSameBucket = lastBucket.getTime() === candleBucket.getTime();
  const lastSameBucket = lastIsSameBucket ? lastRow : null;
  const close = toPositivePrice(candle.close)
    ?? toPositivePrice(candle.open)
    ?? toPositivePrice(lastSameBucket?.close);
  if (close == null) return rows;

  const open = toPositivePrice(candle.open) ?? toPositivePrice(lastSameBucket?.open) ?? close;
  const highCandidates = [
    open,
    close,
    toPositivePrice(candle.high),
    toPositivePrice(lastSameBucket?.high),
  ].filter((value) => value != null);
  const lowCandidates = [
    open,
    close,
    toPositivePrice(candle.low),
    toPositivePrice(lastSameBucket?.low),
  ].filter((value) => value != null);
  const nextRow = {
    date: formatBucketLabel(candleBucket, normalizedInterval),
    open,
    high: Math.max(...highCandidates),
    low: Math.min(...lowCandidates),
    close,
    volume: normalizeIncomingCandleVolume(candle.volume, normalizeIncomingCandleVolume(lastSameBucket?.volume, 0)),
    adj_close: close,
    source,
  };

  if (candleBucket.getTime() < lastBucket.getTime()) {
    return rows;
  }

  if (lastIsSameBucket) {
    nextRows[nextRows.length - 1] = nextRow;
    return nextRows;
  }

  nextRows.push(nextRow);
  return nextRows;
}
