import { describe, expect, it, vi } from "vitest";

import { createDashboardBootstrap } from "./dashboardBootstrap";


describe("dashboardBootstrap", () => {
  it("deduplicates simultaneous requests for the same resource query", async () => {
    let resolveRequest;
    const loader = vi.fn(() => new Promise((resolve) => { resolveRequest = resolve; }));
    const bootstrap = createDashboardBootstrap();

    const first = bootstrap.ensure("watchlist", loader, { queryKey: "compact" });
    const second = bootstrap.ensure("watchlist", loader, { queryKey: "compact" });
    await Promise.resolve();
    resolveRequest({ groups: [] });

    await expect(Promise.all([first, second])).resolves.toEqual([{ groups: [] }, { groups: [] }]);
    expect(loader).toHaveBeenCalledTimes(1);
    expect(bootstrap.resources.watchlist.status).toBe("ready");
    expect(bootstrap.resources.watchlist.loadedAt).toBeTruthy();
  });

  it("does not let an older query overwrite the newer resource state", async () => {
    let resolveOld;
    let resolveNew;
    const bootstrap = createDashboardBootstrap();
    const oldRequest = bootstrap.ensure("kline", () => new Promise((resolve) => { resolveOld = resolve; }), { queryKey: "A" });
    const newRequest = bootstrap.ensure("kline", () => new Promise((resolve) => { resolveNew = resolve; }), { queryKey: "B" });
    await Promise.resolve();

    resolveNew("new");
    await newRequest;
    resolveOld("old");
    await oldRequest;

    expect(bootstrap.resources.kline.queryKey).toBe("B");
    expect(bootstrap.resources.kline.value).toBe("new");
  });

  it("isolates optional resource failures from other resources", async () => {
    const bootstrap = createDashboardBootstrap();

    const results = await Promise.allSettled([
      bootstrap.ensure("kline", async () => "ready"),
      bootstrap.ensure("notifications", async () => { throw new Error("offline"); }),
    ]);

    expect(results.map((result) => result.status)).toEqual(["fulfilled", "rejected"]);
    expect(bootstrap.resources.kline.status).toBe("ready");
    expect(bootstrap.resources.notifications.status).toBe("error");
  });

  it("defers non-critical work until the idle scheduler runs", async () => {
    let scheduled;
    const loader = vi.fn().mockResolvedValue("done");
    const bootstrap = createDashboardBootstrap({
      scheduleIdle: (callback) => {
        scheduled = callback;
        return { type: "test", id: 1 };
      },
    });

    bootstrap.defer("notifications", loader);
    expect(loader).not.toHaveBeenCalled();
    scheduled();
    await Promise.resolve();
    await Promise.resolve();

    expect(loader).toHaveBeenCalledTimes(1);
  });
});

