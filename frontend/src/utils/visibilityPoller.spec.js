import { afterEach, describe, expect, it, vi } from "vitest";

import { createVisibilityPoller } from "./visibilityPoller";

describe("createVisibilityPoller", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("waits for the prior request before scheduling the next one", async () => {
    vi.useFakeTimers();
    let release;
    const task = vi.fn(() => new Promise((resolve) => { release = resolve; }));
    const poller = createVisibilityPoller(task, { intervalMs: 1000, runImmediately: true });

    poller.start();
    await Promise.resolve();
    expect(task).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(5000);
    expect(task).toHaveBeenCalledTimes(1);

    release();
    await Promise.resolve();
    await vi.advanceTimersByTimeAsync(999);
    expect(task).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(task).toHaveBeenCalledTimes(2);
    poller.stop();
  });

  it("pauses while hidden and refreshes immediately after becoming visible", async () => {
    vi.useFakeTimers();
    let visibility = "hidden";
    vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
    const task = vi.fn().mockResolvedValue(undefined);
    const poller = createVisibilityPoller(task, { intervalMs: 1000, runImmediately: true });

    poller.start();
    await vi.advanceTimersByTimeAsync(5000);
    expect(task).not.toHaveBeenCalled();

    visibility = "visible";
    document.dispatchEvent(new Event("visibilitychange"));
    await Promise.resolve();
    expect(task).toHaveBeenCalledTimes(1);
    poller.stop();
  });

  it("continues polling after a background request fails", async () => {
    vi.useFakeTimers();
    const task = vi.fn()
      .mockRejectedValueOnce(new Error("temporary"))
      .mockResolvedValue(undefined);
    const poller = createVisibilityPoller(task, { intervalMs: 1000, runImmediately: true });

    poller.start();
    await vi.advanceTimersByTimeAsync(1000);

    expect(task).toHaveBeenCalledTimes(2);
    poller.stop();
  });
});
