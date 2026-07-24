import { onBeforeUnmount, onMounted, ref } from "vue";
import { secureFetch } from "../utils/lanAccess";
import { createVisibilityPoller } from "../utils/visibilityPoller";

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
  const response = await secureFetch("/api/settings/fubon-accounts/status");
  const contentType = response.headers?.get?.("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(payload?.detail || `HTTP ${response.status}`);
  }
  return {
    accounts: payload?.accounts || [],
    warmup: payload?.warmup || null,
  };
}

function resolveStatus(accounts, warmup) {
  if (!accounts.length) return "unconfigured";
  if (["scheduled", "running"].includes(warmup?.state)) return "connecting";
  if (warmup?.state === "failed" && !(warmup?.connected_account_count > 0)) return "error";
  const activeAccount = accounts.find((account) => account.is_active)
    || accounts.find((account) => account.is_enabled)
    || accounts[0];
  return activeAccount?.connection_status || "disconnected";
}

export function useFubonWorkspaceStatus({ pollMs = 15_000 } = {}) {
  const accounts = ref([]);
  const fubonStatus = ref("unconfigured");
  const fubonProgress = ref({
    state: "unconfigured",
    connected: 0,
    configured: 0,
  });
  const showFubonOnboardingBanner = ref(false);
  const dismissed = ref(false);

  async function refreshFubonWorkspaceStatus() {
    try {
      const payload = await requestFubonStatuses();
      const nextAccounts = payload.accounts;
      const warmup = payload.warmup;
      accounts.value = nextAccounts;
      fubonStatus.value = resolveStatus(nextAccounts, warmup);
      fubonProgress.value = {
        state: warmup?.state || fubonStatus.value,
        connected: Number(warmup?.connected_account_count || 0),
        configured: Number(warmup?.configured_account_count ?? nextAccounts.length),
      };
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

  const statusPoller = createVisibilityPoller(refreshFubonWorkspaceStatus, {
    intervalMs: pollMs,
    runImmediately: true,
  });

  onMounted(() => {
    dismissed.value = readDismissedFlag();
    statusPoller.start();
  });

  onBeforeUnmount(() => {
    statusPoller.stop();
  });

  return {
    accounts,
    fubonStatus,
    fubonProgress,
    showFubonOnboardingBanner,
    dismissFubonOnboardingBanner,
    refreshFubonWorkspaceStatus,
  };
}
