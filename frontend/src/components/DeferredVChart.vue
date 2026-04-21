<template>
  <div ref="shellRef" class="deferred-v-chart-shell">
    <VChart
      v-if="chartReady"
      class="deferred-v-chart-canvas"
      :option="option"
      :autoresize="autoresize"
      @click="$emit('click', $event)"
    />
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import VChart from "vue-echarts";

const props = defineProps({
  option: {
    type: Object,
    required: true,
  },
  autoresize: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["click"]);

const shellRef = ref(null);
const chartReady = ref(false);

let resizeObserver = null;
let rafId = 0;

function isTestEnv() {
  return Boolean(import.meta?.env?.MODE === "test");
}

function tryMountChart() {
  if (chartReady.value) return;
  const shell = shellRef.value;
  if (!shell) return;
  if (shell.clientWidth > 0 && shell.clientHeight > 0) {
    chartReady.value = true;
    if (resizeObserver) {
      resizeObserver.disconnect();
      resizeObserver = null;
    }
  }
}

onMounted(async () => {
  if (isTestEnv()) {
    chartReady.value = true;
    return;
  }

  await nextTick();
  rafId = window.requestAnimationFrame(() => {
    tryMountChart();
  });

  if (!chartReady.value && typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(() => {
      tryMountChart();
    });
    if (shellRef.value) {
      resizeObserver.observe(shellRef.value);
    }
  }
});

onBeforeUnmount(() => {
  if (rafId) {
    window.cancelAnimationFrame(rafId);
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});
</script>

<style scoped>
.deferred-v-chart-shell {
  width: 100%;
}

.deferred-v-chart-canvas {
  width: 100%;
  min-height: inherit;
}
</style>
