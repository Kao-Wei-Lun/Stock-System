import { computed, ref } from "vue";

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers?.get?.("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const error = new Error(payload?.detail || `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function jsonRequest(method, body) {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function useFubonAccounts() {
  const accounts = ref([]);
  const loading = ref(false);
  const error = ref("");
  const statusPolling = ref(null);

  const activeAccount = computed(() => accounts.value.find((account) => account.is_active) || null);

  async function fetchAccounts() {
    loading.value = true;
    error.value = "";
    try {
      const data = await request("/api/settings/fubon-accounts");
      accounts.value = data.accounts || [];
    } catch (err) {
      error.value = err?.message || "讀取帳號失敗";
      throw err;
    } finally {
      loading.value = false;
    }
  }

  async function refreshStatuses() {
    const data = await request("/api/settings/fubon-accounts/status");
    const statuses = data.accounts || [];
    statuses.forEach((status) => {
      const account = accounts.value.find((item) => item.id === status.id);
      if (!account) return;
      account.connection_status = status.connection_status;
      account.connection_error = status.connection_error;
      account.last_connected_at = status.last_connected_at;
      account.is_active = status.is_active;
      account.is_enabled = status.is_enabled;
      account.realtime_assigned_count = status.realtime_assigned_count || 0;
      account.realtime_assigned_tickers = Array.isArray(status.realtime_assigned_tickers)
        ? status.realtime_assigned_tickers
        : [];
      account.realtime_resolved_tickers = Array.isArray(status.realtime_resolved_tickers)
        ? status.realtime_resolved_tickers
        : [];
      account.realtime_ws_mode = status.realtime_ws_mode || account.ws_mode;
      account.realtime_connected = Boolean(status.realtime_connected);
    });
  }

  async function createAccount(formData) {
    const data = await request("/api/settings/fubon-accounts", jsonRequest("POST", formData));
    await fetchAccounts();
    return data;
  }

  async function updateAccount(id, formData) {
    const data = await request(`/api/settings/fubon-accounts/${id}`, jsonRequest("PUT", formData));
    await fetchAccounts();
    return data;
  }

  async function deleteAccount(id) {
    const data = await request(`/api/settings/fubon-accounts/${id}`, { method: "DELETE" });
    await fetchAccounts();
    return data;
  }

  async function activateAccount(id) {
    const data = await request(`/api/settings/fubon-accounts/${id}/activate`, { method: "POST" });
    await fetchAccounts();
    return data;
  }

  async function testConnection(id) {
    const data = await request(`/api/settings/fubon-accounts/${id}/test`, { method: "POST" });
    await fetchAccounts();
    return data;
  }

  async function reconnectAccount(id, marketType = null) {
    const options = marketType
      ? jsonRequest("POST", { market_type: marketType })
      : { method: "POST" };
    const data = await request(`/api/settings/fubon-accounts/${id}/reconnect`, options);
    await refreshStatuses();
    return data;
  }

  function startStatusPolling() {
    stopStatusPolling();
    statusPolling.value = window.setInterval(() => {
      refreshStatuses().catch(() => {});
    }, 10_000);
  }

  function stopStatusPolling() {
    if (statusPolling.value) {
      window.clearInterval(statusPolling.value);
      statusPolling.value = null;
    }
  }

  return {
    accounts,
    activeAccount,
    loading,
    error,
    fetchAccounts,
    refreshStatuses,
    createAccount,
    updateAccount,
    deleteAccount,
    activateAccount,
    testConnection,
    reconnectAccount,
    startStatusPolling,
    stopStatusPolling,
  };
}
