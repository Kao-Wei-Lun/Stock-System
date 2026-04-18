<template>
  <div class="institutional-section">
    <div class="institutional-section-head">
      <div>
        <div class="ind-group-title">區間趨勢圖</div>
        <div class="institutional-section-note">同一段時間內一起看外資、投信、自營商、法人合計與股價收盤變化。</div>
      </div>
      <div class="chip-legend">
        <span v-for="item in lineSeries" :key="item.key" class="chip-legend-item">
          <span class="chip-legend-dot" :style="{ background: item.color }"></span>
          {{ item.label }}
        </span>
        <span class="chip-legend-item">
          <span class="chip-legend-dot price"></span>
          收盤價
        </span>
      </div>
    </div>

    <div v-if="!hasSeries" class="institutional-card institutional-empty">
      目前還沒有足夠的區間資料可以畫出籌碼變化。
    </div>
    <div v-else class="institutional-card chip-trend-panel">
      <svg class="chip-trend-svg" viewBox="0 0 760 340" preserveAspectRatio="none" role="img" aria-label="個股籌碼區間趨勢圖">
        <g>
          <line
            v-for="y in chartGuides"
            :key="`guide-${y}`"
            x1="56"
            :y1="y"
            x2="732"
            :y2="y"
            class="chip-grid-line"
          />
          <line x1="56" :y1="zeroLineY" x2="732" :y2="zeroLineY" class="chip-zero-line" />
          <line
            v-for="y in priceGuides"
            :key="`price-guide-${y}`"
            x1="56"
            :y1="y"
            x2="732"
            :y2="y"
            class="chip-grid-line is-price"
          />
        </g>

        <g>
          <polyline
            v-for="item in lineSeries"
            :key="item.key"
            :points="item.points"
            fill="none"
            :stroke="item.color"
            :stroke-width="item.key === 'institutional_net_buy_sell' ? 3.6 : 2.2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <polyline
            v-if="pricePoints"
            :points="pricePoints"
            fill="none"
            stroke="#ffd166"
            stroke-width="2.2"
            stroke-dasharray="5 4"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </g>

        <g class="chip-axis-labels">
          <text x="20" y="42">{{ formatSigned(maxMetric) }}</text>
          <text x="20" :y="zeroLineY + 4">0</text>
          <text x="20" y="224">{{ formatSigned(minMetric) }}</text>
          <text x="20" y="278">{{ priceHighLabel }}</text>
          <text x="20" y="332">{{ priceLowLabel }}</text>
          <text
            v-for="item in dateLabels"
            :key="item.date"
            :x="item.x"
            y="336"
            text-anchor="middle"
          >
            {{ item.label }}
          </text>
        </g>
      </svg>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

import { fmtPrice } from "../../utils/formatters";

const props = defineProps({
  chipHistory: { type: Object, default: null },
});

const series = computed(() => props.chipHistory?.series || []);
const priceSeries = computed(() => props.chipHistory?.price_series || []);

const chartTop = 26;
const chartBottom = 226;
const priceTop = 252;
const priceBottom = 318;
const chartLeft = 56;
const chartRight = 732;

function formatSigned(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "0";
  return `${numeric > 0 ? "+" : "-"}${Math.abs(Math.round(numeric)).toLocaleString()}`;
}

function scaleX(index, count) {
  if (count <= 1) return (chartLeft + chartRight) / 2;
  return chartLeft + ((chartRight - chartLeft) * index) / (count - 1);
}

const metricKeys = [
  { key: "foreign_net_buy_sell", label: "外資", color: "#00d9a3" },
  { key: "investment_trust_net_buy_sell", label: "投信", color: "#ffd166" },
  { key: "dealer_net_buy_sell", label: "自營商", color: "#3b8bff" },
  { key: "institutional_net_buy_sell", label: "法人合計", color: "#9b6dff" },
];

const metricValues = computed(() =>
  series.value.flatMap((item) =>
    metricKeys.map(({ key }) => Number(item?.[key])).filter((value) => Number.isFinite(value)),
  ),
);

const metricExtent = computed(() => {
  if (!metricValues.value.length) return { min: -1, max: 1 };
  const maxAbs = Math.max(...metricValues.value.map((value) => Math.abs(value)), 1);
  return { min: -maxAbs, max: maxAbs };
});

function scaleMetricY(value) {
  const min = metricExtent.value.min;
  const max = metricExtent.value.max;
  const ratio = (value - max) / (min - max);
  return chartTop + ratio * (chartBottom - chartTop);
}

const priceExtent = computed(() => {
  const values = priceSeries.value
    .map((item) => Number(item?.close))
    .filter((value) => Number.isFinite(value));
  if (!values.length) return { min: 0, max: 0 };
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return { min: min - 1, max: max + 1 };
  return { min, max };
});

function scalePriceY(value) {
  const { min, max } = priceExtent.value;
  const ratio = (value - max) / (min - max);
  return priceTop + ratio * (priceBottom - priceTop);
}

const lineSeries = computed(() =>
  metricKeys.map((item) => ({
    ...item,
    points: series.value
      .map((point, index) => {
        const numeric = Number(point?.[item.key]);
        if (!Number.isFinite(numeric)) return null;
        return `${scaleX(index, series.value.length)},${scaleMetricY(numeric)}`;
      })
      .filter(Boolean)
      .join(" "),
  })),
);

const pricePoints = computed(() => {
  if (!priceSeries.value.length) return "";
  const priceByDate = new Map(
    priceSeries.value
      .filter((item) => item?.date)
      .map((item) => [item.date, Number(item?.close)]),
  );
  return series.value
    .map((point, index) => {
      const numeric = priceByDate.get(point?.snapshot_date);
      if (!Number.isFinite(numeric)) return null;
      return `${scaleX(index, series.value.length)},${scalePriceY(numeric)}`;
    })
    .filter(Boolean)
    .join(" ");
});

const hasSeries = computed(() => series.value.length >= 2);
const maxMetric = computed(() => metricExtent.value.max);
const minMetric = computed(() => metricExtent.value.min);
const zeroLineY = computed(() => scaleMetricY(0));
const chartGuides = [chartTop, (chartTop + chartBottom) / 2, chartBottom];
const priceGuides = [priceTop, priceBottom];
const priceHighLabel = computed(() => fmtPrice(priceExtent.value.max));
const priceLowLabel = computed(() => fmtPrice(priceExtent.value.min));

const dateLabels = computed(() => {
  if (!series.value.length) return [];
  const indexes = new Set([0, Math.floor((series.value.length - 1) / 2), series.value.length - 1]);
  return [...indexes]
    .sort((left, right) => left - right)
    .map((index) => {
      const date = String(series.value[index]?.snapshot_date || "");
      return {
        date,
        x: scaleX(index, series.value.length),
        label: date ? date.slice(5) : "",
      };
    });
});
</script>

<style scoped>
.chip-trend-panel {
  padding: 14px 16px 10px;
}

.chip-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.chip-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text3);
  font-size: 11px;
}

.chip-legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.chip-legend-dot.price {
  background: linear-gradient(135deg, #ffd166, #ff9f1c);
}

.chip-trend-svg {
  width: 100%;
  height: 340px;
}

.chip-grid-line {
  stroke: rgba(255, 255, 255, 0.08);
  stroke-width: 1;
}

.chip-grid-line.is-price {
  stroke: rgba(255, 209, 102, 0.12);
}

.chip-zero-line {
  stroke: rgba(255, 255, 255, 0.18);
  stroke-width: 1.2;
  stroke-dasharray: 4 5;
}

.chip-axis-labels {
  fill: var(--text3);
  font-size: 11px;
  font-family: "JetBrains Mono", monospace;
}

@media (max-width: 860px) {
  .chip-legend {
    justify-content: flex-start;
  }
}
</style>
