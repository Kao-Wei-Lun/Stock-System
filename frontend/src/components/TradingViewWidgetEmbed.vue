<template>
  <div class="tv-widget-shell" :class="{ 'is-interactive': isActuallyInteractive }" @mouseleave="disableInteraction">
    <div v-if="scriptAllowed" class="tv-widget-frame-wrap">
      <div
        ref="scriptWidgetHost"
        class="tv-widget-script-host tradingview-widget-container"
        :class="{ interactive: isActuallyInteractive }"
      ></div>
      <div v-if="!isActuallyInteractive" class="tv-widget-overlay">
        <div class="tv-widget-overlay-card">
          <strong>頁面捲動優先</strong>
          <span>滑鼠滾輪會直接捲動總覽頁。要操作元件時，再切到互動模式。</span>
          <button class="tv-widget-overlay-btn" type="button" @click="enableInteraction">
            啟用互動
          </button>
        </div>
      </div>
      <button
        v-else-if="!isFullscreen"
        class="tv-widget-interaction-exit"
        type="button"
        @click="disableInteraction"
      >
        返回頁面捲動
      </button>
    </div>
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
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  scriptSrc: { type: String, required: true },
  config: { type: Object, required: true },
  fallbackUrl: { type: String, default: "https://www.tradingview.com/" },
  isFullscreen: { type: Boolean, default: false },
});

const ALLOWED_SCRIPT_HOSTS = new Set(["s3.tradingview.com"]);
const ALLOWED_SCRIPT_PATH_PREFIX = "/external-embedding/";
const WIDGET_SCRIPT_PATTERN = /^embed-widget-([a-z0-9-]+)\.js$/;

const interactionEnabled = ref(false);
const scriptWidgetHost = ref(null);

const isActuallyInteractive = computed(() => props.isFullscreen || interactionEnabled.value);

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
const injectedScriptConfig = computed(() => ({
  ...(props.config ?? {}),
  utm_source: "",
  utm_medium: "widget",
  utm_campaign: widgetName.value,
}));

function clearInjectedScriptWidget() {
  if (!scriptWidgetHost.value) return;
  scriptWidgetHost.value.replaceChildren();
}

function renderInjectedScriptWidget() {
  if (!scriptAllowed.value || !scriptWidgetHost.value) return;

  const host = scriptWidgetHost.value;
  clearInjectedScriptWidget();

  const widgetRoot = document.createElement("div");
  widgetRoot.className = "tradingview-widget-container__widget";
  widgetRoot.style.width = "100%";
  widgetRoot.style.height = "100%";

  const script = document.createElement("script");
  script.type = "text/javascript";
  script.async = true;
  script.src = props.scriptSrc;
  script.text = JSON.stringify(injectedScriptConfig.value, null, 2);

  host.append(widgetRoot, script);
}

function syncInjectedScriptWidget() {
  if (!scriptAllowed.value) {
    clearInjectedScriptWidget();
    return;
  }

  renderInjectedScriptWidget();
}

function enableInteraction() {
  interactionEnabled.value = true;
}

function disableInteraction() {
  interactionEnabled.value = false;
}

onMounted(() => {
  syncInjectedScriptWidget();
});

onBeforeUnmount(() => {
  clearInjectedScriptWidget();
});

watch(
  () => props.scriptSrc,
  () => syncInjectedScriptWidget(),
);

watch(
  () => props.config,
  () => syncInjectedScriptWidget(),
  { deep: true },
);

watch(
  () => scriptAllowed.value,
  () => syncInjectedScriptWidget(),
);
</script>

<style scoped>
.tv-widget-shell {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: inherit;
  height: 100%;
}

.tv-widget-frame-wrap {
  position: relative;
  display: flex;
  flex: 1 1 auto;
  min-height: inherit;
}

.tv-widget-script-host {
  display: block;
  flex: 1 1 auto;
  width: 100%;
  min-height: 260px;
  background: transparent;
  pointer-events: none;
}

.tv-widget-script-host.interactive {
  pointer-events: auto;
}

.tv-widget-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px;
  background: linear-gradient(180deg, rgba(8, 12, 18, 0.18), rgba(8, 12, 18, 0.42));
}

.tv-widget-overlay-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 320px;
  padding: 14px 16px;
  border: 1px solid rgba(123, 231, 255, 0.2);
  border-radius: 14px;
  background: rgba(8, 12, 18, 0.9);
  color: var(--text2);
  font-size: 11px;
  line-height: 1.6;
  text-align: center;
}

.tv-widget-overlay-card strong {
  color: var(--text);
  font-size: 12px;
}

.tv-widget-overlay-btn,
.tv-widget-interaction-exit {
  border: 1px solid rgba(123, 231, 255, 0.24);
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.12);
  color: #d7fbff;
  cursor: pointer;
  font-size: 10px;
  font-family: "JetBrains Mono", monospace;
}

.tv-widget-overlay-btn {
  align-self: center;
  min-height: 34px;
  padding: 0 14px;
}

.tv-widget-interaction-exit {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  min-height: 32px;
  padding: 0 16px;
  background: rgba(8, 12, 18, 0.85);
  backdrop-filter: blur(4px);
  border: 1px solid rgba(123, 231, 255, 0.3);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.tv-widget-interaction-exit:hover {
  background: rgba(123, 231, 255, 0.15);
  border-color: rgba(123, 231, 255, 0.5);
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
