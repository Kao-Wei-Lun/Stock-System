<template>
  <div class="tw-heatmap-container" style="position: relative;">
    <div v-if="loading" class="heatmap-loading">載入中...</div>
    <div v-else-if="error" class="heatmap-error">{{ error }}</div>
    <template v-else>
      <div v-if="activeSector" class="heatmap-back-btn" @click="clearSector">
        <span class="icon">&larr;</span> 返回全部產業
      </div>
      <v-chart ref="chartRef" class="echarts-heatmap" :option="chartOption" autoresize @click="handleChartClick" />
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, provide } from "vue";
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { TreemapChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import VChart, { THEME_KEY } from "vue-echarts";
import { secureFetch } from "../../utils/lanAccess";

use([CanvasRenderer, TreemapChart, TooltipComponent]);

provide(THEME_KEY, "dark");

const props = defineProps({
  mode: {
    type: String,
    default: "stocks" // "stocks" or "indices"
  }
});

const emit = defineEmits(["select-ticker"]);

const loading = ref(true);
const error = ref(null);
const marketData = ref([]);
const chartRef = ref(null);
const activeSector = ref(null);

function clearSector() {
  activeSector.value = null;
}
const HEATMAP_SURFACE = "#131722";
const SECTOR_BORDER = "rgba(255, 255, 255, 0.08)";
const TILE_BORDER = "rgba(255, 255, 255, 0.08)";
const HEADER_SURFACE = "rgba(10, 13, 18, 0.92)";
const UPPER_LABEL_TEXT = "#f5f7fa";
const BREADCRUMB_TEXT = "#d7fbff";
const TOOLTIP_SURFACE = "rgba(12, 16, 24, 0.96)";
const TOOLTIP_BORDER = "rgba(139, 149, 167, 0.26)";

function formatNumber(num) {
  const value = Number(num || 0);
  if (!value) return "0";
  if (value >= 100000000) return (value / 100000000).toFixed(2) + " 億";
  if (value >= 10000) return (value / 10000).toFixed(2) + " 萬";
  return value.toLocaleString();
}

function formatPrice(price) {
  const value = Number(price);
  if (!Number.isFinite(value)) return "--";
  const digits = value >= 1000 ? 0 : 2;
  return value.toLocaleString("zh-TW", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatChange(changePct) {
  const pct = Number.parseFloat(changePct) || 0;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getColor(changePct) {
  const pct = Number.parseFloat(changePct);
  if (!Number.isFinite(pct) || pct === 0) return "#2a2e39"; // 平盤
  if (pct >= 3) return "#f23645"; // 強漲（台股紅漲）
  if (pct > 0) return "#f7525f"; // 微漲
  if (pct <= -3) return "#089981"; // 強跌（台股綠跌）
  return "#22ab94"; // 微跌
}

const chartOption = computed(() => {
  const sectorGroups = {};

  marketData.value.forEach((item) => {
    const sector = item.sector || "未分類";
    const tradeValue = Number(item.trade_value || 0);
    const sizeValue = tradeValue > 0 ? tradeValue : 1;
    const change = Number(item.change_pct || 0);
    const symbolName = item.name || item.ticker || "未命名";

    if (!sectorGroups[sector]) {
      sectorGroups[sector] = {
        name: sector,
        value: 0,
        children: [],
      };
    }

    sectorGroups[sector].value += sizeValue;
    sectorGroups[sector].children.push({
      name: symbolName,
      value: sizeValue,
      ticker: item.ticker,
      symbolName,
      sectorName: sector,
      changePct: change,
      price: item.price,
      tradeValue,
      itemStyle: {
        color: getColor(change),
      },
    });
  });

  let treemapData = Object.values(sectorGroups);
  
  if (activeSector.value && sectorGroups[activeSector.value]) {
    treemapData = [sectorGroups[activeSector.value]];
  }

  const chartInstance = chartRef.value;

  return {
    backgroundColor: "transparent",
    tooltip: {
      formatter: function (info) {
        const data = info.data;
        if (!data || !data.ticker) return "";

        const color = data.itemStyle?.color || getColor(data.changePct);

        return `
          <div style="min-width: 210px; padding: 12px 14px;">
            <div style="margin-bottom: 8px; color: #8b95a7; font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;">
              ${escapeHtml(data.sectorName || "台股熱力圖")}
            </div>
            <div style="display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 10px;">
              <div style="font-size: 15px; font-weight: 700; color: #f5f7fa;">
                ${escapeHtml(data.symbolName)}
              </div>
              <div style="font-size: 12px; color: #8b95a7;">
                ${escapeHtml(data.ticker)}
              </div>
            </div>
            <div style="display: grid; gap: 6px; color: #d1d4dc; font-size: 12px;">
              <div style="display: flex; justify-content: space-between; gap: 12px;">
                <span>股價</span>
                <strong style="color: #f5f7fa;">${escapeHtml(formatPrice(data.price))}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; gap: 12px;">
                <span>漲跌</span>
                <strong style="color: ${color};">${escapeHtml(formatChange(data.changePct))}</strong>
              </div>
              <div style="display: flex; justify-content: space-between; gap: 12px;">
                <span>成交值</span>
                <strong style="color: #f5f7fa;">${escapeHtml(formatNumber(data.tradeValue))}</strong>
              </div>
            </div>
          </div>
        `.trim();
      },
      backgroundColor: TOOLTIP_SURFACE,
      borderColor: TOOLTIP_BORDER,
      borderWidth: 1,
      textStyle: { color: "#d1d4dc" },
      padding: 0,
      extraCssText: "border-radius: 14px; box-shadow: 0 20px 48px rgba(0, 0, 0, 0.35); overflow: hidden; backdrop-filter: blur(8px);",
    },
    series: [
      {
        type: "treemap",
        width: "100%",
        height: "100%",
        roam: true,
        nodeClick: false, // Disabling automatic zoom; will manually dispatch action
        sort: "desc",
        animationDurationUpdate: 220,
        breadcrumb: {
          show: false, // Use our custom Vue back button instead
        },
        levels: [
          {
            itemStyle: {
              color: "transparent",
              borderColor: "transparent",
              borderWidth: 0,
              gapWidth: 2,
            },
          },
          {
            upperLabel: {
              show: true,
              height: 24,
              formatter: ({ name }) => `${name}`,
              color: "#a3a6af",
              backgroundColor: "#131722",
              padding: [0, 8],
              fontWeight: 600,
              fontSize: 12,
              lineHeight: 24,
              align: 'left',
              overflow: "truncate",
            },
            itemStyle: {
              color: "transparent",
              borderColor: "#1e222d",
              borderWidth: 1,
              gapWidth: 2,
            }
          },
          {
            label: {
              show: true,
              formatter: ({ data }) => `${data.symbolName}\n${formatChange(data.changePct)}`,
              color: "#ffffff",
              fontSize: 11,
              fontWeight: 500,
              lineHeight: 16,
              overflow: "truncate",
              minMargin: 3,
            },
            itemStyle: {
              borderColor: "#131722",
              borderWidth: 1,
              gapWidth: 0
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
      secureFetch("/api/fubon/snapshot/TSE"),
      secureFetch("/api/fubon/snapshot/OTC")
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

    // Filter by mode
    if (props.mode === "stocks") {
      data = data.filter(item => item.sector && item.sector !== "未分類");
    } else if (props.mode === "indices") {
      data = data.filter(item => !item.sector || item.sector === "未分類");
      // Since they are all "未分類", we can assign them to a single visual block or no block at all.
      // To prevent a single giant "未分類" border, we rename it to "大盤指數與 ETF"
      data.forEach(item => item.sector = "大盤指數與 ETF");
    }

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
  if (params && params.data) {
    if (params.data.ticker) {
      // 點擊到底層個股：觸發選擇股票事件，開啟相關視窗
      emit("select-ticker", {
        ticker: params.data.ticker,
        name: params.data.symbolName,
      });
    } else if (params.treePathInfo && params.treePathInfo.length === 2 && !activeSector.value) {
      // 點擊到外層（產業板塊），設定 activeSector 來過濾資料
      activeSector.value = params.name;
    }
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
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.04);
  background:
    radial-gradient(circle at top, rgba(123, 231, 255, 0.08), transparent 38%),
    #131722;
}

.heatmap-loading,
.heatmap-error {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #8b95a7;
  font-size: 13px;
  letter-spacing: 0.04em;
}

.heatmap-error {
  color: #ff8a9d;
}

.echarts-heatmap {
  width: 100%;
  height: 100%;
  min-height: inherit;
}

.heatmap-back-btn {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: rgba(10, 13, 18, 0.85);
  border: 1px solid rgba(123, 231, 255, 0.2);
  border-radius: 6px;
  color: #a3a6af;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  backdrop-filter: blur(4px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  transition: all 0.2s;
}

.heatmap-back-btn:hover {
  color: #d7fbff;
  border-color: rgba(123, 231, 255, 0.5);
  background: rgba(10, 13, 18, 1);
}
</style>
