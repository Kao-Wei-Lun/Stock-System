<template>
  <div class="tv-widget-shell">
    <iframe
      v-if="scriptAllowed"
      :key="iframeKey"
      class="tv-widget-frame"
      :src="iframeSrc"
      title="TradingView widget"
      loading="lazy"
      sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"
      referrerpolicy="no-referrer-when-downgrade"
    ></iframe>
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
import { computed } from "vue";

const props = defineProps({
  scriptSrc: { type: String, required: true },
  config: { type: Object, required: true },
  fallbackUrl: { type: String, default: "https://www.tradingview.com/" },
});

const ALLOWED_SCRIPT_HOSTS = new Set(["s3.tradingview.com"]);
const ALLOWED_SCRIPT_PATH_PREFIX = "/external-embedding/";
const WIDGET_HOST = "https://www.tradingview-widget.com";
const WIDGET_SCRIPT_PATTERN = /^embed-widget-([a-z0-9-]+)\.js$/;

const widgetName = computed(() => {
  try {
    const url = new URL(props.scriptSrc);
    if (
      url.protocol === "https:"
      && ALLOWED_SCRIPT_HOSTS.has(url.hostname)
      && url.pathname.startsWith(ALLOWED_SCRIPT_PATH_PREFIX)
    ) {
      const fileName = url.pathname.slice(ALLOWED_SCRIPT_PATH_PREFIX.length);
      return fileName.match(WIDGET_SCRIPT_PATTERN)?.[1] ?? "";
    }
  } catch (error) {
    return "";
  }

  return "";
});

const scriptAllowed = computed(() => Boolean(widgetName.value));

const widgetConfig = computed(() => {
  const { locale, ...config } = props.config ?? {};

  return {
    ...config,
    utm_source: "",
    utm_medium: "widget",
    utm_campaign: widgetName.value,
  };
});

const locale = computed(() => props.config?.locale || "en");

const serializedConfig = computed(() => JSON.stringify(widgetConfig.value));

const iframeSrc = computed(() => {
  if (!scriptAllowed.value) return "";

  const query = new URLSearchParams({ locale: locale.value });
  const configHash = encodeURIComponent(serializedConfig.value);
  return `${WIDGET_HOST}/embed-widget/${widgetName.value}/?${query.toString()}#${configHash}`;
});

const iframeKey = computed(() => `${iframeSrc.value}`);
</script>

<style scoped>
.tv-widget-shell {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: inherit;
  height: 100%;
}

.tv-widget-frame {
  display: block;
  flex: 1 1 auto;
  width: 100%;
  min-height: 260px;
  border: 0;
  background: transparent;
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
