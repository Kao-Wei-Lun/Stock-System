import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchWithPolicy } from "./requestPolicy";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("fetchWithPolicy", () => {
  it("aborts a timed-out request and returns a retryable categorized error", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        reject(new DOMException("aborted", "AbortError"));
      });
    })));

    const pending = fetchWithPolicy("/api/slow", {}, { timeoutMs: 25 });
    const assertion = expect(pending).rejects.toMatchObject({
      name: "TimeoutError",
      code: "QV_API_TIMEOUT",
      retryable: true,
    });
    await vi.advanceTimersByTimeAsync(25);

    await assertion;
  });

  it("retries one idempotent GET timeout but never retries a POST", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockResolvedValueOnce({ ok: true }));

    await expect(fetchWithPolicy("/api/read", {}, {
      timeoutMs: 0,
      retries: 1,
      retryDelayMs: 0,
    })).resolves.toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledTimes(2);

    fetch.mockClear();
    fetch.mockRejectedValue(new TypeError("network down"));
    await expect(fetchWithPolicy("/api/write", { method: "POST" }, {
      timeoutMs: 0,
      retries: 3,
    })).rejects.toThrow("network down");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("forwards route-switch aborts without retrying stale requests", async () => {
    const controller = new AbortController();
    vi.stubGlobal("fetch", vi.fn((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        reject(new DOMException("aborted", "AbortError"));
      });
    })));

    const pending = fetchWithPolicy("/api/ohlc/OLD", { signal: controller.signal }, {
      timeoutMs: 5_000,
      retries: 1,
    });
    controller.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
