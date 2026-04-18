import { onBeforeUnmount, onMounted, ref } from "vue";

const ONBOARDING_DISMISS_KEY = "quantvision:fubon-onboarding-dismissed";

function readDismissedFlag() {
  try {
    return window.localStorage.getItem(ONBOARDING_DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

function writeDismissedFlag(value) {
  try {
    if (value) {
      window.localStorage.setItem(ONBOARDING_DISMISS_KEY, "1");
      return;
    }
    window.localStorage.removeItem(ONBOARDING_DISMISS_KEY);
  } catch {
    // Ignore storage failures in restricted browser environments.
  }
}

async function requestFubonStatuses() {
  const response = await fetch("/api/settings/fubon-accounts/status");
  const contentType = response.headers?.get?.("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(payload?.detail || `HTTP ${response.status}`);
  }
  return payload?.accounts || [];
}

function resolveStatus(accounts) {
  if (!accounts.length) return "unconfigured";
  const activeAccount = accounts.find((account) => account.is_active)
    || accounts.find((account) => account.is_enabled)
    || accounts[0];
  return activeAccount?.connection_status || "disconnected";
}

export function useFubonWorkspaceStatus({ pollMs = 15_000 } = {}) {
  const accounts = ref([]);
  const fubonStatus = ref("unconfigured");
  const showFubonOnboardingBanner = ref(false);
  const dismissed = ref(false);
  let pollingId = null;

  async function refreshFubonWorkspaceStatus() {
    try {
      const nextAccounts = await requestFubonStatuses();
      accounts.value = nextAccounts;
      fubonStatus.value = resolveStatus(nextAccounts);
      showFubonOnboardingBanner.value = !dismissed.value && nextAccounts.length === 0;
    } catch {
      fubonStatus.value = accounts.value.length ? "error" : "unconfigured";
      showFubonOnboardingBanner.value = !dismissed.value && accounts.value.length === 0;
    }
  }

  function dismissFubonOnboardingBanner() {
    dismissed.value = true;
    showFubonOnboardingBanner.value = false;
    writeDismissedFlag(true);
  }

  function stopPolling() {
    if (pollingId !== null) {
      window.clearInterval(pollingId);
      pollingId = null;
    }
  }

  function startPolling() {
    stopPolling();
    pollingId = window.setInterval(() => {
      refreshFubonWorkspaceStatus().catch(() => {});
    }, pollMs);
  }

  onMounted(() => {
    dismissed.value = readDismissedFlag();
    void refreshFubonWorkspaceStatus();
    startPolling();
  });

  onBeforeUnmount(() => {
    stopPolling();
  });

  return {
    accounts,
    fubonStatus,
    showFubonOnboardingBanner,
    dismissFubonOnboardingBanner,
    refreshFubonWorkspaceStatus,
  };
}
