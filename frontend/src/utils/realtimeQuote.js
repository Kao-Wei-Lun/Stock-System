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
    bid: nextPositiveValue("bid", null),
    ask: nextPositiveValue("ask", null),
    bid_size: nextDefinedValue("bid_size", null),
    ask_size: nextDefinedValue("ask_size", null),
    bids: hasOwn(incomingQuote, "bids")
      ? (Array.isArray(incomingQuote.bids) ? incomingQuote.bids : [])
      : (previousQuote.bids || []),
    asks: hasOwn(incomingQuote, "asks")
      ? (Array.isArray(incomingQuote.asks) ? incomingQuote.asks : [])
      : (previousQuote.asks || []),
    quote_timestamp: nextDefinedValue("quote_timestamp", null),
    synced_at: nextDefinedValue("synced_at", null),
  };
}
