<template>
  <div class="tw-heatmap-container">
    <div v-if="loading" class="heatmap-loading">載入中...</div>
    <div v-else-if="error" class="heatmap-error">{{ error }}</div>
    <v-chart v-else class="echarts-heatmap" :option="chartOption" autoresize @click="handleChartClick" />
  </div>
</template>

<script setup>
import { ref, onMounted, computed, provide } from "vue";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { TreemapChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import VChart, { THEME_KEY } from "vue-echarts";

use([CanvasRenderer, TreemapChart, TooltipComponent]);

provide(THEME_KEY, "dark");

const emit = defineEmits(["select-ticker"]);

const loading = ref(true);
const error = ref(null);
const marketData = ref([]);

function formatNumber(num) {
  if (!num) return "0";
  if (num >= 100000000) return (num / 100000000).toFixed(2) + " 億";
  if (num >= 10000) return (num / 10000).toFixed(2) + " 萬";
  return num.toString();
}

function getColor(changePct) {
  const pct = parseFloat(changePct) || 0;
  if (pct >= 5) return "#ee354a"; // 強漲
  if (pct > 0) return "#ff4d6a"; // 上漲
  if (pct <= -5) return "#00aa80"; // 強跌
  if (pct < 0) return "#00d9a3"; // 下跌
  return "#303e4d"; // 平盤
}

const chartOption = computed(() => {
  const sectorGroups = {};

  marketData.value.forEach((item) => {
    const sector = item.sector || "未分類";
    if (!sectorGroups[sector]) {
      sectorGroups[sector] = {
        name: sector,
        value: 0,
        children: [],
        itemStyle: { borderWidth: 3, borderColor: "#1e222d", gapWidth: 2 }
      };
    }
    const val = item.trade_value || Math.random() * 10000 + 10000;
    const change = item.change_pct || 0;
    
    sectorGroups[sector].value += val;
    sectorGroups[sector].children.push({
      name: `${item.name}\n${change > 0 ? "+" : ""}${change.toFixed(2)}%`,
      value: val,
      ticker: item.ticker,
      symbolName: item.name,
      changePct: change,
      price: item.price,
      tradeValue: item.trade_value,
      itemStyle: {
        color: getColor(change),
        borderColor: "#1e222d",
        borderWidth: 2,
        gapWidth: 1,
      },
      label: {
        show: true,
        formatter: "{b}",
        color: "#fff",
        fontSize: 13,
        fontWeight: 500,
        overflow: "truncate",
        minMargin: 2
      },
    });
  });

  const treemapData = Object.values(sectorGroups);

  return {
    backgroundColor: "transparent",
    tooltip: {
      formatter: function (info) {
        const data = info.data;
        if (!data || !data.ticker) return "";
        return `
          <div style="font-weight:bold; color:#fff; margin-bottom:4px;">
            ${data.symbolName} (${data.ticker})
          </div>
          <div>股價: ${data.price}</div>
          <div>漲跌: <span style="color:${data.itemStyle.color}">${data.changePct > 0 ? "+" : ""}${data.changePct.toFixed(2)}%</span></div>
          <div>成交值: ${formatNumber(data.tradeValue)}</div>
        `;
      },
      backgroundColor: "rgba(30, 34, 45, 0.9)",
      borderColor: "#2a2e39",
      textStyle: { color: "#d1d4dc" },
      padding: [8, 12],
    },
    series: [
      {
        type: "treemap",
        width: "100%",
        height: "100%",
        roam: true,
        nodeClick: "zoomToNode",
        breadcrumb: {
          show: true,
          itemStyle: { textStyle: { color: "#d1d4dc" } },
          emptyItemWidth: 25
        },
        levels: [
          {
            itemStyle: { borderColor: "#0e1015", borderWidth: 0, gapWidth: 2 }
          },
          {
            upperLabel: {
              show: true,
              height: 24,
              color: "#d1d4dc",
              backgroundColor: "transparent",
              fontWeight: "bold",
              fontSize: 14,
            },
            itemStyle: {
              borderColor: "#1e222d",
              borderWidth: 4,
              gapWidth: 4
            }
          },
          {
            itemStyle: {
              borderColor: "#2a2e39",
              borderWidth: 1,
              gapWidth: 1
            }
          }
        ],
        data: treemapData,
      },
    ],
  };
});

async function fetchHeatmapData() {
  try {
    loading.value = true;
    error.value = null;

    const [tseRes, otcRes] = await Promise.all([
      fetch("/api/fubon/snapshot/TSE"),
      fetch("/api/fubon/snapshot/OTC")
    ]);

    let data = [];
    if (tseRes.ok) {
      const tseData = await tseRes.json();
      data = data.concat(tseData.data || []);
    }
    if (otcRes.ok) {
      const otcData = await otcRes.json();
      data = data.concat(otcData.data || []);
    }

    // Filter out inactive stocks
    data = data.filter(item => item.trade_value > 0);

    // Sort by trade value descending to ensure biggest boxes are top
    data.sort((a, b) => (b.trade_value || 0) - (a.trade_value || 0));

    marketData.value = data;
  } catch (err) {
    error.value = "無法載入台股百大成交值資料";
    console.error("Heatmap fetch error:", err);
  } finally {
    loading.value = false;
  }
}

function handleChartClick(params) {
  if (params && params.data && params.data.ticker) {
    emit("select-ticker", {
      ticker: params.data.ticker,
      name: params.data.symbolName,
    });
  }
}

onMounted(() => {
  fetchHeatmapData();
});
</script>

<style scoped>
.tw-heatmap-container {
  width: 100%;
  height: 100%;
  min-height: 260px;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: var(--color-bg-elevated);
}

.heatmap-loading,
.heatmap-error {
  color: var(--color-text-muted);
  font-size: 14px;
}

.echarts-heatmap {
  width: 100%;
  height: 100%;
  min-height: inherit;
}
</style>
