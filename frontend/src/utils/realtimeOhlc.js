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

function toRealtimeRow(dateValue, price, source, volume = 0, interval = "1m", quote = null) {
  const normalizedInterval = String(interval || "").toLowerCase();
  return {
    date: formatBucketLabel(dateValue, normalizedInterval),
    open: toFiniteNumber(quote?.open) ?? price,
    high: toFiniteNumber(quote?.high) ?? price,
    low: toFiniteNumber(quote?.low) ?? price,
    close: price,
    volume,
    adj_close: price,
    source: source || "fubon_neo",
  };
}

export function upsertRealtimeOhlcFromQuote(rows, quote, interval) {
  if (!Array.isArray(rows) || !rows.length) return Array.isArray(rows) ? rows : [];

  const price = toFiniteNumber(quote?.price);
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
    const baseHigh = toFiniteNumber(lastRow?.high) ?? price;
    const baseLow = toFiniteNumber(lastRow?.low) ?? price;
    const quoteHigh = toFiniteNumber(quote?.high) ?? price;
    const quoteLow = toFiniteNumber(quote?.low) ?? price;
    const baseVolume = toFiniteNumber(lastRow?.volume) ?? 0;
    const quoteVolume = toFiniteNumber(quote?.volume);
    nextRows[nextRows.length - 1] = {
      ...lastRow,
      close: price,
      high: isIntraday ? Math.max(baseHigh, price) : Math.max(baseHigh, quoteHigh),
      low: isIntraday ? Math.min(baseLow, price) : Math.min(baseLow, quoteLow),
      adj_close: price,
      source,
      date: formatBucketLabel(quoteBucket, normalizedInterval),
      ...(isDaily ? {
        open: toFiniteNumber(quote?.open) ?? toFiniteNumber(lastRow?.open) ?? price,
        volume: quoteVolume ?? baseVolume,
      } : isHigherTimeframe ? {
        open: toFiniteNumber(lastRow?.open) ?? toFiniteNumber(quote?.open) ?? price,
        volume: quoteVolume == null ? baseVolume : Math.max(baseVolume, quoteVolume),
      } : {
      }),
    };
    return nextRows;
  }

  if (isDaily || isHigherTimeframe) {
    const nextVolume = toFiniteNumber(quote?.volume) ?? 0;
    nextRows.push({
      date: formatBucketLabel(quoteBucket, normalizedInterval),
      open: toFiniteNumber(quote?.open) ?? price,
      high: toFiniteNumber(quote?.high) ?? price,
      low: toFiniteNumber(quote?.low) ?? price,
      close: price,
      volume: nextVolume,
      adj_close: price,
      source,
    });
    return nextRows;
  }

  nextRows.push(toRealtimeRow(quoteBucket, price, source, 0, normalizedInterval, quote));
  return nextRows;
}
