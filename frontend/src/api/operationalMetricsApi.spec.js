import { afterEach, describe, expect, it, vi } from "vitest";

import { getOperationalMetricsHistory } from "./operationalMetricsApi";

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => "application/json" },
    json: async () => payload,
  };
}

describe("operationalMetricsApi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests bounded history without adding it to the initial dashboard bundle", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ points: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const payload = await getOperationalMetricsHistory({ hours: 24, resolution: "raw" });

    expect(payload).toEqual({ points: [] });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/system/metrics/history?hours=24&resolution=raw",
      {},
    );
  });

  it("returns the backend-safe error message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "暫時無法讀取" }, 503)));

    await expect(getOperationalMetricsHistory()).rejects.toThrow("暫時無法讀取");
  });
});
