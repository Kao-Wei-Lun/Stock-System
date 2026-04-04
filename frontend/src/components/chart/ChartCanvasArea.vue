<template>
  <div ref="chartAreaEl" class="chart-area">
    <canvas
      ref="mainCanvasEl"
      id="mainChart"
      :class="canvasClass"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseleave="onMouseLeave"
      @mouseup="onMouseUp"
      @wheel.prevent="onWheel"
      @click="onChartClick"
      @dblclick="onDoubleClick"
    ></canvas>

    <div v-show="loading" class="chart-loading chart-loading-skeleton">
      <div class="chart-skeleton-ribbon">
        <span class="chart-skeleton-block wide"></span>
        <span class="chart-skeleton-block"></span>
        <span class="chart-skeleton-block"></span>
      </div>
      <div class="chart-skeleton-surface"></div>
      <div class="chart-skeleton-ribbon compact">
        <span class="chart-skeleton-block"></span>
        <span class="chart-skeleton-block narrow"></span>
      </div>
      <p>{{ loadingMessage }}</p>
    </div>

    <div v-show="crosshair.visible" class="crosshair-box is-open">
      <div class="ci-row"><span class="ci-label">日期</span><span>{{ crosshair.date }}</span></div>
      <div class="ci-row"><span class="ci-label">游標價</span><span>{{ crosshair.hoverPrice }}</span></div>
      <div class="ci-row"><span class="ci-label">開盤</span><span>{{ crosshair.open }}</span></div>
      <div class="ci-row"><span class="ci-label">最高</span><span>{{ crosshair.high }}</span></div>
      <div class="ci-row"><span class="ci-label">最低</span><span>{{ crosshair.low }}</span></div>
      <div class="ci-row"><span class="ci-label">收盤</span><span>{{ crosshair.close }}</span></div>
      <div class="ci-row"><span class="ci-label">漲跌</span><span>{{ crosshair.change }} ({{ crosshair.changePct }})</span></div>
      <div class="ci-row"><span class="ci-label">成交量</span><span>{{ crosshair.volume }}</span></div>
    </div>

    <div v-if="visibleEventMarkers.length" class="chart-event-overlay">
      <button
        v-for="marker in visibleEventMarkers"
        :key="marker.key"
        type="button"
        class="chart-event-marker"
        :class="[marker.importance || 'medium', { active: focusedEventKey === marker.key }]"
        :style="{ left: marker.left }"
        :title="`${marker.title} / ${marker.event_date}`"
        @click="jumpToEvent(marker)"
      >
        <span class="chart-event-line"></span>
        <span class="chart-event-dot"></span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watchEffect } from "vue";

const props = defineProps({
  loading: { type: Boolean, default: false },
  loadingMessage: { type: String, default: "" },
  crosshair: { type: Object, required: true },
  visibleEventMarkers: { type: Array, default: () => [] },
  focusedEventKey: { type: String, default: "" },
  canvasClass: { type: String, default: "" },
  chartAreaTarget: { type: Object, required: true },
  mainCanvasTarget: { type: Object, required: true },
  onMouseDown: { type: Function, required: true },
  onMouseMove: { type: Function, required: true },
  onMouseLeave: { type: Function, required: true },
  onMouseUp: { type: Function, required: true },
  onWheel: { type: Function, required: true },
  onChartClick: { type: Function, required: true },
  onDoubleClick: { type: Function, required: true },
  jumpToEvent: { type: Function, required: true },
});

const chartAreaEl = ref(null);
const mainCanvasEl = ref(null);

watchEffect(() => {
  props.chartAreaTarget.target.value = chartAreaEl.value;
});

watchEffect(() => {
  props.mainCanvasTarget.target.value = mainCanvasEl.value;
});

onBeforeUnmount(() => {
  props.chartAreaTarget.target.value = null;
  props.mainCanvasTarget.target.value = null;
});
</script>

<style scoped>
.chart-event-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.chart-event-marker {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 18px;
  margin-left: -9px;
  border: 0;
  background: transparent;
  padding: 0;
  pointer-events: auto;
  cursor: pointer;
}

.chart-event-line {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-50%);
  background: rgba(255, 209, 102, 0.45);
}

.chart-event-dot {
  position: absolute;
  top: 18px;
  left: 50%;
  width: 8px;
  height: 8px;
  transform: translateX(-50%);
  border-radius: 50%;
  background: #ffd166;
  box-shadow: 0 0 0 4px rgba(255, 209, 102, 0.12);
}

.chart-event-marker.high .chart-event-dot {
  background: #ff7b72;
  box-shadow: 0 0 0 4px rgba(255, 123, 114, 0.12);
}

.chart-event-marker.low .chart-event-dot {
  background: #86d98f;
  box-shadow: 0 0 0 4px rgba(134, 217, 143, 0.12);
}

.chart-event-marker.active .chart-event-line {
  background: rgba(0, 212, 255, 0.7);
}

.chart-event-marker.active .chart-event-dot {
  background: #00d4ff;
  box-shadow: 0 0 0 4px rgba(0, 212, 255, 0.14);
}

.chart-loading-skeleton {
  gap: 16px;
}

.chart-skeleton-ribbon {
  width: min(420px, 100%);
  display: flex;
  gap: 10px;
}

.chart-skeleton-ribbon.compact {
  width: min(280px, 80%);
}

.chart-skeleton-block,
.chart-skeleton-surface {
  position: relative;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.07);
}

.chart-skeleton-block::after,
.chart-skeleton-surface::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(123, 231, 255, 0.22) 50%, transparent 100%);
  transform: translateX(-100%);
  animation: chart-skeleton-shimmer 1.4s ease-in-out infinite;
}

.chart-skeleton-block {
  height: 12px;
  flex: 1;
}

.chart-skeleton-block.wide {
  flex: 1.8;
}

.chart-skeleton-block.narrow {
  flex: 0.7;
}

.chart-skeleton-surface {
  width: min(620px, 100%);
  height: clamp(180px, 44vh, 320px);
  border-radius: 26px;
}

@keyframes chart-skeleton-shimmer {
  100% {
    transform: translateX(100%);
  }
}
</style>
