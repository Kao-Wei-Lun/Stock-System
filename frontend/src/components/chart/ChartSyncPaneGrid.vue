<template>
  <div v-if="layoutPanes.length" class="sync-layout-grid" :class="`is-${layoutClass}`">
    <div v-for="pane in layoutPanes" :key="pane.key" class="sync-pane-card">
      <div class="sync-pane-head">
        <span>{{ pane.title }}</span>
        <span>{{ currentTicker }}</span>
      </div>
      <canvas :ref="(element) => setSyncPaneRef(pane.key, element)"></canvas>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  layoutPanes: { type: Array, default: () => [] },
  currentTicker: { type: String, required: true },
  setSyncPaneRef: { type: Function, required: true },
});

const layoutClass = computed(() => {
  if (props.layoutPanes.length >= 3) return "quad";
  if (props.layoutPanes.length === 1) return "double";
  return "single";
});
</script>
