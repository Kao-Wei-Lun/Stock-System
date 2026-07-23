export const QV_PERFORMANCE_MARKS = Object.freeze({
  appMounted: "qv:app-mounted",
  terminalVisible: "qv:terminal-visible",
  chartDataReady: "qv:chart-data-ready",
  chartPainted: "qv:chart-painted",
});

function getPerformanceApi() {
  return typeof globalThis.performance === "object" ? globalThis.performance : null;
}

function sanitizeDetail(detail) {
  if (!detail || typeof detail !== "object") return undefined;
  return Object.fromEntries(
    Object.entries(detail)
      .filter(([, value]) => ["string", "number", "boolean"].includes(typeof value))
      .slice(0, 8),
  );
}

export function readQuantVisionPerformance() {
  const performanceApi = getPerformanceApi();
  const result = {
    time_origin: Number(performanceApi?.timeOrigin || 0) || null,
    marks: {},
  };
  for (const name of Object.values(QV_PERFORMANCE_MARKS)) {
    const entries = performanceApi?.getEntriesByName?.(name, "mark") || [];
    const entry = entries.at(-1);
    result.marks[name] = entry
      ? { start_time_ms: Number(entry.startTime.toFixed(2)), detail: entry.detail || null }
      : null;
  }
  return result;
}

export function markQuantVisionPerformance(name, detail) {
  if (!Object.values(QV_PERFORMANCE_MARKS).includes(name)) return false;
  const performanceApi = getPerformanceApi();
  if (typeof performanceApi?.mark !== "function") return false;

  performanceApi.clearMarks?.(name);
  const safeDetail = sanitizeDetail(detail);
  try {
    performanceApi.mark(name, safeDetail ? { detail: safeDetail } : undefined);
  } catch {
    performanceApi.mark(name);
  }

  if (typeof window !== "undefined") {
    window.__QV_PERFORMANCE__ = readQuantVisionPerformance();
  }
  return true;
}

