function hasOwn(source, key) {
  return Object.prototype.hasOwnProperty.call(source || {}, key);
}

function toFiniteNumberOrNull(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function toPositiveQuoteValue(value) {
  const numeric = toFiniteNumberOrNull(value);
  return numeric != null && numeric > 0 ? numeric : null;
}

function normalizeBookLevel(level = {}) {
  if (!level || typeof level !== "object") return null;
  const normalized = {};
  const price = toPositiveQuoteValue(level.price);
  const size = toFiniteNumberOrNull(level.size);
  if (price != null) normalized.price = price;
  if (size != null) normalized.size = size;
  return Object.keys(normalized).length ? normalized : null;
}

export function mergeBookLevels(previousLevels = [], incomingLevels = undefined, topLevel = null) {
  const previous = Array.isArray(previousLevels) ? previousLevels.slice(0, 5) : [];
  const next = previous.map((level) => ({ ...level }));

  if (Array.isArray(incomingLevels) && incomingLevels.length) {
    incomingLevels.slice(0, 5).forEach((level, index) => {
      const normalized = normalizeBookLevel(level);
      if (normalized) {
        next[index] = { ...(next[index] || {}), ...normalized };
      }
    });
  }

  const normalizedTopLevel = normalizeBookLevel(topLevel);
  if (normalizedTopLevel) {
    next[0] = { ...(next[0] || {}), ...normalizedTopLevel };
  }

  return next.filter((level) => level && Object.keys(level).length);
}

export function mergeRealtimeQuote(previousQuote = {}, incomingQuote = {}, fallbackName = null) {
  const nextPositiveValue = (key, fallback = null) => {
    if (!hasOwn(incomingQuote, key)) return toPositiveQuoteValue(previousQuote[key]) ?? fallback;
    if (incomingQuote[key] == null || incomingQuote[key] === "") {
      return toPositiveQuoteValue(previousQuote[key]) ?? fallback;
    }
    return toPositiveQuoteValue(incomingQuote[key]) ?? toPositiveQuoteValue(previousQuote[key]) ?? fallback;
  };

  const nextDefinedValue = (key, fallback = null) => {
    if (!hasOwn(incomingQuote, key)) return previousQuote[key] ?? fallback;
    if (incomingQuote[key] == null || incomingQuote[key] === "") return previousQuote[key] ?? fallback;
    return incomingQuote[key];
  };

  const bid = nextPositiveValue("bid", null);
  const ask = nextPositiveValue("ask", null);
  const bidSize = nextDefinedValue("bid_size", null);
  const askSize = nextDefinedValue("ask_size", null);
  const bidTopLevel = hasOwn(incomingQuote, "bid") || hasOwn(incomingQuote, "bid_size")
    ? { price: bid, size: bidSize }
    : null;
  const askTopLevel = hasOwn(incomingQuote, "ask") || hasOwn(incomingQuote, "ask_size")
    ? { price: ask, size: askSize }
    : null;
  const shouldMergeBids = Array.isArray(incomingQuote.bids)
    || hasOwn(incomingQuote, "bid")
    || hasOwn(incomingQuote, "bid_size");
  const shouldMergeAsks = Array.isArray(incomingQuote.asks)
    || hasOwn(incomingQuote, "ask")
    || hasOwn(incomingQuote, "ask_size");

  return {
    price: nextPositiveValue("price", null),
    open: nextPositiveValue("open", null),
    high: nextPositiveValue("high", null),
    low: nextPositiveValue("low", null),
    prev_close: nextPositiveValue("prev_close", null),
    volume: nextDefinedValue("volume", null),
    market_cap: nextDefinedValue("market_cap", null),
    change: hasOwn(incomingQuote, "change") ? (incomingQuote.change ?? 0) : (previousQuote.change ?? 0),
    change_pct: hasOwn(incomingQuote, "change_pct") ? (incomingQuote.change_pct ?? 0) : (previousQuote.change_pct ?? 0),
    resolved_symbol: nextDefinedValue("resolved_symbol", null),
    market: nextDefinedValue("market", null),
    exchange: nextDefinedValue("exchange", null),
    name: hasOwn(incomingQuote, "name") ? (incomingQuote.name || fallbackName) : (previousQuote.name || fallbackName),
    source: nextDefinedValue("source", null),
    quote_type: nextDefinedValue("quote_type", null),
    is_delayed: hasOwn(incomingQuote, "is_delayed") ? (incomingQuote.is_delayed ?? true) : (previousQuote.is_delayed ?? true),
    bid,
    ask,
    bid_size: bidSize,
    ask_size: askSize,
    bids: shouldMergeBids
      ? mergeBookLevels(previousQuote.bids, incomingQuote.bids, bidTopLevel)
      : (previousQuote.bids || []),
    asks: shouldMergeAsks
      ? mergeBookLevels(previousQuote.asks, incomingQuote.asks, askTopLevel)
      : (previousQuote.asks || []),
    quote_timestamp: nextDefinedValue("quote_timestamp", null),
    synced_at: nextDefinedValue("synced_at", null),
  };
}
