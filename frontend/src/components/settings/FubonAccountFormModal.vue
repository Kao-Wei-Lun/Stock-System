<template>
  <div class="settings-modal-overlay" :class="{ open }" role="dialog" aria-modal="true">
    <form class="settings-modal" @submit.prevent="submitForm">
      <div class="settings-modal-head">
        <div>
          <div class="settings-modal-kicker">富邦 Neo API</div>
          <h3>{{ account ? "編輯帳號" : "新增帳號" }}</h3>
        </div>
        <button class="icon-text-btn" type="button" @click="$emit('close')">關閉</button>
      </div>

      <div class="settings-form-grid">
        <label class="settings-field">
          <span>帳號名稱</span>
          <input v-model.trim="form.label" required maxlength="100" placeholder="主帳號" />
        </label>

        <label class="settings-field">
          <span>身分證字號</span>
          <input v-model.trim="form.user_id" required maxlength="50" autocomplete="username" />
        </label>

        <label class="settings-field">
          <span>電子平台密碼</span>
          <input
            v-model="form.password"
            :required="!account"
            type="password"
            autocomplete="current-password"
            :placeholder="account ? '留空代表不變更' : ''"
          />
        </label>

        <label class="settings-field">
          <span>API Key</span>
          <input
            v-model.trim="form.api_key"
            :required="!account"
            type="password"
            autocomplete="off"
            :placeholder="account ? '留空代表不變更' : ''"
          />
        </label>

        <label class="settings-field wide">
          <span>憑證檔路徑</span>
          <input v-model.trim="form.cert_path" maxlength="500" placeholder="C:\CAFubon\...\account.pfx" />
        </label>

        <label class="settings-field">
          <span>憑證密碼</span>
          <input
            v-model="form.cert_password"
            type="password"
            autocomplete="off"
            :placeholder="account ? '留空代表不變更' : ''"
          />
        </label>

        <label class="settings-field">
          <span>行情模式</span>
          <select v-model="form.ws_mode">
            <option value="Speed">Speed</option>
            <option value="Normal">Normal</option>
          </select>
        </label>
      </div>

      <label class="settings-check">
        <input v-model="form.is_enabled" type="checkbox" />
        <span>啟用此帳號</span>
      </label>

      <div class="settings-secure-note">
        密碼與 API Key 會加密後存入本機資料庫。
      </div>

      <div class="settings-modal-actions">
        <button class="secondary-btn" type="button" :disabled="saving" @click="$emit('close')">取消</button>
        <button class="primary-btn" type="submit" :disabled="saving">
          {{ saving ? "儲存中" : "儲存並測試連線" }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { reactive, watch } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  account: { type: Object, default: null },
  saving: { type: Boolean, default: false },
});

const emit = defineEmits(["close", "save"]);

const form = reactive({
  label: "",
  user_id: "",
  password: "",
  cert_path: "",
  cert_password: "",
  api_key: "",
  ws_mode: "Speed",
  is_enabled: true,
});

function resetForm() {
  const account = props.account;
  form.label = account?.label || "";
  form.user_id = account?.user_id || "";
  form.password = "";
  form.cert_path = account?.cert_path || "";
  form.cert_password = "";
  form.api_key = "";
  form.ws_mode = account?.ws_mode || "Speed";
  form.is_enabled = account?.is_enabled !== false;
}

function submitForm() {
  const payload = {
    label: form.label,
    user_id: form.user_id,
    cert_path: form.cert_path,
    ws_mode: form.ws_mode,
    is_enabled: form.is_enabled,
  };
  if (form.password) payload.password = form.password;
  if (form.cert_password) payload.cert_password = form.cert_password;
  if (form.api_key) payload.api_key = form.api_key;
  if (!props.account) {
    payload.password = form.password;
    payload.api_key = form.api_key;
    payload.cert_password = form.cert_password;
  }
  emit("save", payload);
}

watch(
  () => [props.open, props.account],
  () => resetForm(),
  { immediate: true },
);
</script>

<style scoped>
.settings-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 900;
  display: none;
  align-items: center;
  justify-content: center;
  padding: 18px;
  background: rgba(0, 0, 0, 0.68);
}

.settings-modal-overlay.open {
  display: flex;
}

.settings-modal {
  width: min(720px, 100%);
  max-height: 88vh;
  overflow: auto;
  border: 1px solid var(--border2);
  border-radius: 8px;
  background: rgba(13, 20, 32, 0.98);
  padding: 18px;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.36);
}

.settings-modal-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.settings-modal-kicker {
  font-size: 10px;
  color: var(--text3);
  letter-spacing: 0.08em;
}

.settings-modal h3 {
  margin-top: 4px;
  font-family: "Syne", sans-serif;
  font-size: 18px;
}

.settings-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.settings-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.settings-field.wide {
  grid-column: 1 / -1;
}

.settings-field span,
.settings-check span {
  font-size: 10px;
  color: var(--text3);
}

.settings-field input,
.settings-field select {
  min-height: 38px;
  width: 100%;
  border: 1px solid var(--border2);
  border-radius: 6px;
  background: var(--bg3);
  color: var(--text);
  font-family: "JetBrains Mono", monospace;
  font-size: 12px;
  padding: 8px 10px;
  outline: none;
}

.settings-field input:focus,
.settings-field select:focus {
  border-color: var(--cyan);
}

.settings-check {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}

.settings-check input {
  accent-color: var(--green);
}

.settings-secure-note {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 217, 163, 0.22);
  border-radius: 8px;
  color: var(--text2);
  background: rgba(0, 217, 163, 0.07);
}

.settings-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

.primary-btn,
.secondary-btn,
.icon-text-btn {
  min-height: 36px;
  border-radius: 8px;
  font-family: "JetBrains Mono", monospace;
  cursor: pointer;
}

.primary-btn {
  border: 1px solid var(--green2);
  background: rgba(0, 217, 163, 0.18);
  color: var(--green);
  padding: 0 14px;
}

.secondary-btn,
.icon-text-btn {
  border: 1px solid var(--border2);
  background: var(--bg3);
  color: var(--text2);
  padding: 0 12px;
}

.primary-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .settings-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
