import { reactive } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createPaperApi } from "./paperApi";
import { usePaperAccounts } from "./usePaperAccounts";
import { usePaperBots } from "./usePaperBots";
import { usePaperMargin } from "./usePaperMargin";
import { usePaperReplays } from "./usePaperReplays";

function state() {
  return {
    loading: reactive({ accounts: false, bots: false, replay: false, margin: false }),
    errors: reactive({ accounts: "", bots: "", replay: "", margin: "" }),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("paper trading composable contracts", () => {
  it("aborts owned requests when the dashboard is disposed", async () => {
    vi.stubGlobal("fetch", vi.fn((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    })));
    const api = createPaperApi();

    const pending = api.apiFetch("/accounts");
    expect(api.pendingCount()).toBe(1);
    api.dispose();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
    expect(api.pendingCount()).toBe(0);
  });

  it("loads accounts and preserves the parent form-selection contract", async () => {
    const { loading, errors } = state();
    const apiFetch = vi.fn().mockResolvedValue({ items: [{ id: 4, name: "TMF" }] });
    const accounts = usePaperAccounts({
      apiFetch,
      notify: vi.fn(),
      sectionLoading: loading,
      sectionErrors: errors,
    });
    const botForm = reactive({ account_id: null });
    const replayForm = reactive({ account_id: null });

    await accounts.loadAccounts({ botForm, replayForm });

    expect(apiFetch).toHaveBeenCalledWith("/accounts");
    expect(accounts.accounts.value).toEqual([{ id: 4, name: "TMF" }]);
    expect(botForm.account_id).toBe(4);
    expect(replayForm.account_id).toBe(4);
    expect(loading.accounts).toBe(false);
  });

  it("keeps bot, replay, and margin failures isolated by section", async () => {
    const { loading, errors } = state();
    const notify = vi.fn();
    const apiFetch = vi.fn(async (path) => {
      if (path === "/bots") return { items: [{ id: 2, status: "idle" }] };
      if (path === "/replay/runs") return { items: [{ id: 7 }] };
      if (path === "/accounts/margin/estimate") {
        return { ok: false, error: "provider disconnected", initial_margin_per_contract: 28900 };
      }
      return {};
    });
    const bots = usePaperBots({
      apiFetch,
      notify,
      sectionLoading: loading,
      sectionErrors: errors,
    });
    const replays = usePaperReplays({
      apiFetch,
      notify,
      sectionLoading: loading,
      sectionErrors: errors,
    });
    const accounts = usePaperAccounts({
      apiFetch,
      notify,
      sectionLoading: loading,
      sectionErrors: errors,
    });
    const margin = usePaperMargin({
      apiFetch,
      notify,
      accountForm: accounts.accountForm,
      sectionLoading: loading,
      sectionErrors: errors,
      reloadAccounts: vi.fn(),
    });

    await Promise.all([bots.loadBots(), replays.loadReplayRuns()]);
    await margin.previewAccountMargin();

    expect(bots.bots.value).toHaveLength(1);
    expect(replays.replayRuns.value).toHaveLength(1);
    expect(margin.marginPreview.value.initial_margin_per_contract).toBe(28900);
    expect(errors.margin).toBe("provider disconnected");
    expect(errors.bots).toBe("");
    expect(errors.replay).toBe("");
  });
});
