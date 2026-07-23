import { describe, expect, it, vi } from "vitest";

import {
  createLazyDashboardAlerting,
  createLazyDashboardMarketIntel,
  createLazyDashboardMarketSnapshots,
  createLazyDashboardScreener,
  createLazyDashboardTradeWorkbench,
} from "./lazyDashboardSecondaryControllers";

describe("lazy dashboard secondary controllers", () => {
  it("loads screener only when an action is requested", async () => {
    const runScreener = vi.fn(async () => undefined);
    const loadModule = vi.fn(async () => ({
      createDashboardScreener: () => ({
        screenerResults: { value: { items: [{ ticker: "2330" }] } },
        screenerPresets: { value: [] },
        screenerLoading: { value: false },
        screenerFilters: { market: "TW" },
        runScreener,
      }),
    }));
    const facade = createLazyDashboardScreener({}, loadModule);

    expect(facade.screenerResults.value.items).toEqual([]);
    expect(loadModule).not.toHaveBeenCalled();
    await facade.runScreener();
    expect(runScreener).toHaveBeenCalledOnce();
    expect(facade.screenerFilters.market).toBe("TW");
  });

  it("initializes the journal only after the review controller is loaded", async () => {
    const resetJournalForm = vi.fn();
    const loadBacktestHistory = vi.fn(async () => undefined);
    const loadModule = vi.fn(async () => ({
      createDashboardTradeWorkbench: () => ({
        journalForm: { ticker: "2330" },
        resetJournalForm,
        loadBacktestHistory,
      }),
    }));
    const facade = createLazyDashboardTradeWorkbench({}, loadModule);

    expect(loadModule).not.toHaveBeenCalled();
    await facade.loadBacktestHistory();
    expect(resetJournalForm).toHaveBeenCalledOnce();
    expect(loadBacktestHistory).toHaveBeenCalledOnce();
    expect(facade.journalForm.ticker).toBe("2330");
  });

  it("keeps institutional data outside the terminal graph until requested", async () => {
    const loadInstitutionalData = vi.fn(async () => undefined);
    const loadModule = vi.fn(async () => ({
      createDashboardMarketIntel: () => ({
        institutionalDate: { value: "2026-07-23" },
        loadInstitutionalData,
      }),
    }));
    const facade = createLazyDashboardMarketIntel({}, loadModule);

    expect(loadModule).not.toHaveBeenCalled();
    await facade.loadInstitutionalData();
    expect(loadInstitutionalData).toHaveBeenCalledOnce();
  });

  it("loads alert behavior only when the alert surface is opened", async () => {
    const openAlertModal = vi.fn();
    const loadModule = vi.fn(async () => ({
      createDashboardAlerting: () => ({
        alertModalOpen: { value: false },
        alertForm: { ticker: "2330" },
        openAlertModal,
      }),
    }));
    const facade = createLazyDashboardAlerting({}, loadModule);

    expect(loadModule).not.toHaveBeenCalled();
    await facade.openAlertModal();
    expect(openAlertModal).toHaveBeenCalledOnce();
  });

  it("loads market snapshots only for overview consumers", async () => {
    const loadMarketSnapshots = vi.fn(async () => undefined);
    const loadModule = vi.fn(async () => ({
      createDashboardMarketSnapshots: () => ({ loadMarketSnapshots }),
    }));
    const facade = createLazyDashboardMarketSnapshots({}, loadModule);

    expect(facade.marketSnapshots.value).toEqual([]);
    expect(loadModule).not.toHaveBeenCalled();
    await facade.loadMarketSnapshots();
    expect(loadMarketSnapshots).toHaveBeenCalledOnce();
  });
});
