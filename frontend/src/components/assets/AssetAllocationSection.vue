<template>
  <section class="asset-card asset-card-wide asset-allocation-card">
    <div class="asset-card-head">
      <div>
        <div class="asset-card-title">資產配置</div>
        <div class="bt-trade-sub">帳戶、市場與幣別配置；產業維度待資料欄位支援後啟用</div>
      </div>
      <div class="asset-allocation-tabs">
        <button
          v-for="tab in allocationTabs"
          :key="tab.key"
          class="asset-inline-btn"
          :class="{ active: allocationTab === tab.key }"
          type="button"
          :disabled="tab.disabled"
          :data-testid="`asset-allocation-tab-${tab.key}`"
          @click="setAllocationTab(tab)"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div v-if="allocationTab === 'account' && assetAccountAllocation.length" class="asset-donut-card">
      <DeferredVChart
        class="asset-chart asset-chart-donut"
        :option="accountAllocationChartOption"
        autoresize
        @click="handleAccountAllocationClick"
      />
      <div class="asset-donut-legend">
        <button
          v-for="item in assetAccountAllocation.slice(0, 5)"
          :key="item.key"
          class="asset-donut-legend-item"
          type="button"
          @click="$emit('focus-holdings', { accountKey: item.key })"
        >
          <span class="asset-dot" :style="{ backgroundColor: paletteColorFor(assetAccountAllocation, item.key) }"></span>
          <strong>{{ item.key }}</strong>
          <small>{{ formatPercent(item.weight_pct) }}</small>
        </button>
      </div>
    </div>

    <div v-else-if="allocationTab === 'market' && assetMarketAllocation.length" class="asset-donut-card">
      <DeferredVChart
        class="asset-chart asset-chart-donut"
        :option="marketAllocationChartOption"
        autoresize
        @click="handleMarketAllocationClick"
      />
      <div class="asset-donut-legend">
        <button
          v-for="item in assetMarketAllocation"
          :key="item.key"
          class="asset-donut-legend-item"
          type="button"
          @click="$emit('focus-holdings', { marketKey: item.key })"
        >
          <span class="asset-dot" :style="{ backgroundColor: paletteColorFor(assetMarketAllocation, item.key) }"></span>
          <strong>{{ item.key }}</strong>
          <small>{{ formatPercent(item.weight_pct) }}</small>
        </button>
      </div>
    </div>

    <div v-else-if="allocationTab === 'currency' && normalizedCurrencyAllocation.length" class="asset-donut-card">
      <DeferredVChart
        class="asset-chart asset-chart-donut"
        :option="currencyAllocationChartOption"
        autoresize
      />
      <div class="asset-donut-legend">
        <div
          v-for="item in normalizedCurrencyAllocation"
          :key="item.key"
          class="asset-donut-legend-item static"
        >
          <span class="asset-dot" :style="{ backgroundColor: paletteColorFor(normalizedCurrencyAllocation, item.key) }"></span>
          <strong>{{ item.key }}</strong>
          <small>{{ formatPercent(item.weight_pct) }}</small>
        </div>
      </div>
    </div>

    <div v-else class="asset-allocation-empty" data-testid="asset-allocation-empty">
      {{ allocationEmptyMessage }}
    </div>
  </section>
</template>

<script setup>
import { computed, provide, ref } from "vue";
import { use } from "echarts/core";
import { PieChart } from "echarts/charts";
import { GraphicComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { THEME_KEY } from "vue-echarts";

import DeferredVChart from "../DeferredVChart.vue";
import {
  formatCurrency,
  formatPercent,
  numberOrZero,
  parseFiniteNumber,
} from "./assetDashboardFormatters";

use([PieChart, CanvasRenderer, GraphicComponent, TooltipComponent]);
provide(THEME_KEY, "dark");

const props = defineProps({
  assetBaseCurrency: { type: String, default: "TWD" },
  assetAccountAllocation: { type: Array, default: () => [] },
  assetMarketAllocation: { type: Array, default: () => [] },
  assetCurrencyAllocation: { type: Array, default: () => [] },
});

const emit = defineEmits(["focus-holdings"]);

const allocationTab = ref("account");

const allocationTabs = [
  { key: "account", label: "帳戶配置", disabled: false },
  { key: "market", label: "市場配置", disabled: false },
  { key: "sector", label: "產業配置", disabled: true },
  { key: "currency", label: "幣別配置", disabled: false },
];

const allocationPalette = ["#60a5fa", "#94a3b8", "#f59e0b", "#a78bfa", "#14b8a6", "#64748b", "#f97316"];

const allocationEmptyMessage = computed(() => ({
  account: "尚無帳戶配置資料。",
  market: "目前沒有可用的市場配置資料。",
  sector: "目前資料尚未提供產業配置，待後續資料欄位支援。",
  currency: "目前沒有可用的幣別配置資料。",
}[allocationTab.value] || "尚無配置資料。"));

const normalizedCurrencyAllocation = computed(() => (
  (props.assetCurrencyAllocation || [])
    .map((item) => {
      const key = String(item?.key || item?.currency || "").trim().toUpperCase();
      return {
        ...item,
        key,
        currency: key,
      };
    })
    .filter((item) => item.key && parseFiniteNumber(item.value_base) != null)
));

const accountAllocationChartOption = computed(() => buildDonutChartOption(
  props.assetAccountAllocation,
  "帳戶配置",
  formatCurrency(totalAllocationValue(props.assetAccountAllocation), props.assetBaseCurrency),
));

const marketAllocationChartOption = computed(() => buildDonutChartOption(
  props.assetMarketAllocation,
  "市場配置",
  formatCurrency(totalAllocationValue(props.assetMarketAllocation), props.assetBaseCurrency),
));

const currencyAllocationChartOption = computed(() => buildDonutChartOption(
  normalizedCurrencyAllocation.value,
  "幣別配置",
  formatCurrency(totalAllocationValue(normalizedCurrencyAllocation.value), props.assetBaseCurrency),
));

function setAllocationTab(tab) {
  if (tab.disabled) return;
  allocationTab.value = tab.key;
}

function handleAccountAllocationClick(params) {
  const accountKey = params?.data?.name;
  if (!accountKey) return;
  emit("focus-holdings", { accountKey });
}

function handleMarketAllocationClick(params) {
  const marketKey = params?.data?.name;
  if (!marketKey) return;
  emit("focus-holdings", { marketKey });
}

function buildDonutChartOption(items, title, subtitle) {
  return {
    animation: false,
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(8, 14, 22, 0.94)",
      borderColor: "rgba(148, 163, 184, 0.22)",
      textStyle: { color: "#e7f3ff" },
      formatter(params) {
        return [
          `<div class="asset-tooltip-title">${params?.data?.name || ""}</div>`,
          `<div>資產：${formatCurrency(params?.data?.value, props.assetBaseCurrency)}</div>`,
          `<div>占比：${formatPercent(params?.data?.weight_pct)}</div>`,
        ].join("");
      },
    },
    series: [
      {
        type: "pie",
        radius: ["56%", "80%"],
        center: ["50%", "48%"],
        avoidLabelOverlap: true,
        itemStyle: {
          borderColor: "#07111b",
          borderWidth: 3,
        },
        label: { show: false },
        emphasis: { scale: true, scaleSize: 10 },
        data: (items || []).map((item, index) => ({
          name: item.key,
          value: numberOrZero(item.value_base),
          weight_pct: parseFiniteNumber(item.weight_pct),
          itemStyle: { color: allocationPalette[index % allocationPalette.length] },
        })),
      },
    ],
    graphic: [
      {
        type: "text",
        left: "center",
        top: "36%",
        style: {
          text: title,
          fill: "rgba(219, 229, 240, 0.72)",
          fontSize: 12,
          fontWeight: 600,
        },
      },
      {
        type: "text",
        left: "center",
        top: "46%",
        style: {
          text: subtitle,
          fill: "rgba(219, 229, 240, 0.46)",
          fontSize: 10,
        },
      },
    ],
  };
}

function paletteColorFor(items, key) {
  const index = (items || []).findIndex((item) => item.key === key);
  return allocationPalette[index >= 0 ? index % allocationPalette.length : 0];
}

function totalAllocationValue(items) {
  return (items || []).reduce((sum, item) => sum + numberOrZero(item?.value_base), 0);
}
</script>

<style scoped>
.asset-card {
  padding: 18px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: var(--asset-radius-card, 16px);
  background: var(--asset-card-bg, #111827);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.14);
}

.asset-allocation-card {
  grid-column: 1 / -1;
}

.asset-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.asset-card-title {
  color: var(--asset-text-primary, #e5e7eb);
  font-size: 18px;
  font-weight: 800;
}

.bt-trade-sub {
  color: var(--asset-text-secondary, #94a3b8);
  font-size: 11px;
  line-height: 1.5;
}

.asset-inline-btn {
  min-height: 34px;
  padding: 7px 10px;
  border: 1px solid var(--asset-border, #1f2937);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.72);
  color: var(--asset-text-secondary, #94a3b8);
  font: inherit;
  cursor: pointer;
}

.asset-inline-btn:hover,
.asset-inline-btn.active {
  border-color: rgba(37, 99, 235, 0.4);
  background: rgba(37, 99, 235, 0.16);
  color: var(--asset-text-primary, #e5e7eb);
}

.asset-allocation-tabs {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.asset-allocation-tabs .asset-inline-btn:disabled {
  cursor: not-allowed;
  opacity: 0.44;
}

.asset-allocation-empty {
  display: grid;
  place-items: center;
  min-height: 240px;
  border: 1px dashed var(--asset-border, rgba(255, 255, 255, 0.08));
  border-radius: var(--asset-radius-card, 16px);
  color: var(--asset-text-secondary, rgba(219, 229, 240, 0.72));
  text-align: center;
}

.asset-donut-card {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(260px, 1fr);
  gap: 16px;
  align-items: center;
}

.asset-chart {
  width: 100%;
}

.asset-chart-donut {
  min-height: 280px;
}

.asset-donut-legend {
  display: grid;
  gap: 8px;
}

.asset-donut-legend-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--asset-border, rgba(255, 255, 255, 0.08));
  border-radius: 12px;
  background: rgba(8, 14, 24, 0.66);
  color: var(--asset-text-primary, #e5e7eb);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.asset-donut-legend-item:hover {
  border-color: rgba(37, 99, 235, 0.34);
  background: rgba(37, 99, 235, 0.1);
}

.asset-donut-legend-item.static {
  cursor: default;
}

.asset-donut-legend-item.static:hover {
  border-color: rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.5);
}

.asset-donut-legend-item strong {
  flex: 1;
}

.asset-donut-legend-item small {
  color: var(--asset-text-secondary, rgba(219, 229, 240, 0.64));
  font-variant-numeric: tabular-nums;
}

.asset-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  flex: 0 0 10px;
}

:deep(.asset-tooltip-title) {
  margin-bottom: 8px;
  color: #f5fbff;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 1180px) {
  .asset-donut-card {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .asset-card-head {
    display: grid;
  }

  .asset-allocation-tabs {
    justify-content: flex-start;
  }

  .asset-chart-donut {
    min-height: 260px;
  }
}
</style>
