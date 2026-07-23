import { reactive, ref } from "vue";

export function usePaperAccounts({ apiFetch, notify, sectionLoading, sectionErrors }) {
  const accounts = ref([]);
  const creatingAccount = ref(false);
  const deletingAccounts = reactive({});
  const accountForm = reactive({
    name: "TMF 模擬帳戶",
    product_symbol: "TMF",
    starting_equity: 100000,
  });
  const riskForm = reactive({
    daily_loss_limit_pct: 0.05,
    max_drawdown_pct: 0.15,
    max_contracts_hard: 10,
    max_margin_usage_pct: 0.6,
    risk_per_trade_pct: 0.02,
    stress_points: 2000,
    total_position_risk_pct: 0.2,
  });

  async function loadAccounts({ botForm, replayForm } = {}) {
    sectionLoading.accounts = true;
    sectionErrors.accounts = "";
    try {
      const data = await apiFetch("/accounts");
      accounts.value = data.items || [];
      if (accounts.value.length && botForm && !botForm.account_id) {
        botForm.account_id = accounts.value[0].id;
      }
      if (accounts.value.length && replayForm && !replayForm.account_id) {
        replayForm.account_id = accounts.value[0].id;
      }
    } catch (error) {
      sectionErrors.accounts = error.message || "未知錯誤";
    } finally {
      sectionLoading.accounts = false;
    }
  }

  async function createAccount({ reload, marginSyncErrorMessage } = {}) {
    creatingAccount.value = true;
    try {
      const account = await apiFetch("/accounts", {
        method: "POST",
        body: JSON.stringify({
          ...accountForm,
          risk_config: { ...riskForm },
          cost_model: {},
        }),
      });
      notify(
        account.margin_sync_error ? marginSyncErrorMessage : "帳戶建立成功",
        account.margin_sync_error ? "error" : "success",
      );
      if (reload) await reload();
      return account;
    } catch (error) {
      notify(error.message, "error");
      return null;
    } finally {
      creatingAccount.value = false;
    }
  }

  async function removeAccount(account) {
    deletingAccounts[account.id] = true;
    try {
      await apiFetch(`/accounts/${account.id}`, { method: "DELETE" });
      notify("帳戶已刪除", "success");
      return true;
    } catch (error) {
      notify(error.message, "error");
      return false;
    } finally {
      delete deletingAccounts[account.id];
    }
  }

  return {
    accounts,
    accountForm,
    riskForm,
    creatingAccount,
    deletingAccounts,
    loadAccounts,
    createAccount,
    removeAccount,
  };
}
