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

function toRealtimeRow(dateValue, price, source, volume = 0) {
  return {
    date: formatLocalDate(dateValue, true),
    open: price,
    high: price,
    low: price,
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
  const isDaily = normalizedInterval === "1d";
  const isSameBucket = lastBucket.getTime() === quoteBucket.getTime();

  if (quoteBucket.getTime() < lastBucket.getTime()) {
    return rows;
  }

  if (isSameBucket) {
    const baseHigh = toFiniteNumber(lastRow?.high) ?? price;
    const baseLow = toFiniteNumber(lastRow?.low) ?? price;
    nextRows[nextRows.length - 1] = {
      ...lastRow,
      close: price,
      high: isDaily ? Math.max(baseHigh, toFiniteNumber(quote?.high) ?? price) : Math.max(baseHigh, price),
      low: isDaily ? Math.min(baseLow, toFiniteNumber(quote?.low) ?? price) : Math.min(baseLow, price),
      adj_close: price,
      source,
      ...(isDaily ? {
        open: toFiniteNumber(quote?.open) ?? toFiniteNumber(lastRow?.open) ?? price,
        volume: toFiniteNumber(quote?.volume) ?? toFiniteNumber(lastRow?.volume) ?? 0,
        date: formatLocalDate(quoteBucket, false),
      } : {
        date: formatLocalDate(quoteBucket, true),
      }),
    };
    return nextRows;
  }

  if (isDaily) {
    nextRows.push({
      date: formatLocalDate(quoteBucket, false),
      open: toFiniteNumber(quote?.open) ?? price,
      high: toFiniteNumber(quote?.high) ?? price,
      low: toFiniteNumber(quote?.low) ?? price,
      close: price,
      volume: toFiniteNumber(quote?.volume) ?? 0,
      adj_close: price,
      source,
    });
    return nextRows;
  }

  nextRows.push(toRealtimeRow(quoteBucket, price, source));
  return nextRows;
}
