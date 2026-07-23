export const CHART_UPDATE_KIND = Object.freeze({
  noop: "noop",
  lastBar: "last-bar",
  appendBar: "append-bar",
  fullReset: "full-reset",
});

export function classifyChartDataUpdate(previousRows, nextRows, {
  previousTicker = null,
  nextTicker = null,
  previousInterval = null,
  nextInterval = null,
} = {}) {
  const previous = Array.isArray(previousRows) ? previousRows : [];
  const next = Array.isArray(nextRows) ? nextRows : [];
  if (
    (previousTicker != null && nextTicker != null && previousTicker !== nextTicker)
    || (previousInterval != null && nextInterval != null && previousInterval !== nextInterval)
  ) {
    return CHART_UPDATE_KIND.fullReset;
  }
  if (previousRows === nextRows) return CHART_UPDATE_KIND.noop;
  if (!previous.length || !next.length) return CHART_UPDATE_KIND.fullReset;

  const previousLast = previous.at(-1);
  const nextLast = next.at(-1);
  const sameFirstBar = previous[0] === next[0];
  if (
    next.length === previous.length
    && sameFirstBar
    && previous.at(-2) === next.at(-2)
    && previousLast?.date === nextLast?.date
  ) {
    return previousLast === nextLast ? CHART_UPDATE_KIND.noop : CHART_UPDATE_KIND.lastBar;
  }
  if (
    next.length === previous.length + 1
    && sameFirstBar
    && previousLast === next.at(-2)
  ) {
    return CHART_UPDATE_KIND.appendBar;
  }
  return CHART_UPDATE_KIND.fullReset;
}
