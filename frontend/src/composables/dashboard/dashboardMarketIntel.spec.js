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
});
