export const QV_PERFORMANCE_MARKS = Object.freeze({
  appMounted: "qv:app-mounted",
  terminalVisible: "qv:terminal-visible",
  chartDataReady: "qv:chart-data-ready",
  chartPainted: "qv:chart-painted",
});

const MAX_RUNTIME_SAMPLES = 200;
const runtimeSamples = {
  longTaskMs: [],
  realtimeTransportMs: [],
  realtimePaintMs: [],
  measures: {},
  resources: {},
};
let performanceObserver = null;
let realtimePaintFrame = null;
let pendingRealtimePaintStartedAt = null;

function getPerformanceApi() {
  return typeof globalThis.performance === "object" ? globalThis.performance : null;
}

function readPerformanceNow() {
  const performanceApi = getPerformanceApi();
  if (typeof performanceApi?.now !== "function") return 0;
  try {
    return Number(performanceApi.now()) || 0;
  } catch {
    return 0;
  }
}

function appendBounded(target, value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return;
  target.push(numeric);
  if (target.length > MAX_RUNTIME_SAMPLES) {
    target.splice(0, target.length - MAX_RUNTIME_SAMPLES);
  }
}

function percentile(values, ratio) {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const index = Math.max(0, Math.min(sorted.length - 1, Math.ceil((sorted.length - 1) * ratio)));
  return Number(sorted[index].toFixed(2));
}

function summarize(values) {
  return {
    count: values.length,
    p50_ms: percentile(values, 0.5),
    p95_ms: percentile(values, 0.95),
    max_ms: values.length ? Number(Math.max(...values).toFixed(2)) : null,
  };
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
  result.runtime = {
    sample_capacity: MAX_RUNTIME_SAMPLES,
    long_tasks: summarize(runtimeSamples.longTaskMs),
    realtime_transport: summarize(runtimeSamples.realtimeTransportMs),
    realtime_paint: summarize(runtimeSamples.realtimePaintMs),
    measures: { ...runtimeSamples.measures },
    resources: Object.fromEntries(
      Object.entries(runtimeSamples.resources).map(([key, value]) => [key, { ...value }]),
    ),
  };
  return result;
}

function publishPerformanceSnapshot() {
  if (typeof window !== "undefined") {
    window.__QV_PERFORMANCE__ = readQuantVisionPerformance();
  }
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

  publishPerformanceSnapshot();
  return true;
}

export function startQuantVisionPerformanceObserver(ObserverCtor = globalThis.PerformanceObserver) {
  if (performanceObserver) return true;
  if (typeof ObserverCtor !== "function") return false;

  const supported = Array.isArray(ObserverCtor.supportedEntryTypes)
    ? ObserverCtor.supportedEntryTypes
    : ["longtask", "measure", "resource"];
  const entryTypes = ["longtask", "measure", "resource"].filter((type) => supported.includes(type));
  if (!entryTypes.length) return false;

  try {
    performanceObserver = new ObserverCtor((list) => {
      for (const entry of list.getEntries()) {
        if (entry.entryType === "longtask") {
          appendBounded(runtimeSamples.longTaskMs, entry.duration);
        } else if (entry.entryType === "measure" && String(entry.name || "").startsWith("qv:")) {
          runtimeSamples.measures[String(entry.name).slice(0, 64)] = Number(Number(entry.duration || 0).toFixed(2));
        } else if (entry.entryType === "resource") {
          const key = String(entry.initiatorType || "other").slice(0, 24) || "other";
          const bucket = runtimeSamples.resources[key] || { count: 0, transfer_bytes: 0, duration_ms: 0 };
          bucket.count += 1;
          bucket.transfer_bytes += Math.max(0, Number(entry.transferSize || 0));
          bucket.duration_ms += Math.max(0, Number(entry.duration || 0));
          runtimeSamples.resources[key] = bucket;
        }
      }
      publishPerformanceSnapshot();
    });
    performanceObserver.observe({ entryTypes });
    return true;
  } catch {
    performanceObserver = null;
    return false;
  }
}

export function recordQuantVisionRealtimeMessage(message, {
  nowEpochMs = Date.now(),
  // Keep the method lookup separate from the call. This avoids a production
  // minification edge case that emitted an out-of-scope temporary variable.
  nowPerformanceMs = readPerformanceNow(),
  requestFrame = globalThis.requestAnimationFrame,
} = {}) {
  const sourceTimestamp = Number(message?.ts);
  const transportMs = nowEpochMs - sourceTimestamp;
  if (Number.isFinite(sourceTimestamp) && transportMs >= 0 && transportMs <= 60_000) {
    appendBounded(runtimeSamples.realtimeTransportMs, transportMs);
  }

  pendingRealtimePaintStartedAt = pendingRealtimePaintStartedAt == null
    ? Number(nowPerformanceMs)
    : Math.min(pendingRealtimePaintStartedAt, Number(nowPerformanceMs));
  if (realtimePaintFrame != null || typeof requestFrame !== "function") return;

  realtimePaintFrame = requestFrame((paintedAt) => {
    realtimePaintFrame = null;
    if (pendingRealtimePaintStartedAt != null) {
      appendBounded(runtimeSamples.realtimePaintMs, Number(paintedAt) - pendingRealtimePaintStartedAt);
    }
    pendingRealtimePaintStartedAt = null;
    publishPerformanceSnapshot();
  });
}

export function resetQuantVisionPerformanceForTests() {
  performanceObserver?.disconnect?.();
  performanceObserver = null;
  realtimePaintFrame = null;
  pendingRealtimePaintStartedAt = null;
  runtimeSamples.longTaskMs.length = 0;
  runtimeSamples.realtimeTransportMs.length = 0;
  runtimeSamples.realtimePaintMs.length = 0;
  runtimeSamples.measures = {};
  runtimeSamples.resources = {};
}
