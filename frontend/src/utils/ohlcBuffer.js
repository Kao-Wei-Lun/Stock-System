export const DEFAULT_OHLC_BUFFER_LIMIT = 500;

export function mergeOhlcBuffer(currentRows, incomingRows, maxRows = DEFAULT_OHLC_BUFFER_LIMIT) {
  const byDate = new Map();
  for (const row of [...(currentRows || []), ...(incomingRows || [])]) {
    if (!row?.date) continue;
    byDate.set(String(row.date), row);
  }
  return [...byDate.values()]
    .sort((left, right) => String(left.date).localeCompare(String(right.date)))
    .slice(-Math.max(1, Number(maxRows) || DEFAULT_OHLC_BUFFER_LIMIT));
}
