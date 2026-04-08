<template>
  <aside class="terminal-drawer">
    <div class="terminal-drawer-head">
      <div>
        <div class="terminal-drawer-kicker">Execution Utilities</div>
        <div class="terminal-drawer-title">盤中工具抽屜</div>
      </div>
      <button class="terminal-drawer-close" type="button" @click="$emit('close')">
        收合
      </button>
    </div>

    <div class="terminal-drawer-tabs">
      <button
        class="terminal-drawer-tab"
        :class="{ active: normalizedTab === 'alerts' }"
        type="button"
        @click="$emit('set-right-tab', 'alerts')"
      >
        警報
      </button>
      <button
        class="terminal-drawer-tab"
        :class="{ active: normalizedTab === 'journal' }"
        type="button"
        @click="$emit('set-right-tab', 'journal')"
      >
        快速日誌
      </button>
    </div>

    <div class="terminal-drawer-body">
      <AlertConfigPanel
        v-if="normalizedTab === 'alerts'"
        :alerts="alerts"
        :formatDateTime="formatDateTime"
        :formatAlertTarget="formatAlertTarget"
        :formatAlertSummary="formatAlertSummary"
        :formatAlertStatus="formatAlertStatus"
        :formatAlertType="formatAlertType"
        :getAlertContextSource="getAlertContextSource"
        :getAlertContextGroupName="getAlertContextGroupName"
        :getAlertContextTags="getAlertContextTags"
        :getAlertSnapshotLabel="getAlertSnapshotLabel"
        :isAlertLogOpen="isAlertLogOpen"
        :isAlertLogLoading="isAlertLogLoading"
        :getAlertLogs="getAlertLogs"
        :formatLogSource="formatLogSource"
        :formatAlertMetricValue="formatAlertMetricValue"
        :formatLogMacroContext="formatLogMacroContext"
        :formatLogContextSummary="formatLogContextSummary"
        @open-watch-group="$emit('open-watch-group', $event)"
        @toggle-alert-active="$emit('toggle-alert-active', $event)"
        @toggle-alert-log="$emit('toggle-alert-log', $event)"
        @delete-alert="$emit('delete-alert', $event)"
        @open-alert-modal="$emit('open-alert-modal')"
      />

      <div v-else class="terminal-journal-shell">
        <div class="terminal-journal-summary">
          <div class="terminal-journal-title">快速紀錄 {{ currentTicker || "目前標的" }}</div>
          <div class="terminal-journal-copy">
            專注記下當下情緒、進出場理由與截圖，不離開終端也能留下盤中脈絡。
          </div>
        </div>

        <JournalEntryForm
          :journal-form="journalForm"
          :journal-loading="journalLoading"
          @update-journal-field="$emit('update-journal-field', $event)"
          @add-journal-attachment="$emit('add-journal-attachment')"
          @remove-journal-attachment="$emit('remove-journal-attachment', $event)"
          @save-journal-entry="$emit('save-journal-entry')"
          @reset-journal-form="$emit('reset-journal-form')"
          @delete-journal-entry="$emit('delete-journal-entry', $event)"
        />
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from "vue";

import AlertConfigPanel from "../AlertConfigPanel.vue";
import JournalEntryForm from "../journal/JournalEntryForm.vue";

const props = defineProps({
  rightTab: { type: String, default: "alerts" },
  currentTicker: { type: String, default: "" },
  alerts: { type: Array, default: () => [] },
  alertTriggerLogs: { type: Object, default: () => ({}) },
  alertLogLoading: { type: Object, default: () => ({}) },
  expandedAlertLogId: { type: [Number, String], default: null },
  journalForm: { type: Object, required: true },
  journalLoading: { type: Boolean, required: true },
});

defineEmits([
  "close",
  "set-right-tab",
  "open-watch-group",
  "toggle-alert-active",
  "toggle-alert-log",
  "delete-alert",
  "open-alert-modal",
  "update-journal-field",
  "add-journal-attachment",
  "remove-journal-attachment",
  "save-journal-entry",
  "reset-journal-form",
  "delete-journal-entry",
]);

const normalizedTab = computed(() => (props.rightTab === "journal" ? "journal" : "alerts"));

const ALERT_TYPE_LABELS = {
  price: "價格",
  pct: "漲跌幅",
  rsi: "RSI",
  macd: "MACD",
  volume: "量比",
  basis: "Basis",
  institutional: "法人異常",
  event: "事件提醒",
  market_risk: "市場風險",
};

const ALERT_CONDITION_LABELS = {
  gt: "大於",
  lt: "小於",
  eq: "等於",
  "大於": "大於",
  "小於": "小於",
  "等於": "等於",
  cross_up: "黃金交叉",
  cross_down: "死亡交叉",
  "上穿": "黃金交叉",
  "下穿": "死亡交叉",
  "黃金交叉": "黃金交叉",
  "死亡交叉": "死亡交叉",
  high: "進入高風險",
  medium_or_high: "進入中風險以上",
  risk_off: "進入 risk-off",
  offensive: "進入偏進攻",
};

const MARKET_RISK_VALUE_LABELS = {
  high: "高風險",
  medium: "中風險",
  low: "低風險",
  medium_or_high: "中風險以上",
  risk_off: "risk-off",
  risk_on: "risk-on",
  offensive: "偏進攻",
  balanced: "平衡觀察",
  selective: "選擇性出手",
  defensive: "防守控倉",
};

function formatDateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("zh-TW", { hour12: false });
}

function formatAlertType(alert) {
  return ALERT_TYPE_LABELS[String(alert?.type || "").toLowerCase()] || alert?.type || "警報";
}

function formatAlertCondition(alert) {
  const normalizedType = String(alert?.type || "").toLowerCase();
  const rawCondition = alert?.condition || alert?.cond || "";
  const normalizedCondition = String(rawCondition).toLowerCase();
  if (normalizedType === "institutional") {
    return normalizedCondition === "high" ? "高異常" : "中度以上異常";
  }
  if (normalizedType === "event") {
    return normalizedCondition === "within_days" ? "事件前提醒" : rawCondition || "—";
  }
  return ALERT_CONDITION_LABELS[rawCondition] || ALERT_CONDITION_LABELS[normalizedCondition] || rawCondition || "—";
}

function formatAlertTarget(alert) {
  if (alert?.condition_payload?.target_label) return alert.condition_payload.target_label;
  if (String(alert?.type || "").toLowerCase() === "market_risk") return "市場";
  if (String(alert?.ticker || "").toUpperCase() === "MARKET") return "市場";
  return alert?.ticker || "—";
}

function formatAlertMetricValue(alert, value) {
  if (value == null || value === "") return "—";
  const normalizedType = String(alert?.type || "").toLowerCase();
  if (normalizedType === "market_risk") {
    return MARKET_RISK_VALUE_LABELS[String(value)] || String(value);
  }
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return String(value);
  if (normalizedType === "basis" && alert?.condition_payload?.metric === "basis_pct") {
    return `${numericValue.toFixed(2)}%`;
  }
  if (normalizedType === "event") return `${numericValue.toFixed(0)} 日內`;
  if (normalizedType === "pct") return `${numericValue.toFixed(2)}%`;
  if (normalizedType === "volume") return `${numericValue.toFixed(2)}x`;
  return numericValue.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatAlertSummary(alert) {
  const condition = formatAlertCondition(alert);
  const valueLabel = formatAlertMetricValue(alert, alert?.value);
  return valueLabel === "—"
    ? `${formatAlertType(alert)} · ${condition}`
    : `${formatAlertType(alert)} · ${condition} ${valueLabel}`;
}

function formatAlertStatus(alert) {
  if (alert?.triggered) return "已觸發";
  return alert?.active ? "監控中" : "已暫停";
}

function getAlertLogs(alert) {
  return props.alertTriggerLogs?.[String(alert?.id ?? "")] || [];
}

function isAlertLogOpen(alert) {
  return String(props.expandedAlertLogId ?? "") === String(alert?.id ?? "");
}

function isAlertLogLoading(alert) {
  return Boolean(props.alertLogLoading?.[String(alert?.id ?? "")]);
}

function formatLogSource(log) {
  return log?.payload?.quote?.source || "local_db";
}

function formatLogMacroContext(log) {
  const summary = log?.payload?.macro_summary || log?.payload?.quote?.macro_summary;
  if (!summary) return "";
  const riskLabel = MARKET_RISK_VALUE_LABELS[String(summary.overall_risk)] || summary.overall_risk;
  const postureLabel = MARKET_RISK_VALUE_LABELS[String(summary.trade_posture)] || summary.trade_posture;
  return `市場 ${riskLabel} / ${postureLabel}`;
}

function getAlertContextSource(alert) {
  const source = String(alert?.condition_payload?.context_source || "").toLowerCase();
  if (source === "watchlist") return "來源：觀察池";
  if (source === "watchlist_group") return "來源：觀察群組";
  if (!source) return "";
  return `來源：${source}`;
}

function getAlertContextGroupName(alert) {
  return String(alert?.condition_payload?.context_group_name || "").trim();
}

function getAlertContextTags(alert) {
  return Array.isArray(alert?.condition_payload?.context_tags)
    ? alert.condition_payload.context_tags.filter(Boolean).slice(0, 4)
    : [];
}

function formatLogContextSummary(log) {
  const source = String(log?.payload?.context_source || "").toLowerCase();
  const parts = [];
  if (source === "watchlist_group") parts.push("來源：觀察群組");
  else if (source === "watchlist") parts.push("來源：觀察池");
  else if (source) parts.push(`來源：${source}`);
  if (log?.payload?.context_group_name) parts.push(`群組：${log.payload.context_group_name}`);
  return parts.join(" / ");
}

function getAlertSnapshotLabel(alert) {
  const snapshotPrice = alert?.condition_payload?.snapshot_price;
  if (snapshotPrice == null || snapshotPrice === "") return "";
  return `快照 ${formatAlertMetricValue({ type: "price" }, snapshotPrice)}`;
}
</script>

<style scoped>
.terminal-drawer {
  width: 380px;
  min-width: 380px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  background:
    linear-gradient(180deg, rgba(8, 13, 21, 0.98), rgba(6, 10, 18, 0.98)),
    radial-gradient(circle at top right, rgba(255, 209, 102, 0.08), transparent 32%);
}

.terminal-drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 16px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.terminal-drawer-kicker {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text3);
}

.terminal-drawer-title {
  margin-top: 4px;
  font-family: "Syne", sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: var(--text1);
}

.terminal-drawer-close {
  padding: 7px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  font-size: 10px;
}

.terminal-drawer-tabs {
  display: flex;
  gap: 8px;
  padding: 10px 16px 0;
}

.terminal-drawer-tab {
  flex: 1;
  padding: 9px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  font-size: 11px;
}

.terminal-drawer-tab.active {
  border-color: rgba(123, 231, 255, 0.26);
  background: rgba(123, 231, 255, 0.12);
  color: #d7fbff;
}

.terminal-drawer-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 14px 16px 16px;
}

.terminal-journal-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.terminal-journal-summary {
  padding: 12px;
  border: 1px solid rgba(123, 231, 255, 0.14);
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(8, 24, 32, 0.96), rgba(8, 14, 24, 0.96));
}

.terminal-journal-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text1);
}

.terminal-journal-copy {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--text3);
}

@media (max-width: 1400px) {
  .terminal-drawer {
    width: 340px;
    min-width: 340px;
  }
}

@media (max-width: 960px) {
  .terminal-drawer {
    position: fixed;
    inset: 72px 0 72px auto;
    z-index: 55;
    width: min(100vw, 380px);
    min-width: 0;
    box-shadow: -18px 0 40px rgba(0, 0, 0, 0.32);
  }
}
</style>
