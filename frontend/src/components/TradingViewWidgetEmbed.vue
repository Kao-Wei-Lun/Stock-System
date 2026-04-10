<template>
  <div class="tv-widget-shell">
    <iframe
      v-if="scriptAllowed"
      :key="iframeKey"
      class="tv-widget-frame"
      :srcdoc="iframeSrcdoc"
      title="TradingView widget"
      loading="lazy"
      sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
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

const serializedConfig = computed(() => JSON.stringify(props.config ?? {}));

const iframeKey = computed(() => `${props.scriptSrc}::${serializedConfig.value}`);

const iframeSrcdoc = computed(() => {
  if (!scriptAllowed.value) return "";

  const scriptSrc = escapeHtmlAttribute(props.scriptSrc);
  const configJson = escapeScriptJson(serializedConfig.value);

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      html,
      body,
      .tradingview-widget-container,
      .tradingview-widget-container__widget {
        width: 100%;
        height: 100%;
        min-height: 100%;
        margin: 0;
      }

      body {
        overflow: hidden;
        background: transparent;
      }
    </style>
  </head>
  <body>
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="${scriptSrc}" async>
${configJson}
      <\/script>
    </div>
  </body>
</html>`;
});

function escapeHtmlAttribute(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function escapeScriptJson(value) {
  return String(value)
    .replace(/<\//g, "<\\/")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}
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
