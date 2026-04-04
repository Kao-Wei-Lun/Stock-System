<template>
  <div class="ind-panel" :class="[panelClass, { visible }]">
    <div class="ind-label-tag">{{ label }}</div>
    <canvas ref="canvasEl"></canvas>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watchEffect } from "vue";

const props = defineProps({
  visible: { type: Boolean, default: false },
  label: { type: String, required: true },
  canvasTarget: { type: Object, required: true },
  panelClass: { type: String, default: "" },
});

const canvasEl = ref(null);

watchEffect(() => {
  props.canvasTarget.target.value = canvasEl.value;
});

onBeforeUnmount(() => {
  props.canvasTarget.target.value = null;
});
</script>
