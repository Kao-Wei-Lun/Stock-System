import { fetchWithPolicy } from "../utils/requestPolicy";

export async function getOperationalMetricsHistory({
  hours = 24,
  resolution = "auto",
  timeoutMs = import.meta.env.MODE === "test" ? 0 : 15_000,
} = {}) {
  const params = new URLSearchParams({
    hours: String(hours),
    resolution: String(resolution),
  });
  const response = await fetchWithPolicy(
    `/api/system/metrics/history?${params.toString()}`,
    {},
    { timeoutMs, retries: import.meta.env.MODE === "test" ? 0 : 1 },
  );
  const contentType = response.headers?.get?.("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(payload?.detail || `HTTP ${response.status}`);
  }
  return payload;
}
