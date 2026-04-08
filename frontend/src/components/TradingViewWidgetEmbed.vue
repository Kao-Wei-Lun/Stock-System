<template>
  <div class="tv-widget-shell">
    <div ref="hostRef" class="tradingview-widget-container"></div>
    <a
      v-if="fallbackUrl"
      class="tv-widget-link"
      :href="fallbackUrl"
      target="_blank"
      rel="noreferrer"
    >
      Open In TradingView
    </a>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  scriptSrc: { type: String, required: true },
  config: { type: Object, required: true },
  fallbackUrl: { type: String, default: "https://www.tradingview.com/" },
});

const hostRef = ref(null);

function cleanupHost() {
  if (!hostRef.value) return;
  hostRef.value.replaceChildren();
}

function renderWidget() {
  if (!hostRef.value || typeof document === "undefined") return;

  cleanupHost();

  const widgetNode = document.createElement("div");
  widgetNode.className = "tradingview-widget-container__widget";

  const scriptNode = document.createElement("script");
  scriptNode.type = "text/javascript";
  scriptNode.async = true;
  scriptNode.src = props.scriptSrc;
  scriptNode.text = JSON.stringify(props.config);

  hostRef.value.appendChild(widgetNode);
  hostRef.value.appendChild(scriptNode);
}

watch(
  () => [props.scriptSrc, JSON.stringify(props.config)],
  async () => {
    await nextTick();
    renderWidget();
  },
  { immediate: true },
);

onMounted(() => {
  renderWidget();
});

onBeforeUnmount(() => {
  cleanupHost();
});
</script>

<style scoped>
.tv-widget-shell {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}

.tradingview-widget-container {
  min-height: inherit;
}

.tv-widget-link {
  align-self: flex-end;
  color: var(--text3);
  font-size: 10px;
  text-decoration: none;
}
</style>
