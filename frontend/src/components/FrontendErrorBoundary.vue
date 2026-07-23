<template>
  <main
    v-if="failure"
    class="frontend-recovery"
    role="alert"
    aria-live="assertive"
    data-testid="frontend-recovery"
  >
    <section class="frontend-recovery__card">
      <div class="frontend-recovery__eyebrow">QUANTVISION RECOVERY</div>
      <h1>前端模組暫時無法載入</h1>
      <p>{{ recoveryMessage }}</p>
      <p class="frontend-recovery__code">錯誤分類：{{ failure.category }}</p>
      <div class="frontend-recovery__actions">
        <button type="button" autofocus @click="retryModule">重新載入模組</button>
        <button type="button" @click="reloadPage">重新載入頁面</button>
        <button type="button" class="secondary" :disabled="clearing" @click="clearCacheAndReload">
          {{ clearing ? "清除中…" : "清除前端快取並重載" }}
        </button>
      </div>
      <p class="frontend-recovery__hint">此操作只會清除瀏覽器中的行情快取，不會刪除資料庫、帳戶或交易紀錄。</p>
    </section>
  </main>
  <div v-else :key="renderKey">
    <slot />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onErrorCaptured, onMounted, ref } from "vue";

import { resetIndexedDbTerminalCache } from "../services/terminalCache";
import {
  categorizeFrontendError,
  frontendErrorEventName,
} from "../utils/frontendRecovery";

const failure = ref(null);
const renderKey = ref(0);
const clearing = ref(false);

const recoveryMessage = computed(() => (
  failure.value?.category === "module_load"
    ? "新版本檔案或網路快取可能不同步，您可以先重試模組；既有資料不會受到影響。"
    : "畫面執行時發生錯誤。您可以重試目前畫面，或安全清除本機行情快取後重新載入。"
));

function capture(category, source) {
  failure.value = {
    category: String(category || "unexpected"),
    source: String(source || "runtime"),
  };
}

function handleReportedError(event) {
  capture(event?.detail?.category, event?.detail?.source);
}

function retryModule() {
  failure.value = null;
  renderKey.value += 1;
}

function reloadPage() {
  window.location.reload();
}

async function clearCacheAndReload() {
  clearing.value = true;
  try {
    await resetIndexedDbTerminalCache();
    if (globalThis.caches?.keys) {
      const names = await globalThis.caches.keys();
      await Promise.all(
        names
          .filter((name) => String(name).toLowerCase().includes("quantvision"))
          .map((name) => globalThis.caches.delete(name)),
      );
    }
  } finally {
    window.location.reload();
  }
}

onErrorCaptured((error) => {
  capture(categorizeFrontendError(error), "component");
  return false;
});

onMounted(() => window.addEventListener(frontendErrorEventName(), handleReportedError));
onBeforeUnmount(() => window.removeEventListener(frontendErrorEventName(), handleReportedError));
</script>

<style scoped>
.frontend-recovery {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  color: #dcecff;
  background:
    radial-gradient(circle at 20% 0%, rgba(21, 134, 194, 0.16), transparent 40%),
    #07101c;
}

.frontend-recovery__card {
  width: min(620px, 100%);
  padding: 32px;
  border: 1px solid rgba(103, 205, 255, 0.22);
  border-radius: 18px;
  background: rgba(12, 25, 41, 0.96);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
}

.frontend-recovery__eyebrow,
.frontend-recovery__code {
  color: #62d8ff;
  font: 600 12px/1.4 "JetBrains Mono Variable", monospace;
  letter-spacing: 0.12em;
}

.frontend-recovery h1 {
  margin: 10px 0;
  font-size: clamp(24px, 4vw, 36px);
}

.frontend-recovery p {
  color: rgba(220, 236, 255, 0.76);
  line-height: 1.7;
}

.frontend-recovery__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
}

.frontend-recovery button {
  min-height: 42px;
  padding: 0 16px;
  border: 1px solid #32c7ef;
  border-radius: 9px;
  color: #05131c;
  background: #62d8ff;
  cursor: pointer;
}

.frontend-recovery button.secondary {
  color: #ccecff;
  background: transparent;
}

.frontend-recovery button:focus-visible {
  outline: 3px solid #ffd166;
  outline-offset: 3px;
}

.frontend-recovery button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.frontend-recovery__hint {
  margin-bottom: 0;
  font-size: 12px;
}
</style>
