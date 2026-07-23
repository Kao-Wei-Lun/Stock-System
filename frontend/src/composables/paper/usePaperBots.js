import { computed, reactive, ref } from "vue";

import { createVisibilityPoller } from "../../utils/visibilityPoller";

export function usePaperBots({ apiFetch, notify, sectionLoading, sectionErrors }) {
  const bots = ref([]);
  const liveBotState = ref(null);
  const creatingBot = ref(false);
  const startingAllBots = ref(false);
  const deletingBots = reactive({});
  const botForm = reactive({
    account_id: null,
    name: "TMF 日盤 Bot",
    mode: "realtime",
    holding_policy: "day_only",
  });
  const botStrategyForm = reactive({
    strategy_type: "v2",
    v2_variant: "v2_winrate_candidate",
    stop_loss_points: 60,
    take_profit_points: 120,
  });
  const runningBotIds = computed(() => (
    bots.value.filter((bot) => bot.status === "running").map((bot) => bot.id)
  ));
  const startableBotCount = computed(() => (
    bots.value.filter((bot) => bot.status !== "running").length
  ));
  const activeBotStatusClass = computed(() => (
    bots.value.some((bot) => bot.status === "running") ? "running" : "idle"
  ));
  const activeBotStatusLabel = computed(() => {
    const running = bots.value.filter((bot) => bot.status === "running");
    return running.length ? `${running.length} Bot 運行中` : "無運行 Bot";
  });
  const directionLabel = computed(() => {
    const direction = liveBotState.value?.direction;
    return { long: "📈 做多", short: "📉 做空", neutral: "⏸ 觀望" }[direction] || direction || "--";
  });
  const dataSourceLabel = computed(() => {
    const source = liveBotState.value?.data_source;
    return { fubon_neo: "富邦 API" }[source] || source || "--";
  });

  async function loadBots() {
    sectionLoading.bots = true;
    sectionErrors.bots = "";
    try {
      const data = await apiFetch("/bots");
      bots.value = data.items || [];
    } catch (error) {
      sectionErrors.bots = error.message || "未知錯誤";
    } finally {
      sectionLoading.bots = false;
    }
  }

  async function createBot(buildStrategyConfig) {
    creatingBot.value = true;
    try {
      await apiFetch("/bots", {
        method: "POST",
        body: JSON.stringify({
          ...botForm,
          strategy_config: buildStrategyConfig(botStrategyForm),
        }),
      });
      notify("Bot 建立成功", "success");
      await loadBots();
    } catch (error) {
      notify(error.message, "error");
    } finally {
      creatingBot.value = false;
    }
  }

  async function removeBot(bot) {
    deletingBots[bot.id] = true;
    try {
      await apiFetch(`/bots/${bot.id}`, { method: "DELETE" });
      notify("Bot 已刪除", "success");
      if (liveBotState.value?.bot_id === bot.id) liveBotState.value = null;
      await loadBots();
      return true;
    } catch (error) {
      notify(error.message, "error");
      return false;
    } finally {
      delete deletingBots[bot.id];
    }
  }

  async function startBot(botId) {
    try {
      const data = await apiFetch(`/bots/${botId}/start`, { method: "POST" });
      notify(`Bot ${botId} 已啟動`, "success");
      liveBotState.value = data.bot;
      await loadBots();
      startPolling();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function startAllBots() {
    startingAllBots.value = true;
    try {
      const data = await apiFetch("/bots/start-all", { method: "POST" });
      const firstLive = (data.items || []).find((item) => item.bot)?.bot;
      if (firstLive) liveBotState.value = firstLive;
      await loadBots();
      if (runningBotIds.value.length) startPolling();
      if (data.failed_count) {
        notify(`已啟動 ${data.started_count || 0} 個 Bot，${data.failed_count} 個失敗`, "error");
      } else if (data.started_count) {
        notify(`已啟動 ${data.started_count} 個 Bot`, "success");
      } else if (data.already_running_count) {
        notify("所有 Bot 已在運行中", "success");
      } else {
        notify("沒有可啟動的 Bot", "info");
      }
    } catch (error) {
      notify(error.message, "error");
    } finally {
      startingAllBots.value = false;
    }
  }

  async function stopBot(botId) {
    try {
      const data = await apiFetch(`/bots/${botId}/stop`, { method: "POST" });
      notify(`Bot ${botId} 已停止`, "success");
      liveBotState.value = data.bot;
      await loadBots();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  async function refreshBotState(botId) {
    try {
      liveBotState.value = await apiFetch(`/bots/${botId}/state`);
    } catch {
      // Polling failures are represented by the persisted bot list.
    }
  }

  async function pollRunningBots() {
    const ids = runningBotIds.value;
    if (!ids.length) {
      stopPolling();
      return;
    }
    for (const id of ids) {
      try {
        const state = await apiFetch(`/bots/${id}/state`);
        const bot = bots.value.find((item) => item.id === id);
        if (bot) {
          bot.bar_count = state.bar_count;
          bot.status = state.status;
          bot.strategy_config = state.strategy_config || bot.strategy_config;
        }
        if (liveBotState.value?.bot_id === id || ids.length === 1) {
          liveBotState.value = state;
        }
      } catch {
        // A later poll can recover without blanking the last known state.
      }
    }
  }

  const botPoller = createVisibilityPoller(pollRunningBots, { intervalMs: 3000 });
  function startPolling() {
    botPoller.start();
  }
  function stopPolling() {
    botPoller.stop();
  }

  return {
    bots,
    liveBotState,
    creatingBot,
    startingAllBots,
    deletingBots,
    botForm,
    botStrategyForm,
    runningBotIds,
    startableBotCount,
    activeBotStatusClass,
    activeBotStatusLabel,
    directionLabel,
    dataSourceLabel,
    loadBots,
    createBot,
    removeBot,
    startBot,
    startAllBots,
    stopBot,
    refreshBotState,
    startPolling,
    stopPolling,
  };
}
