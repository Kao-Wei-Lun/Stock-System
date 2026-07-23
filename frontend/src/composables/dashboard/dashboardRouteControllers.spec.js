import { describe, expect, it, vi } from "vitest";

import { createDashboardRouteControllers } from "./dashboardRouteControllers";

describe("dashboardRouteControllers", () => {
  it("activates only the selected route and disposes the previous controller", async () => {
    const terminal = { activate: vi.fn(), deactivate: vi.fn(), dispose: vi.fn() };
    const assets = { activate: vi.fn(), deactivate: vi.fn(), dispose: vi.fn() };
    const registry = createDashboardRouteControllers({ terminal, assets, overview: {} });

    await registry.activate("terminal");
    expect(terminal.activate).toHaveBeenCalledOnce();
    expect(assets.activate).not.toHaveBeenCalled();

    await registry.activate("assets");
    expect(terminal.deactivate).toHaveBeenCalledOnce();
    expect(assets.activate).toHaveBeenCalledOnce();
    await registry.dispose();
    expect(assets.deactivate).toHaveBeenCalledOnce();
    expect(terminal.dispose).toHaveBeenCalledOnce();
  });

  it("rejects stale rapid-route activation completion", async () => {
    let release;
    const terminal = {
      activate: vi.fn(() => new Promise((resolve) => { release = resolve; })),
      deactivate: vi.fn(),
    };
    const assets = { activate: vi.fn(), deactivate: vi.fn() };
    const registry = createDashboardRouteControllers({ terminal, assets, overview: {} });

    const first = registry.activate("terminal");
    const second = registry.activate("assets");
    release();

    expect(await first).toBe(false);
    expect(await second).toBe(true);
    expect(registry.getActiveName()).toBe("assets");
  });
});
