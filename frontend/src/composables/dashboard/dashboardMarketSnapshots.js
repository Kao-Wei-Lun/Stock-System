import { computed, ref } from "vue";

function normalizeRows(payload) {
  return Array.isArray(payload?.data) ? payload.data : [];
}

function buildBreadthCard(label, market, payload) {
  const summary = payload?.summary || {};
  const total = Number(summary.count || 0);
  const advancers = Number(summary.advancers || 0);
  const decliners = Number(summary.decliners || 0);
  const unchanged = Number(summary.unchanged || 0);
  return {
    key: market,
    label,
    market,
    total,
    advancers,
    decliners,
    unchanged,
    date: payload?.date || null,
    time: payload?.time || null,
    totalTradeValue: Number(summary.total_trade_value || 0),
  };
}

function sortMovers(items, direction) {
  const multiplier = direction === "down" ? 1 : -1;
  return [...items].sort((left, right) => {
    const leftValue = Number(left?.change_pct ?? left?.change ?? 0);
    const rightValue = Number(right?.change_pct ?? right?.change ?? 0);
    return (leftValue - rightValue) * multiplier;
  });
}

export function createDashboardMarketSnapshots({
  dashboardApi,
  pushNotification,
} = {}) {
  const marketSnapshots = ref({ TSE: null, OTC: null });
  const marketStrongMovers = ref([]);
  const marketWeakMovers = ref([]);
  const marketActiveLeaders = ref([]);
  const marketSnapshotLoading = ref(false);
  const marketSnapshotError = ref("");

  const marketBreadthCards = computed(() => ([
    buildBreadthCard("上市", "TSE", marketSnapshots.value.TSE),
    buildBreadthCard("上櫃", "OTC", marketSnapshots.value.OTC),
  ]));

  async function loadMarketSnapshots(forceRefresh = false) {
    marketSnapshotLoading.value = true;
    marketSnapshotError.value = "";
    try {
      const [tseSnapshot, otcSnapshot, tseUp, otcUp, tseDown, otcDown, tseActives, otcActives] = await Promise.all([
        dashboardApi.getFubonSnapshotSummary("TSE", { refresh: forceRefresh }),
        dashboardApi.getFubonSnapshotSummary("OTC", { refresh: forceRefresh }),
        dashboardApi.getFubonMovers("TSE", { direction: "up", change: "percent", limit: 10, refresh: forceRefresh }),
        dashboardApi.getFubonMovers("OTC", { direction: "up", change: "percent", limit: 10, refresh: forceRefresh }),
        dashboardApi.getFubonMovers("TSE", { direction: "down", change: "percent", limit: 10, refresh: forceRefresh }),
        dashboardApi.getFubonMovers("OTC", { direction: "down", change: "percent", limit: 10, refresh: forceRefresh }),
        dashboardApi.getFubonActives("TSE", { trade: "value", limit: 10, refresh: forceRefresh }),
        dashboardApi.getFubonActives("OTC", { trade: "value", limit: 10, refresh: forceRefresh }),
      ]);

      marketSnapshots.value = {
        TSE: tseSnapshot || null,
        OTC: otcSnapshot || null,
      };
      marketStrongMovers.value = sortMovers(
        [...normalizeRows(tseUp), ...normalizeRows(otcUp)],
        "up",
      ).slice(0, 10);
      marketWeakMovers.value = sortMovers(
        [...normalizeRows(tseDown), ...normalizeRows(otcDown)],
        "down",
      ).slice(0, 10);
      marketActiveLeaders.value = [...normalizeRows(tseActives), ...normalizeRows(otcActives)]
        .sort((left, right) => Number(right?.trade_value || 0) - Number(left?.trade_value || 0))
        .slice(0, 10);
    } catch (error) {
      console.error(error);
      marketSnapshotError.value = error.message || "無法載入市場快照";
      if (forceRefresh) {
        pushNotification?.({
          icon: "⚠️",
          title: "市場快照載入失敗",
          msg: marketSnapshotError.value,
          type: "error",
        });
      }
    } finally {
      marketSnapshotLoading.value = false;
    }
  }

  return {
    marketSnapshots,
    marketStrongMovers,
    marketWeakMovers,
    marketActiveLeaders,
    marketSnapshotLoading,
    marketSnapshotError,
    marketBreadthCards,
    loadMarketSnapshots,
  };
}
