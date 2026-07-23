<template>
  <section class="fubon-panel">
    <div class="settings-section-head">
      <div>
        <h2>富邦 API 帳號</h2>
        <p>新增帳號後，先測試連線，再設為使用中。其餘啟用中的帳號會自動參與即時訂閱分流。混合模式下，watchlist 會優先走 Speed，目前開啟中的盤中標的會優先升級到 Normal。</p>
      </div>
      <button class="primary-btn" type="button" @click="openCreateModal">新增帳號</button>
    </div>

    <div v-if="message.text" class="settings-message" :class="message.type">
      {{ message.text }}
    </div>

    <div v-if="error" class="settings-message error">{{ error }}</div>

    <div v-if="loading && !accounts.length" class="settings-empty">讀取帳號中</div>

    <div v-else-if="!accounts.length" class="settings-empty">
      尚未建立富邦 API 帳號。
    </div>

    <div v-else class="account-list">
      <article v-for="account in accounts" :key="account.id" class="account-card">
        <div class="account-main">
          <div class="account-title-row">
            <span class="status-dot" :class="statusClass(account.connection_status)"></span>
            <div>
              <h3>{{ account.label }}</h3>
              <div class="account-sub">{{ account.user_id }} · {{ modeLabel(account.realtime_ws_mode || account.ws_mode) }}</div>
              <div class="account-mode-note">{{ modeHint(account.realtime_ws_mode || account.ws_mode) }}</div>
            </div>
          </div>
          <span v-if="account.is_active" class="active-badge">使用中</span>
        </div>

        <div class="account-meta">
          <div>
            <span>連線狀態</span>
            <strong>{{ statusLabel(account.connection_status) }}</strong>
          </div>
          <div>
            <span>即時訂閱</span>
            <strong>{{ account.realtime_assigned_count || 0 }} 檔</strong>
          </div>
          <div>
            <span>憑證</span>
            <strong>{{ account.cert_path || "未填寫" }}</strong>
          </div>
          <div>
            <span>最後連線</span>
            <strong>{{ formatTime(account.last_connected_at) }}</strong>
          </div>
          <div>
            <span>帳號能力</span>
            <strong>{{ capabilityLabel(account.account_capabilities) }}</strong>
          </div>
          <div>
            <span>自動恢復</span>
            <strong>{{ recoveryLabel(account) }}</strong>
          </div>
        </div>

        <div v-if="account.connection_error" class="account-error">
          {{ account.connection_error }}
        </div>
        <div v-if="account.recovery_last_error" class="account-error">
          {{ account.recovery_last_error }}
          <span v-if="account.recovery_next_retry_at">
            （下次嘗試：{{ formatTime(account.recovery_next_retry_at) }}）
          </span>
        </div>

        <div v-if="account.realtime_assigned_tickers?.length" class="account-symbols">
          <span
            v-for="ticker in account.realtime_assigned_tickers.slice(0, 8)"
            :key="`${account.id}-${ticker}`"
            class="account-symbol-chip"
          >
            {{ ticker }}
          </span>
          <span v-if="account.realtime_assigned_tickers.length > 8" class="account-symbol-chip muted">
            +{{ account.realtime_assigned_tickers.length - 8 }}
          </span>
        </div>

        <div class="account-actions">
          <button type="button" :disabled="isBusy(account.id)" @click="testAccount(account)">測試連線</button>
          <button type="button" :disabled="isBusy(account.id) || !account.is_enabled" @click="reconnect(account, 'stock')">
            重連股票
          </button>
          <button type="button" :disabled="isBusy(account.id) || !account.is_enabled" @click="reconnect(account, 'futopt')">
            重連期權
          </button>
          <button type="button" :disabled="isBusy(account.id) || !account.is_enabled" @click="reconnect(account)">
            重新登入
          </button>
          <button type="button" :disabled="isBusy(account.id)" @click="openEditModal(account)">編輯</button>
          <button type="button" :disabled="account.is_active || isBusy(account.id)" @click="activate(account)">
            設為使用中
          </button>
          <button class="danger" type="button" :disabled="isBusy(account.id)" @click="remove(account)">刪除</button>
        </div>
      </article>
    </div>

    <FubonAccountFormModal
      :open="modalOpen"
      :account="editingAccount"
      :saving="saving"
      @close="closeModal"
      @save="saveAccount"
    />
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { useFubonAccounts } from "../../composables/useFubonAccounts";
import FubonAccountFormModal from "./FubonAccountFormModal.vue";

const {
  accounts,
  loading,
  error,
  fetchAccounts,
  createAccount,
  updateAccount,
  deleteAccount,
  activateAccount,
  testConnection,
  reconnectAccount,
  startStatusPolling,
  stopStatusPolling,
} = useFubonAccounts();

const modalOpen = ref(false);
const editingAccount = ref(null);
const saving = ref(false);
const busyIds = ref(new Set());
const message = reactive({ type: "success", text: "" });

function setMessage(type, text) {
  message.type = type;
  message.text = text;
}

function setBusy(id, busy) {
  const next = new Set(busyIds.value);
  if (busy) next.add(id);
  else next.delete(id);
  busyIds.value = next;
}

function isBusy(id) {
  return busyIds.value.has(id);
}

function openCreateModal() {
  editingAccount.value = null;
  modalOpen.value = true;
}

function openEditModal(account) {
  editingAccount.value = account;
  modalOpen.value = true;
}

function closeModal() {
  if (saving.value) return;
  modalOpen.value = false;
}

async function saveAccount(payload) {
  saving.value = true;
  setMessage("success", "");
  try {
    let accountId = editingAccount.value?.id;
    if (accountId) {
      await updateAccount(accountId, payload);
    } else {
      const created = await createAccount(payload);
      accountId = created.id;
    }
    modalOpen.value = false;
    if (accountId) {
      const result = await testConnection(accountId);
      setMessage(
        result.success ? "success" : "error",
        result.success ? "帳號已儲存，連線測試成功。" : `帳號已儲存，連線測試失敗：${result.message}`,
      );
    } else {
      setMessage("success", "帳號已儲存。");
    }
  } catch (err) {
    setMessage("error", err?.message || "帳號儲存失敗");
  } finally {
    saving.value = false;
  }
}

async function testAccount(account) {
  setBusy(account.id, true);
  setMessage("success", "");
  try {
    const result = await testConnection(account.id);
    setMessage(result.success ? "success" : "error", result.message || "連線測試完成");
  } catch (err) {
    setMessage("error", err?.message || "連線測試失敗");
  } finally {
    setBusy(account.id, false);
  }
}

async function reconnect(account, marketType = null) {
  setBusy(account.id, true);
  setMessage("success", "");
  try {
    const result = await reconnectAccount(account.id, marketType);
    setMessage(result.success ? "success" : "error", result.message || "富邦重新連線已啟動");
  } catch (err) {
    setMessage("error", err?.message || "富邦重新連線失敗");
  } finally {
    setBusy(account.id, false);
  }
}

async function activate(account) {
  setBusy(account.id, true);
  setMessage("success", "");
  try {
    const result = await activateAccount(account.id);
    setMessage(result.success ? "success" : "error", result.message || "已設為使用中");
  } catch (err) {
    setMessage("error", err?.message || "啟用帳號失敗");
  } finally {
    setBusy(account.id, false);
  }
}

async function remove(account) {
  if (!window.confirm(`刪除 ${account.label}？`)) return;
  setBusy(account.id, true);
  setMessage("success", "");
  try {
    await deleteAccount(account.id);
    setMessage("success", "帳號已刪除。");
  } catch (err) {
    setMessage("error", err?.message || "刪除帳號失敗");
  } finally {
    setBusy(account.id, false);
  }
}

function statusClass(status) {
  if (status === "connected") return "connected";
  if (status === "connecting") return "connecting";
  if (status === "error") return "error";
  return "disconnected";
}

function statusLabel(status) {
  if (status === "connected") return "已連線";
  if (status === "connecting") return "連線中";
  if (status === "error") return "連線失敗";
  return "未連線";
}

function formatTime(value) {
  if (!value) return "尚無";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-TW", { hour12: false });
}

function modeLabel(mode) {
  return mode === "Normal" ? "Normal · 盤中焦點" : "Speed · 自選觀察池";
}

function modeHint(mode) {
  return mode === "Normal"
    ? "目前畫面正在看的 ticker 會優先分配到這組帳號。"
    : "watchlist 與背景即時訂閱會優先分配到這組帳號。";
}

function capabilityLabel(capabilities) {
  if (!Array.isArray(capabilities) || !capabilities.length) return "尚未辨識";
  return capabilities.map((capability) => ({
    stock: "證券",
    futures: "期貨",
    options: "選擇權",
    unknown: "待確認",
  }[capability] || capability)).join("、");
}

function recoveryLabel(account) {
  const state = {
    ready: "正常",
    disconnected: "未連線",
    connecting: "重連中",
    backoff: "等待重試",
    configuration_error: "需修正設定",
  }[account?.recovery_state] || account?.recovery_state || "待命";
  return account?.recovery_attempt ? `${state}（第 ${account.recovery_attempt} 次）` : state;
}

onMounted(() => {
  fetchAccounts().catch(() => {});
  startStatusPolling();
});

onBeforeUnmount(() => {
  stopStatusPolling();
});
</script>

<style scoped>
.fubon-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.settings-section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.settings-section-head h2 {
  font-family: "Syne", sans-serif;
  font-size: 20px;
}

.settings-section-head p {
  margin-top: 5px;
  color: var(--text3);
  line-height: 1.6;
}

.settings-message,
.settings-empty,
.account-error {
  border: 1px solid var(--border2);
  border-radius: 8px;
  padding: 10px 12px;
  background: rgba(17, 25, 39, 0.86);
  color: var(--text2);
}

.settings-message.success {
  border-color: rgba(0, 217, 163, 0.32);
  color: var(--green);
}

.settings-message.error,
.account-error {
  border-color: rgba(255, 77, 106, 0.34);
  color: var(--red);
}

.account-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 12px;
}

.account-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  border: 1px solid var(--border2);
  border-radius: 8px;
  background: rgba(13, 20, 32, 0.92);
  padding: 14px;
}

.account-main,
.account-title-row,
.account-actions {
  display: flex;
  align-items: center;
}

.account-main {
  justify-content: space-between;
  gap: 12px;
}

.account-title-row {
  min-width: 0;
  gap: 10px;
}

.account-title-row h3 {
  font-size: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-sub {
  margin-top: 4px;
  color: var(--text3);
  font-size: 10px;
}

.account-mode-note {
  margin-top: 3px;
  color: var(--text3);
  font-size: 10px;
  line-height: 1.5;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex: 0 0 auto;
  background: var(--text3);
}

.status-dot.connected {
  background: var(--green);
  box-shadow: 0 0 12px rgba(0, 217, 163, 0.52);
}

.status-dot.connecting {
  background: var(--amber);
}

.status-dot.error {
  background: var(--red);
}

.active-badge {
  flex: 0 0 auto;
  border: 1px solid rgba(0, 217, 163, 0.34);
  border-radius: 999px;
  color: var(--green);
  padding: 4px 8px;
  font-size: 10px;
}

.account-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.account-meta div {
  min-width: 0;
}

.account-meta span {
  display: block;
  color: var(--text3);
  font-size: 10px;
  margin-bottom: 3px;
}

.account-meta strong {
  display: block;
  color: var(--text2);
  font-weight: 500;
  word-break: break-all;
  line-height: 1.5;
}

.account-symbols {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.account-symbol-chip {
  border: 1px solid rgba(123, 231, 255, 0.24);
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 10px;
  color: var(--text2);
  background: rgba(123, 231, 255, 0.08);
}

.account-symbol-chip.muted {
  border-color: var(--border2);
  color: var(--text3);
  background: rgba(255, 255, 255, 0.04);
}

.account-actions {
  flex-wrap: wrap;
  gap: 8px;
}

.account-actions button,
.primary-btn {
  min-height: 34px;
  border-radius: 8px;
  border: 1px solid var(--border2);
  background: var(--bg3);
  color: var(--text2);
  padding: 0 10px;
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
  cursor: pointer;
}

.primary-btn {
  border-color: var(--green2);
  color: var(--green);
  background: rgba(0, 217, 163, 0.12);
}

.account-actions button:hover,
.primary-btn:hover {
  border-color: var(--cyan);
  color: var(--text);
}

.account-actions button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.account-actions button.danger {
  border-color: rgba(255, 77, 106, 0.34);
  color: var(--red);
}

@media (max-width: 720px) {
  .settings-section-head {
    flex-direction: column;
  }

  .account-list {
    grid-template-columns: 1fr;
  }

  .account-meta {
    grid-template-columns: 1fr;
  }
}
</style>
