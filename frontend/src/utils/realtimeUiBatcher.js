const DEFAULT_HIDDEN_FLUSH_MS = 250;

function normalizeTicker(value) {
  return String(value || "").trim().toUpperCase();
}

function timestampRank(message) {
  const value = message?.data?.quote_timestamp ?? message?.data?.ts ?? message?.ts;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const parsed = Date.parse(String(value || "").replace(" ", "T"));
  return Number.isFinite(parsed) ? parsed : null;
}

function meaningful(value) {
  return value != null && value !== "" && (!Array.isArray(value) || value.length > 0);
}

export function mergeBatchedQuoteMessage(currentMessage, incomingMessage) {
  if (!currentMessage) return incomingMessage;
  if (!incomingMessage) return currentMessage;

  const current = currentMessage.data || {};
  const incoming = incomingMessage.data || {};
  const currentRank = timestampRank(currentMessage);
  const incomingRank = timestampRank(incomingMessage);
  const incomingIsLatest = currentRank == null || incomingRank == null || incomingRank >= currentRank;
  const data = { ...current };

  if (incomingIsLatest) {
    Object.entries(incoming).forEach(([key, value]) => {
      if (key === "high" || key === "low" || !meaningful(value)) return;
      data[key] = value;
    });
  }

  const highs = [current.high, incoming.high].map(Number).filter(Number.isFinite);
  const lows = [current.low, incoming.low].map(Number).filter(Number.isFinite);
  if (highs.length) data.high = Math.max(...highs);
  if (lows.length) data.low = Math.min(...lows);

  return {
    ...(incomingIsLatest ? currentMessage : incomingMessage),
    ...(incomingIsLatest ? incomingMessage : currentMessage),
    ticker: normalizeTicker(data.ticker || incomingMessage.ticker || currentMessage.ticker),
    data,
  };
}

export function createRealtimeUiBatcher({
  onQuote,
  onBooks,
  onCandle,
  getActiveTicker,
  enabled = true,
  requestFrame = globalThis.requestAnimationFrame,
  cancelFrame = globalThis.cancelAnimationFrame,
  setTimer = globalThis.setTimeout,
  clearTimer = globalThis.clearTimeout,
  documentRef = globalThis.document,
  hiddenFlushMs = DEFAULT_HIDDEN_FLUSH_MS,
} = {}) {
  const pendingQuotes = new Map();
  const pendingBooks = new Map();
  let scheduledKind = null;
  let scheduledHandle = null;
  let destroyed = false;

  function cancelScheduled() {
    if (scheduledHandle == null) return;
    if (scheduledKind === "frame") cancelFrame?.(scheduledHandle);
    else clearTimer?.(scheduledHandle);
    scheduledHandle = null;
    scheduledKind = null;
  }

  function flush() {
    cancelScheduled();
    const activeTicker = normalizeTicker(getActiveTicker?.());
    const quote = pendingQuotes.get(activeTicker);
    const books = pendingBooks.get(activeTicker);
    pendingQuotes.clear();
    pendingBooks.clear();
    if (quote) onQuote?.(quote);
    if (books) onBooks?.(books);
  }

  function scheduleFlush() {
    if (destroyed || scheduledHandle != null) return;
    if (documentRef?.hidden || typeof requestFrame !== "function") {
      scheduledKind = "timer";
      scheduledHandle = setTimer?.(flush, Math.max(100, Number(hiddenFlushMs) || DEFAULT_HIDDEN_FLUSH_MS));
      return;
    }
    scheduledKind = "frame";
    scheduledHandle = requestFrame(flush);
  }

  function push(message) {
    if (destroyed || !message) return;
    if (!enabled) {
      if (message.type === "quote") onQuote?.(message);
      else if (message.type === "books") onBooks?.(message);
      else if (message.type === "candle") onCandle?.(message);
      return;
    }

    const ticker = normalizeTicker(message.ticker || message.data?.ticker);
    if (!ticker) return;
    if (message.type === "candle") {
      onCandle?.(message);
      return;
    }
    if (message.type === "quote") {
      pendingQuotes.set(ticker, mergeBatchedQuoteMessage(pendingQuotes.get(ticker), message));
      scheduleFlush();
    } else if (message.type === "books") {
      const previous = pendingBooks.get(ticker);
      const previousRank = timestampRank(previous);
      const incomingRank = timestampRank(message);
      if (previousRank == null || incomingRank == null || incomingRank >= previousRank) {
        pendingBooks.set(ticker, message);
      }
      scheduleFlush();
    }
  }

  function clearTicker(ticker) {
    const normalized = normalizeTicker(ticker);
    pendingQuotes.delete(normalized);
    pendingBooks.delete(normalized);
  }

  function handleVisibilityChange() {
    if (!documentRef?.hidden && (pendingQuotes.size || pendingBooks.size)) {
      flush();
    }
  }

  documentRef?.addEventListener?.("visibilitychange", handleVisibilityChange);

  function destroy() {
    destroyed = true;
    cancelScheduled();
    pendingQuotes.clear();
    pendingBooks.clear();
    documentRef?.removeEventListener?.("visibilitychange", handleVisibilityChange);
  }

  return {
    push,
    flush,
    clearTicker,
    destroy,
    pendingCount: () => pendingQuotes.size + pendingBooks.size,
  };
}
