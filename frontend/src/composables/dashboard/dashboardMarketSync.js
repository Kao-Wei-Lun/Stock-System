export function createDashboardMarketSync({
  dashboardApi,
  apiFetch,
  currentTicker,
  currentPeriod,
  currentInterval,
  syncingCurrent,
  syncingAll,
  normalizeTicker,
  isFutoptTicker,
  applyQuote,
  ensureKline,
  loadWatchlist,
  loadEventCalendar,
  loadMarketSnapshots,
  loadMacroDashboard,
  loadTickerIntelligence,
  pushNotification,
}) {
  async function syncCurrentTicker() {
    syncingCurrent.value = true;
    try {
      const normalizedTicker = normalizeTicker(currentTicker.value);
      let result;
      let refreshedQuote = null;
      if (isFutoptTicker(normalizedTicker)) {
        result = await dashboardApi.syncFutoptOhlc(normalizedTicker, {
          period: currentPeriod.value,
          interval: currentInterval.value,
        });
      } else {
        const [historyResult, quoteResult] = await Promise.all([
          apiFetch(`/api/sync/${normalizedTicker}`, { method: "POST" }),
          dashboardApi.refreshQuote(normalizedTicker),
        ]);
        result = historyResult;
        refreshedQuote = quoteResult;
        if (refreshedQuote) applyQuote(refreshedQuote);
      }
      const quoteStatus = refreshedQuote?.refresh_status;
      const quoteStatusText = quoteStatus === "throttled"
        ? "；報價已節流並保留最近快照"
        : quoteStatus === "backoff"
          ? "；供應商退避中，暫用最近快照"
          : refreshedQuote
            ? "；報價已刷新"
            : "";
      pushNotification({
        icon: "✅",
        title: "同步完成",
        msg: `${currentTicker.value} 已同步 ${result.synced ?? result.row_count ?? 0} 筆${quoteStatusText}`,
        type: "success",
      });
      await ensureKline(
        currentTicker.value,
        currentPeriod.value,
        currentInterval.value,
        { force: true },
      );
    } catch (error) {
      pushNotification({ icon: "⚠️", title: "同步失敗", msg: "請檢查網路連線", type: "error" });
    } finally {
      syncingCurrent.value = false;
    }
  }

  async function syncAll() {
    syncingAll.value = true;
    pushNotification({
      icon: "📥",
      title: "全量同步開始",
      msg: "正在同步股票與大盤最新資料，這可能需要幾分鐘",
    });
    try {
      const result = await apiFetch("/api/sync/all?period=1y&interval=1d", {
        method: "POST",
        retries: 1,
        retryDelayMs: 1200,
      });
      await Promise.all([
        loadWatchlist(),
        ensureKline(
          currentTicker.value,
          currentPeriod.value,
          currentInterval.value,
          { force: true },
        ),
        loadEventCalendar(true),
        loadMarketSnapshots(true),
        loadMacroDashboard(true),
        loadTickerIntelligence(currentTicker.value, true),
      ]);
      pushNotification({
        icon: result.failure_count ? "⚠️" : "✅",
        title: result.failure_count ? "同步部分完成" : "同步完成",
        msg: `已同步 ${result.success_count} 檔，失敗 ${result.failure_count} 檔，共更新 ${Number(result.total_rows || 0).toLocaleString()} 筆資料`,
        type: result.failure_count ? "warning" : "success",
      });
    } catch (error) {
      pushNotification({
        icon: "⚠️",
        title: "全量同步失敗",
        msg: error.message || "請稍後再試",
        type: "error",
      });
    } finally {
      syncingAll.value = false;
    }
  }

  return {
    syncAll,
    syncCurrentTicker,
  };
}
