<template>
  <div class="tv-widget-shell">
    <div ref="hostRef" class="tradingview-widget-container"></div>
    <div v-if="!scriptAllowed" class="tv-widget-warning">
      此 TradingView 來源未在允許清單內。
    </div>
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  scriptSrc: { type: String, required: true },
  config: { type: Object, required: true },
  fallbackUrl: { type: String, default: "https://www.tradingview.com/" },
});

const hostRef = ref(null);
const ALLOWED_SCRIPT_HOSTS = new Set(["s3.tradingview.com"]);
const ALLOWED_SCRIPT_PATH_PREFIX = "/external-embedding/";

const scriptAllowed = computed(() => {
  try {
    const url = new URL(props.scriptSrc);
    return (
      url.protocol === "https:"
      && ALLOWED_SCRIPT_HOSTS.has(url.hostname)
      && url.pathname.startsWith(ALLOWED_SCRIPT_PATH_PREFIX)
    );
  } catch (error) {
    return false;
  }
});

function cleanupHost() {
  if (!hostRef.value) return;
  hostRef.value.replaceChildren();
}

function renderWidget() {
  if (!hostRef.value || typeof document === "undefined") return;

  cleanupHost();
  if (!scriptAllowed.value) return;

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

.tv-widget-warning {
  padding: 10px 12px;
  border: 1px solid rgba(255, 77, 106, 0.2);
  border-radius: 8px;
  color: #ff8a9d;
  background: rgba(255, 77, 106, 0.08);
  font-size: 11px;
}
</style>
