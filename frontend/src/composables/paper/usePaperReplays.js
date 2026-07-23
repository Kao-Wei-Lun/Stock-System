import { reactive, ref } from "vue";

export function usePaperReplays({ apiFetch, notify, sectionLoading, sectionErrors }) {
  const replayRuns = ref([]);
  const replayResult = ref(null);
  const runningReplay = ref(false);
  const replayStrategyForm = reactive({
    strategy_type: "v2",
    v2_variant: "v2_winrate_candidate",
    stop_loss_points: 60,
    take_profit_points: 120,
  });
  const replayForm = reactive({
    account_id: null,
    start_date: "",
    end_date: "",
  });

  async function loadReplayRuns() {
    sectionLoading.replay = true;
    sectionErrors.replay = "";
    try {
      const data = await apiFetch("/replay/runs");
      replayRuns.value = data.items || [];
    } catch (error) {
      sectionErrors.replay = error.message || "未知錯誤";
    } finally {
      sectionLoading.replay = false;
    }
  }

  async function runReplay(buildStrategyConfig) {
    runningReplay.value = true;
    replayResult.value = null;
    try {
      const data = await apiFetch("/replay/run", {
        method: "POST",
        body: JSON.stringify({
          ...replayForm,
          strategy_config: buildStrategyConfig(replayStrategyForm),
        }),
      });
      replayResult.value = data.result;
      notify("回放完成", "success");
      await loadReplayRuns();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      runningReplay.value = false;
    }
  }

  return {
    replayRuns,
    replayResult,
    runningReplay,
    replayStrategyForm,
    replayForm,
    loadReplayRuns,
    runReplay,
  };
}
