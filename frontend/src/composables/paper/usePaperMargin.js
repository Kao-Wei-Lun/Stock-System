import { reactive, ref } from "vue";

export function usePaperMargin({
  apiFetch,
  notify,
  accountForm,
  sectionLoading,
  sectionErrors,
  reloadAccounts,
}) {
  const marginPreview = ref(null);
  const marginPreviewLoading = ref(false);
  const refreshingAllMargins = ref(false);
  const refreshingAccountMargins = reactive({});

  async function previewAccountMargin({ silent = false } = {}) {
    marginPreviewLoading.value = true;
    sectionLoading.margin = true;
    sectionErrors.margin = "";
    try {
      const data = await apiFetch("/accounts/margin/estimate", {
        method: "POST",
        body: JSON.stringify({ product_symbol: accountForm.product_symbol || "TMF" }),
      });
      marginPreview.value = data;
      if (!data.ok) {
        sectionErrors.margin = data.error || data.margin_sync_error
          || "供應商未回傳最新值，已保留可用的持久化值";
      }
      if (!silent) {
        notify(data.ok ? "保證金預查完成" : "已使用預設保證金", data.ok ? "success" : "error");
      }
    } catch (error) {
      sectionErrors.margin = error.message || "未知錯誤";
      if (!silent) notify(error.message, "error");
    } finally {
      marginPreviewLoading.value = false;
      sectionLoading.margin = false;
    }
  }

  async function refreshAccountMargin(account) {
    refreshingAccountMargins[account.id] = true;
    sectionErrors.margin = "";
    try {
      const data = await apiFetch(`/accounts/${account.id}/margin/refresh`, { method: "POST" });
      notify(
        data.ok ? "保證金已更新" : "保證金更新失敗，已保留可用值",
        data.ok ? "success" : "error",
      );
      if (!data.ok) {
        sectionErrors.margin = data.error || data.margin_sync_error
          || "供應商未回傳最新值，已保留既有保證金";
      }
      await reloadAccounts();
    } catch (error) {
      sectionErrors.margin = error.message || "未知錯誤";
      notify(error.message, "error");
    } finally {
      delete refreshingAccountMargins[account.id];
    }
  }

  async function refreshAllMargins() {
    refreshingAllMargins.value = true;
    sectionErrors.margin = "";
    try {
      const data = await apiFetch("/accounts/margins/refresh", { method: "POST" });
      notify(
        data.failed ? `已更新 ${data.success}/${data.total} 個帳戶` : "全部保證金已更新",
        data.failed ? "error" : "success",
      );
      if (data.failed) {
        sectionErrors.margin = `${data.failed} 個帳戶更新失敗，已保留各帳戶最後可用值`;
      }
      await reloadAccounts();
    } catch (error) {
      sectionErrors.margin = error.message || "未知錯誤";
      notify(error.message, "error");
    } finally {
      refreshingAllMargins.value = false;
    }
  }

  return {
    marginPreview,
    marginPreviewLoading,
    refreshingAllMargins,
    refreshingAccountMargins,
    previewAccountMargin,
    refreshAccountMargin,
    refreshAllMargins,
  };
}
