import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

import { createDashboardMarketIntel } from "./dashboardMarketIntel";

describe("dashboardMarketIntel", () => {
  it("skips stock-only intelligence requests for futopt tickers", async () => {
    const getTickerEvents = vi.fn().mockResolvedValue({ items: [] });
    const getTickerNews = vi.fn().mockResolvedValue({ items: [] });
    const getFundamentals = vi.fn().mockResolvedValue({ detail: { sector: "Technology" } });
    const getTaiwanChips = vi.fn().mockResolvedValue({ detail: { ticker: "2330.TW" } });

    const marketIntel = createDashboardMarketIntel({
      storedPrefs: {},
      currentTicker: ref("MXFE6"),
      dashboardApi: {
        getTickerEvents,
        getTickerNews,
        getFundamentals,
        getTaiwanChips,
      },
      apiFetch: vi.fn(),
      pushNotification: vi.fn(),
      normalizeTicker: (ticker) => String(ticker || "").trim().toUpperCase(),
      isFutoptTicker: (ticker) => ticker === "MXFE6",
    });

    await marketIntel.loadTickerIntelligence("MXFE6", true);

    expect(getTickerEvents).toHaveBeenCalledTimes(1);
    expect(getTickerNews).toHaveBeenCalledTimes(1);
    expect(getFundamentals).not.toHaveBeenCalled();
    expect(getTaiwanChips).not.toHaveBeenCalled();
    expect(marketIntel.fundamentalsDetail.value).toBeNull();
    expect(marketIntel.taiwanChipDetail.value).toBeNull();
  });

  it("skips stock-only intelligence requests for index tickers like ^TWII", async () => {
    const getTickerEvents = vi.fn().mockResolvedValue({ items: [] });
    const getTickerNews = vi.fn().mockResolvedValue({ items: [] });
    const getFundamentals = vi.fn().mockResolvedValue({ detail: { sector: "Index" } });
    const getTaiwanChips = vi.fn().mockResolvedValue({ detail: { ticker: "^TWII" } });

    const marketIntel = createDashboardMarketIntel({
      storedPrefs: {},
      currentTicker: ref("^TWII"),
      dashboardApi: {
        getTickerEvents,
        getTickerNews,
        getFundamentals,
        getTaiwanChips,
      },
      apiFetch: vi.fn(),
      pushNotification: vi.fn(),
      normalizeTicker: (ticker) => String(ticker || "").trim().toUpperCase(),
      isFutoptTicker: () => false,
    });

    await marketIntel.loadTickerIntelligence("^TWII", true);

    expect(getTickerEvents).toHaveBeenCalledTimes(1);
    expect(getTickerNews).toHaveBeenCalledTimes(1);
    expect(getFundamentals).not.toHaveBeenCalled();
    expect(getTaiwanChips).not.toHaveBeenCalled();
    expect(marketIntel.fundamentalsDetail.value).toBeNull();
    expect(marketIntel.taiwanChipDetail.value).toBeNull();
  });

  it("loads taiwan chip history for supported tickers and refreshes the selected range", async () => {
    const getTickerEvents = vi.fn().mockResolvedValue({ items: [] });
    const getTickerNews = vi.fn().mockResolvedValue({ items: [] });
    const getFundamentals = vi.fn().mockResolvedValue({ detail: { sector: "Semiconductors" }, summary: {} });
    const getTaiwanChips = vi.fn().mockResolvedValue({
      detail: { ticker: "2330.TW", snapshot_date: "2026-04-18" },
      summary: { bias: "bullish" },
    });
    const getTaiwanChipHistory = vi.fn().mockResolvedValue({
      ticker: "2330.TW",
      latest: {
        detail: { ticker: "2330.TW", snapshot_date: "2026-04-18" },
        summary: { bias: "bullish" },
      },
      series: [
        { snapshot_date: "2026-04-17", institutional_net_buy_sell: 12000 },
        { snapshot_date: "2026-04-18", institutional_net_buy_sell: 24000 },
      ],
    });

    const marketIntel = createDashboardMarketIntel({
      storedPrefs: {},
      currentTicker: ref("2330.TW"),
      dashboardApi: {
        getTickerEvents,
        getTickerNews,
        getFundamentals,
        getTaiwanChips,
        getTaiwanChipHistory,
      },
      apiFetch: vi.fn(),
      pushNotification: vi.fn(),
      normalizeTicker: (ticker) => String(ticker || "").trim().toUpperCase(),
      isFutoptTicker: () => false,
    });

    await marketIntel.loadTickerIntelligence("2330.TW");

    expect(getTaiwanChipHistory).toHaveBeenCalledWith("2330.TW", { days: 20, refresh: false });
    expect(marketIntel.taiwanChipHistory.value?.series).toHaveLength(2);
    expect(marketIntel.taiwanChipRangeDays.value).toBe(20);

    await marketIntel.setTaiwanChipRangeDays(60);

    expect(getTaiwanChipHistory).toHaveBeenLastCalledWith("2330.TW", { days: 60, refresh: false });
    expect(marketIntel.taiwanChipRangeDays.value).toBe(60);
  });
});
