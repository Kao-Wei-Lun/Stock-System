const DEFAULT_COMPARE_COLORS = ["#ffd166", "#ff8c42", "#9b6dff", "#00d4ff", "#ff4d6a"];

export function normalizeComparisonTickers(targetTickers, mainTicker, normalizeTicker, limit = 5) {
  const normalizedMainTicker = normalizeTicker(mainTicker);
  return [...new Set(
    (targetTickers || [])
      .map((ticker) => normalizeTicker(ticker))
      .filter((ticker) => ticker && ticker !== normalizedMainTicker),
  )].slice(0, limit);
}

export function createDashboardComparison({
  dashboardApi,
  compareTickers,
  rawCompareSeries,
  comparisonMode,
  currentTicker,
  currentPeriod,
  currentInterval,
  klineDisplayMode,
  normalizeTicker,
  isFutoptTicker,
  resolveFutoptInterval,
  resolveFutoptPeriod,
  resolveTimeframeInterval,
  getEffectiveKlineDisplayMode,
  getExpandedFetchPeriod,
  getDisplayNameForTicker,
  getRequestSequence,
  pushNotification,
  colors = DEFAULT_COMPARE_COLORS,
}) {
  async function loadComparisonSeries(
    targetTickers = compareTickers.value,
    { requestToken = null } = {},
  ) {
    const normalizedTickers = normalizeComparisonTickers(
      targetTickers,
      currentTicker.value,
      normalizeTicker,
    );
    compareTickers.value = normalizedTickers;

    if (!normalizedTickers.length) {
      rawCompareSeries.value = [];
      return;
    }

    const mainTickerIsFutopt = isFutoptTicker(currentTicker.value);
    const resolvedInterval = mainTickerIsFutopt
      ? resolveFutoptInterval(currentInterval.value)
      : resolveTimeframeInterval(currentPeriod.value, currentInterval.value);
    const displayMode = getEffectiveKlineDisplayMode(klineDisplayMode.value, resolvedInterval);
    const fetchPeriod = mainTickerIsFutopt
      ? resolveFutoptPeriod(currentPeriod.value, resolvedInterval)
      : getExpandedFetchPeriod(currentPeriod.value, displayMode);

    const results = await Promise.allSettled(
      normalizedTickers.map(async (ticker, index) => {
        const payload = isFutoptTicker(ticker)
          ? await dashboardApi.getFutoptOhlc(ticker, {
            period: resolveFutoptPeriod(fetchPeriod, resolvedInterval),
            interval: resolveFutoptInterval(resolvedInterval),
            refreshMode: "background",
            limit: 400,
            warmup: 250,
          })
          : await dashboardApi.getOhlc(ticker, {
            period: fetchPeriod,
            interval: resolvedInterval,
            limit: 400,
            warmup: 250,
          });
        const data = payload.data || [];
        const firstClose = data.find((row) => row.close != null)?.close ?? null;
        const lastClose = data.length ? data[data.length - 1].close : null;
        const changePct = firstClose && lastClose ? ((lastClose - firstClose) / firstClose) * 100 : 0;
        return {
          ticker,
          name: getDisplayNameForTicker(ticker),
          color: colors[index % colors.length],
          changePct,
          data,
        };
      }),
    );

    if (requestToken != null && requestToken !== getRequestSequence()) return;
    rawCompareSeries.value = results
      .filter((result) => result.status === "fulfilled" && result.value.data.length)
      .map((result) => result.value);
  }

  async function addCompareTicker(ticker) {
    const normalized = normalizeTicker(ticker);
    if (!normalized) return;
    if (normalized === normalizeTicker(currentTicker.value)) {
      pushNotification({ icon: "ℹ", title: "主圖已是這檔股票", msg: normalized });
      return;
    }
    if (compareTickers.value.includes(normalized)) return;
    if (compareTickers.value.length >= 5) {
      pushNotification({
        icon: "⚠️",
        title: "比較標的已達上限",
        msg: "最多可同時比較 5 檔股票",
        type: "error",
      });
      return;
    }
    await loadComparisonSeries([...compareTickers.value, normalized]);
  }

  async function removeCompareTicker(ticker) {
    await loadComparisonSeries(
      compareTickers.value.filter((item) => item !== normalizeTicker(ticker)),
    );
  }

  function clearCompareTickers() {
    compareTickers.value = [];
    rawCompareSeries.value = [];
  }

  function setComparisonMode(mode) {
    comparisonMode.value = mode === "price" ? "price" : "percent";
  }

  return {
    addCompareTicker,
    clearCompareTickers,
    loadComparisonSeries,
    removeCompareTicker,
    setComparisonMode,
  };
}
