<template>
  <main class="settings-workspace">
    <div class="settings-hero">
      <div>
        <div class="settings-kicker">Settings</div>
        <h1>系統設定</h1>
      </div>
      <div class="settings-tabs" role="tablist" aria-label="設定分類">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          :class="{ active: activeTab === tab.key }"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <div class="settings-content">
      <FubonAccountsPanel v-if="activeTab === 'fubon'" />

      <section v-else-if="activeTab === 'notifications'" class="settings-placeholder">
        <h2>通知設定</h2>
        <p>通知通道會沿用目前的 Telegram 與 Discord 環境設定。</p>
      </section>

      <section v-else class="settings-placeholder">
        <h2>系統資訊</h2>
        <p>後端連線、排程與資料同步狀態維持在狀態列與系統健康檢查中。</p>
      </section>
    </div>
  </main>
</template>

<script setup>
import { ref } from "vue";

import FubonAccountsPanel from "./FubonAccountsPanel.vue";

const activeTab = ref("fubon");

const tabs = [
  { key: "fubon", label: "富邦 API" },
  { key: "notifications", label: "通知" },
  { key: "system", label: "系統" },
];
</script>

<style scoped>
.settings-workspace {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: linear-gradient(180deg, rgba(8, 12, 18, 0.98), rgba(12, 18, 28, 0.98));
}

.settings-workspace::-webkit-scrollbar {
  width: 6px;
}

.settings-workspace::-webkit-scrollbar-thumb {
  background: var(--border2);
  border-radius: 999px;
}

.settings-hero {
  position: sticky;
  top: 0;
  z-index: 3;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border);
  background: rgba(10, 16, 26, 0.98);
}

.settings-kicker {
  color: var(--text3);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.settings-hero h1 {
  margin-top: 4px;
  font-family: "Syne", sans-serif;
  font-size: 24px;
}

.settings-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.settings-tabs button {
  min-height: 34px;
  border: 1px solid var(--border2);
  border-radius: 8px;
  background: var(--bg3);
  color: var(--text2);
  padding: 0 12px;
  font-family: "JetBrains Mono", monospace;
  cursor: pointer;
}

.settings-tabs button.active {
  border-color: rgba(123, 231, 255, 0.35);
  color: #d7fbff;
  background: rgba(123, 231, 255, 0.12);
}

.settings-content {
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: 18px 20px 28px;
}

.settings-placeholder {
  border: 1px solid var(--border2);
  border-radius: 8px;
  background: rgba(13, 20, 32, 0.92);
  padding: 16px;
}

.settings-placeholder h2 {
  font-family: "Syne", sans-serif;
  font-size: 19px;
}

.settings-placeholder p {
  margin-top: 8px;
  color: var(--text2);
  line-height: 1.7;
}

@media (max-width: 720px) {
  .settings-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .settings-content {
    padding: 14px 12px 24px;
  }
}
</style>
