function parseRenderableOhlcDate(value) {
  if (!value) return null;
  const normalized = typeof value === "string" && value.includes(" ") ? value.replace(" ", "T") : value;
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function isRenderableOhlcRow(row) {
  if (!row || !parseRenderableOhlcDate(row.date)) return false;

  const rawOpen = row.open ?? row.close;
  const rawHigh = row.high ?? row.close;
  const rawLow = row.low ?? row.close;
  const rawClose = row.close ?? row.open;

  if ([rawOpen, rawHigh, rawLow, rawClose].some((value) => value == null || value === "")) {
    return false;
  }

  const open = Number(rawOpen);
  const high = Number(rawHigh);
  const low = Number(rawLow);
  const close = Number(rawClose);

  return [open, high, low, close].every(Number.isFinite);
}

export function filterRenderableOhlcRows(rows) {
  return Array.isArray(rows) ? rows.filter((row) => isRenderableOhlcRow(row)) : [];
}
