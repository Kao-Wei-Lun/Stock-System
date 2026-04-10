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
    startStatusPolling,
    stopStatusPolling,
  };
}
