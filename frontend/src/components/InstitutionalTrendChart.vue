<template>
  <div class="trend-card">
    <div class="trend-card-head">
      <div>
        <div class="ind-group-title">{{ title }}</div>
        <div v-if="subtitle" class="institutional-section-note">{{ subtitle }}</div>
      </div>
      <div class="trend-legend">
        <span
          v-for="series in visibleSeries"
          :key="series.key"
          class="trend-legend-item"
        >
          <span class="trend-legend-dot" :style="{ background: series.color }"></span>
          <span>{{ series.label }}</span>
          <strong>{{ formatValue(latestValues[series.key]) }}</strong>
        </span>
      </div>
    </div>

    <div v-if="!points.length" class="institutional-empty">尚無趨勢資料</div>
    <div
      v-else
      ref="chartWrapRef"
      class="trend-chart-wrap"
      @mousemove="handleMouseMove"
      @mouseleave="clearHover"
    >
      <svg class="trend-chart" viewBox="0 0 640 220" preserveAspectRatio="none">
      <path
        v-if="bandPath"
        :d="bandPath"
        class="trend-band"
      />

      <line
        v-for="tick in gridTicks"
        :key="`grid-${tick}`"
        x1="44"
        :y1="scaleY(tick)"
        x2="620"
        :y2="scaleY(tick)"
        class="trend-grid"
      />

      <text
        v-for="tick in gridTicks"
        :key="`label-${tick}`"
        x="4"
        :y="scaleY(tick) + 4"
        class="trend-axis-text"
      >
        {{ formatValue(tick) }}
      </text>

      <path
        v-for="series in visibleSeries"
        :key="series.key"
        :d="linePath(series.key)"
        class="trend-line"
        :style="{ stroke: series.color }"
      />

      <g v-if="hoverIndex != null">
        <line
          :x1="scaleX(hoverIndex)"
          y1="16"
          :x2="scaleX(hoverIndex)"
          y2="192"
          class="trend-hover-line"
        />
        <circle
          v-for="series in visibleSeries"
          :key="`dot-${series.key}`"
          v-if="hoverValue(series.key) != null"
          :cx="scaleX(hoverIndex)"
          :cy="scaleY(hoverValue(series.key))"
          r="3.5"
          class="trend-hover-dot"
          :style="{ fill: series.color }"
        />
      </g>

      <g v-for="mark in dateMarks" :key="mark.index">
        <line
          :x1="scaleX(mark.index)"
          y1="16"
          :x2="scaleX(mark.index)"
          y2="192"
          class="trend-grid trend-grid-vertical"
        />
        <text
          :x="scaleX(mark.index)"
          y="210"
          class="trend-date-text"
          text-anchor="middle"
        >
          {{ mark.label }}
        </text>
      </g>
      </svg>

      <div v-if="hoverPoint" class="trend-tooltip" :style="tooltipStyle">
        <div class="trend-tooltip-title">{{ hoverPoint.date }}</div>
        <div v-for="series in visibleSeries" :key="`tip-${series.key}`" class="trend-tooltip-row">
          <span>
            <span class="trend-legend-dot" :style="{ background: series.color }"></span>
            {{ series.label }}
          </span>
          <strong>{{ formatValue(hoverPoint[series.key]) }}</strong>
        </div>
        <div v-if="bandMinKey && hoverPoint[bandMinKey] != null" class="trend-tooltip-row">
          <span>成本帶低</span>
          <strong>{{ formatValue(hoverPoint[bandMinKey]) }}</strong>
        </div>
        <div v-if="bandMaxKey && hoverPoint[bandMaxKey] != null" class="trend-tooltip-row">
          <span>成本帶高</span>
          <strong>{{ formatValue(hoverPoint[bandMaxKey]) }}</strong>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { fmtTwMoney } from "../utils/formatters";

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: "" },
  points: { type: Array, default: () => [] },
  series: { type: Array, default: () => [] },
  bandMinKey: { type: String, default: "" },
  bandMaxKey: { type: String, default: "" },
  valueFormat: { type: String, default: "number" },
});

const chartWrapRef = ref(null);
const hoverIndex = ref(null);
const hoverLeft = ref(0);

const CHART_LEFT = 44;
const CHART_RIGHT = 620;
const CHART_TOP = 16;
const CHART_BOTTOM = 192;

const visibleSeries = computed(() =>
  (props.series || []).filter((series) =>
    props.points.some((point) => Number.isFinite(Number(point?.[series.key]))),
  ),
);

const valueBounds = computed(() => {
  const values = [];
  for (const point of props.points) {
    for (const series of visibleSeries.value) {
      const value = Number(point?.[series.key]);
      if (Number.isFinite(value)) values.push(value);
    }
    if (props.bandMinKey) {
      const value = Number(point?.[props.bandMinKey]);
      if (Number.isFinite(value)) values.push(value);
    }
    if (props.bandMaxKey) {
      const value = Number(point?.[props.bandMaxKey]);
      if (Number.isFinite(value)) values.push(value);
    }
  }
  if (!values.length) return { min: 0, max: 1 };
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    const padding = Math.max(Math.abs(min) * 0.08, 1);
    min -= padding;
    max += padding;
  } else {
    const padding = Math.max((max - min) * 0.12, Math.abs(max) * 0.04, 1);
    min -= padding;
    max += padding;
  }
  return { min, max };
});

const gridTicks = computed(() => {
  const { min, max } = valueBounds.value;
  const ticks = [];
  for (let index = 0; index < 4; index += 1) {
    const ratio = index / 3;
    ticks.push(max - (max - min) * ratio);
  }
  return ticks;
});

const latestValues = computed(() => {
  const last = props.points.at(-1) || {};
  return Object.fromEntries(visibleSeries.value.map((series) => [series.key, last[series.key]]));
});

const dateMarks = computed(() => {
  if (!props.points.length) return [];
  const targetCount = Math.min(5, props.points.length);
  const step = Math.max(1, Math.floor((props.points.length - 1) / Math.max(targetCount - 1, 1)));
  const marks = [];
  for (let index = 0; index < props.points.length; index += step) {
    marks.push({
      index,
      label: formatDateLabel(props.points[index]?.date),
    });
  }
  const lastIndex = props.points.length - 1;
  if (!marks.find((item) => item.index === lastIndex)) {
    marks.push({ index: lastIndex, label: formatDateLabel(props.points[lastIndex]?.date) });
  }
  return marks;
});

const bandPath = computed(() => {
  if (!props.bandMinKey || !props.bandMaxKey || !props.points.length) return "";
  const topPoints = [];
  const bottomPoints = [];
  props.points.forEach((point, index) => {
    const high = Number(point?.[props.bandMaxKey]);
    const low = Number(point?.[props.bandMinKey]);
    if (!Number.isFinite(high) || !Number.isFinite(low)) return;
    topPoints.push(`${scaleX(index)},${scaleY(high)}`);
    bottomPoints.unshift(`${scaleX(index)},${scaleY(low)}`);
  });
  if (!topPoints.length || !bottomPoints.length) return "";
  return `M ${topPoints.join(" L ")} L ${bottomPoints.join(" L ")} Z`;
});

const hoverPoint = computed(() => (
  hoverIndex.value == null ? null : (props.points[hoverIndex.value] || null)
));

const tooltipStyle = computed(() => {
  const left = hoverLeft.value > 420 ? hoverLeft.value - 180 : hoverLeft.value + 14;
  return {
    left: `${Math.max(8, left)}px`,
    top: "10px",
  };
});

function scaleX(index) {
  if (props.points.length <= 1) return (CHART_LEFT + CHART_RIGHT) / 2;
  const width = CHART_RIGHT - CHART_LEFT;
  return CHART_LEFT + (index / (props.points.length - 1)) * width;
}

function scaleY(value) {
  const { min, max } = valueBounds.value;
  const ratio = (Number(value) - min) / (max - min || 1);
  return CHART_BOTTOM - ratio * (CHART_BOTTOM - CHART_TOP);
}

function linePath(key) {
  const segments = [];
  let started = false;
  props.points.forEach((point, index) => {
    const value = Number(point?.[key]);
    if (!Number.isFinite(value)) return;
    segments.push(`${started ? "L" : "M"} ${scaleX(index)} ${scaleY(value)}`);
    started = true;
  });
  return segments.join(" ");
}

function hoverValue(key) {
  if (hoverIndex.value == null) return null;
  const value = Number(props.points[hoverIndex.value]?.[key]);
  return Number.isFinite(value) ? value : null;
}

function formatDateLabel(value) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  const year = String(date.getFullYear()).slice(2);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}/${month}/${day}`;
}

function formatValue(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  if (props.valueFormat === "price") return numeric.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (props.valueFormat === "amount") {
    return fmtTwMoney(numeric, { signed: true });
  }
  return `${numeric >= 0 ? "+" : ""}${Math.round(numeric).toLocaleString()}`;
}

function handleMouseMove(event) {
  const chart = chartWrapRef.value;
  if (!chart || !props.points.length) return;
  const rect = chart.getBoundingClientRect();
  const ratio = Math.min(Math.max((event.clientX - rect.left) / Math.max(rect.width, 1), 0), 1);
  hoverIndex.value = Math.min(props.points.length - 1, Math.max(0, Math.round(ratio * (props.points.length - 1))));
  hoverLeft.value = event.clientX - rect.left;
}

function clearHover() {
  hoverIndex.value = null;
}
</script>
