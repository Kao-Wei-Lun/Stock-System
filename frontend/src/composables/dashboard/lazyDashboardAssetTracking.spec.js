import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

import { createLazyDashboardAssetTracking } from "./lazyDashboardAssetTracking";

describe("createLazyDashboardAssetTracking", () => {
  it("does not load the asset controller until its first action", async () => {
    const loadModule = vi.fn(async () => ({
      createDashboardAssetTracking: () => ({
        assetLoading: ref(false),
        assetError: ref(""),
        assetAccounts: ref([{ id: 1 }]),
        loadAssetTrackingData: vi.fn(async () => "loaded"),
      }),
    }));
    const facade = createLazyDashboardAssetTracking({}, loadModule);

    expect(loadModule).not.toHaveBeenCalled();
    expect(facade.assetAccounts.value).toEqual([]);

    await expect(facade.loadAssetTrackingData()).resolves.toBe("loaded");
    expect(loadModule).toHaveBeenCalledOnce();
    expect(facade.assetAccounts.value).toEqual([{ id: 1 }]);
  });

  it("deduplicates concurrent dynamic imports and allows retry after failure", async () => {
    const createController = () => ({
      loadAssetTrackingData: vi.fn(async () => undefined),
    });
    const loadModule = vi.fn()
      .mockRejectedValueOnce(new Error("chunk failed"))
      .mockResolvedValue({ createDashboardAssetTracking: createController });
    const facade = createLazyDashboardAssetTracking({}, loadModule);

    await expect(facade.loadAssetTrackingData()).rejects.toThrow("chunk failed");
    await expect(Promise.all([
      facade.loadAssetTrackingData(),
      facade.loadAssetTrackingData(),
    ])).resolves.toEqual([undefined, undefined]);
    expect(loadModule).toHaveBeenCalledTimes(2);
  });
});
