<template>
  <div class="right-panel">
    <div class="rp-tabs">
      <div class="rtab" :class="{ active: rightTab === 'indicators' }" @click="$emit('set-right-tab', 'indicators')">指標</div>
      <div class="rtab" :class="{ active: rightTab === 'alerts' }" @click="$emit('set-right-tab', 'alerts')">警報</div>
      <div class="rtab" :class="{ active: rightTab === 'backtest' }" @click="$emit('set-right-tab', 'backtest')">回測</div>
      <div class="rtab" :class="{ active: rightTab === 'journal' }" @click="$emit('set-right-tab', 'journal')">日誌</div>
      <div class="rtab" :class="{ active: rightTab === 'db' }" @click="$emit('set-right-tab', 'db')">資料庫</div>
    </div>

    <div v-show="rightTab === 'indicators'" class="rp-content">
      <div class="ind-group">
        <div class="ind-group-title">指標模板</div>
        <div class="preset-grid">
          <button class="preset-chip" @click="$emit('apply-indicator-preset', 'trend')">趨勢模板</button>
          <button class="preset-chip" @click="$emit('apply-indicator-preset', 'swing')">擺盪模板</button>
          <button class="preset-chip" @click="$emit('apply-indicator-preset', 'volume')">量價模板</button>
          <button class="preset-chip" @click="$emit('apply-indicator-preset', 'clean')">清爽模板</button>
        </div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">趨勢疊加</div>
        <div v-for="row in overlayRows" :key="row.key" class="ind-row">
          <div>
            <div class="ind-name">{{ row.label }}</div>
            <div v-if="row.hint" class="ind-hint">{{ row.hint }}</div>
          </div>
          <div class="ind-row-actions">
            <div class="ind-val" :style="{ color: row.color }">{{ row.value }}</div>
            <div class="ind-toggle" :class="{ on: activeInd[row.key] }" @click="$emit('toggle-indicator', row.key)"></div>
          </div>
        </div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">副圖面板</div>
        <div v-for="row in panelRows" :key="row.key" class="ind-row">
          <div>
            <div class="ind-name">{{ row.label }}</div>
            <div v-if="row.hint" class="ind-hint">{{ row.hint }}</div>
          </div>
          <div class="ind-row-actions">
            <div class="ind-val" :class="row.valueClass">{{ row.value }}</div>
            <div class="ind-toggle" :class="{ on: activePanels[row.key] }" @click="$emit('toggle-panel', row.key)"></div>
          </div>
        </div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">指標參數</div>
        <div v-for="section in settingSections" :key="section.title" class="setting-section">
          <div class="setting-section-title">{{ section.title }}</div>
          <div class="setting-grid">
            <label v-for="setting in section.items" :key="setting.key" class="setting-row">
              <span class="setting-label">{{ setting.label }}</span>
              <input
                class="setting-input"
                type="number"
                :step="setting.step"
                :min="setting.min"
                :max="setting.max"
                :value="indicatorSettings[setting.key]"
                @input="$emit('update-indicator-setting', { key: setting.key, value: $event.target.value })"
              />
              <span class="setting-range">{{ setting.range }}</span>
            </label>
          </div>
        </div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">技術面總結</div>
        <div class="tech-summary">
          <div v-for="(item, idx) in indicatorSnapshot.techSummaryItems || []" :key="idx">
            <span :class="item.cls">{{ item.text }}</span>
          </div>
          <div v-if="indicatorSnapshot.techSummaryVerdict" style="margin-top:8px">
            <span :class="indicatorSnapshot.techSummaryVerdict.cls">{{ indicatorSnapshot.techSummaryVerdict.text }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-show="rightTab === 'alerts'" class="rp-content">
      <div class="alert-summary-card">
        <div class="alert-summary-title">警報中心</div>
        <div class="alert-summary-subtitle">狀態、觸發紀錄與通知均來自本地資料庫</div>
      </div>
      <div v-if="alerts.length" class="alert-list">
        <div
          v-for="(alert, index) in alerts"
          :key="alert.id || `${alert.ticker}-${index}`"
          class="alert-card"
          :class="{ triggered: alert.triggered }"
        >
          <div class="alert-head">
            <div>
              <div class="alert-tk">{{ formatAlertTarget(alert) }}</div>
              <div class="alert-cond">{{ formatAlertSummary(alert) }}</div>
            </div>
            <div class="alert-badge" :class="alert.triggered ? 'triggered' : (alert.active ? 'active' : 'paused')">
              {{ formatAlertStatus(alert) }}
            </div>
          </div>

          <div class="alert-meta-grid">
            <div class="alert-meta-item">
              <span>類型</span>
              <span>{{ formatAlertType(alert) }}</span>
            </div>
            <div class="alert-meta-item">
              <span>最近評估</span>
              <span>{{ formatDateTime(alert.last_evaluated_at) }}</span>
            </div>
            <div class="alert-meta-item">
              <span>最近觸發</span>
              <span>{{ formatDateTime(alert.triggered_at) }}</span>
            </div>
            <div class="alert-meta-item">
              <span>儲存位置</span>
              <span>MySQL / alerts</span>
            </div>
          </div>

          <div v-if="getAlertContextSource(alert) || getAlertContextGroupName(alert) || getAlertContextTags(alert).length" class="alert-context-card">
            <div class="alert-context-head">
              <span>{{ getAlertContextSource(alert) || "研究上下文" }}</span>
              <span v-if="getAlertSnapshotLabel(alert)">{{ getAlertSnapshotLabel(alert) }}</span>
            </div>
            <div v-if="getAlertContextGroupName(alert) || getAlertContextTags(alert).length" class="alert-context-tags">
              <span
                v-if="getAlertContextGroupName(alert)"
                :key="`${alert.id}-context-group`"
                class="alert-context-tag"
              >
                {{ `群組：${getAlertContextGroupName(alert)}` }}
              </span>
              <span
                v-for="tag in getAlertContextTags(alert)"
                :key="`${alert.id}-${tag}`"
                class="alert-context-tag"
              >
                {{ tag }}
              </span>
            </div>
          </div>

          <div class="alert-actions">
            <button
              v-if="getAlertContextGroupName(alert)"
              class="alert-action-btn log"
              @click="$emit('open-watch-group', { groupName: getAlertContextGroupName(alert), ticker: alert.ticker || null })"
            >
              回到群組
            </button>
            <button class="alert-action-btn pause" @click="$emit('toggle-alert-active', alert.id)">
              {{ alert.active ? "暫停" : "恢復" }}
            </button>
            <button class="alert-action-btn log" @click="$emit('toggle-alert-log', alert.id)">
              {{ isAlertLogOpen(alert) ? "收合紀錄" : "觸發紀錄" }}
            </button>
            <button class="alert-action-btn delete" @click="$emit('delete-alert', alert.id)">刪除</button>
          </div>

          <div v-if="isAlertLogOpen(alert)" class="alert-log-card">
            <div class="alert-log-title">alert_trigger_logs</div>
            <div v-if="isAlertLogLoading(alert)" class="alert-log-empty">載入中...</div>
            <div v-else-if="getAlertLogs(alert).length" class="alert-log-list">
              <div
                v-for="log in getAlertLogs(alert)"
                :key="log.id"
                class="alert-log-row"
              >
                <div class="alert-log-row-top">
                  <span>{{ formatDateTime(log.created_at) }}</span>
                  <span>{{ formatLogSource(log) }}</span>
                </div>
                <div class="alert-log-row-bottom">
                  <span>觸發值 {{ formatAlertMetricValue(alert, log.trigger_value) }}</span>
                  <span>門檻 {{ formatAlertMetricValue(alert, log.threshold_value) }}</span>
                </div>
                <div v-if="formatLogMacroContext(log)" class="alert-log-row-bottom">
                  <span>{{ formatLogMacroContext(log) }}</span>
                </div>
                <div v-if="formatLogContextSummary(log)" class="alert-log-row-bottom">
                  <span>{{ formatLogContextSummary(log) }}</span>
                </div>
              </div>
            </div>
            <div v-else class="alert-log-empty">尚無觸發紀錄</div>
          </div>
        </div>
      </div>
      <div v-else style="color:var(--text3);font-size:11px;text-align:center;padding:16px">尚無警報</div>
      <button class="add-btn" @click="$emit('open-alert-modal')">＋ 新增警報</button>
    </div>

    <div v-show="rightTab === 'backtest'" class="rp-content">
      <BacktestPanel
        :backtestForm="backtestForm"
        :backtestResult="backtestResult"
        :backtestLoading="backtestLoading"
        :backtestHistory="backtestHistory"
        :formatPct="formatPct"
        :formatPositionSizing="formatPositionSizing"
        :backtestEquityPath="backtestEquityPath"
        :backtestTradeRows="backtestTradeRows"
        :backtestHistoryRows="backtestHistoryRows"
        :backtestCompareRows="backtestCompareRows"
        :isBacktestRunCompared="isBacktestRunCompared"
        @update-backtest-field="$emit('update-backtest-field', $event)"
        @run-backtest="$emit('run-backtest')"
        @load-backtest="$emit('load-backtest', $event)"
        @toggle-backtest-compare="$emit('toggle-backtest-compare', $event)"
        @clear-backtest-compare="$emit('clear-backtest-compare')"
      />
    </div>

    <div v-show="rightTab === 'journal'" class="rp-content">
      <JournalPanel
        :journalForm="journalForm"
        :journalEntries="journalEntries"
        :journalStats="journalStats"
        :journalLoading="journalLoading"
        :journalFilterPresets="journalFilterPresets"
        :journalFilterScope="journalFilterScope"
        :journalFilters="journalFilters"
        v-model:showAllJournalEntries="showAllJournalEntries"
        v-model:editingJournalPresetId="editingJournalPresetId"
        v-model:journalPresetName="journalPresetName"
        v-model:journalPresetDescription="journalPresetDescription"
        :formatDateTime="formatDateTime"
        @update-journal-field="$emit('update-journal-field', $event)"
        @update-journal-filter="$emit('update-journal-filter', $event)"
        @apply-journal-filter-preset="$emit('apply-journal-filter-preset', $event)"
        @save-journal-filter-preset="$emit('save-journal-filter-preset', $event)"
        @load-journal-filter-preset="$emit('load-journal-filter-preset', $event)"
        @delete-journal-filter-preset="$emit('delete-journal-filter-preset', $event)"
        @save-journal-entry="$emit('save-journal-entry')"
        @delete-journal-entry="$emit('delete-journal-entry', $event)"
        @select-journal-entry="$emit('select-journal-entry', $event)"
        @reset-journal-form="$emit('reset-journal-form')"
        @add-journal-attachment="$emit('add-journal-attachment')"
        @remove-journal-attachment="$emit('remove-journal-attachment', $event)"
        @create-watch-group="$emit('create-watch-group', $event)"
        @add-watchlist="$emit('add-watchlist', $event)"
        @open-alert-modal="$emit('open-alert-modal', $event)"
      />
    </div>

    <div v-show="rightTab === 'db'" class="rp-content">
      <div class="ind-group">
        <div class="ind-group-title">資料庫狀態</div>
        <div v-if="dbStats">
          <div class="db-stat-row"><span>總 K 線筆數</span><span style="color:var(--green)">{{ dbStats.total_rows?.toLocaleString() }}</span></div>
          <div class="db-stat-row"><span>股票數量</span><span>{{ dbStats.total_tickers }}</span></div>
          <div v-for="item in dbStats.top_tickers || []" :key="item.ticker" class="db-stat-row">
            <span>
              <div>{{ item.ticker }}</div>
              <div v-if="item.name && item.name !== item.ticker" class="db-stat-name">{{ item.name }}</div>
            </span>
            <span>{{ item.rows }} 筆</span>
          </div>
        </div>
        <div v-else-if="dbStatsLoading" style="color:var(--text2);font-size:11px">載入中...</div>
        <div v-else style="color:var(--red);font-size:11px">{{ dbStatsError || "尚未載入資料庫統計" }}</div>
      </div>
      <button class="sync-btn" :disabled="syncingAll" @click="$emit('sync-all')">{{ syncingAll ? "↻ 同步中..." : "↻ 同步股票與大盤最新資料" }}</button>
      <div style="margin-top:10px;font-size:10px;color:var(--text3);line-height:1.8">
        資料庫：<span style="color:var(--text2)">MySQL / quantvision</span><br>
        資料來源：<span style="color:var(--text2)">Yahoo Finance</span><br>
        更新頻率：<span style="color:var(--text2)">定時輪詢 + 每日自動更新</span><br>
        同步範圍：<span style="color:var(--text2)">自選股群組與全球大盤群組</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import BacktestPanel from "./BacktestPanel.vue";
import JournalPanel from "./JournalPanel.vue";


const props = defineProps({
  rightTab: { type: String, required: true },
  indicatorSnapshot: { type: Object, required: true },
  activeInd: { type: Object, required: true },
  activePanels: { type: Object, required: true },
  indicatorSettings: { type: Object, required: true },
  alerts: { type: Array, required: true },
  alertTriggerLogs: { type: Object, default: () => ({}) },
  alertLogLoading: { type: Object, default: () => ({}) },
  expandedAlertLogId: { type: [Number, String], default: null },
  backtestForm: { type: Object, required: true },
  backtestResult: { type: Object, default: null },
  backtestHistory: { type: Array, default: () => [] },
  backtestCompareIds: { type: Array, default: () => [] },
  backtestCompareRuns: { type: Array, default: () => [] },
  backtestLoading: { type: Boolean, required: true },
  journalForm: { type: Object, required: true },
  journalEntries: { type: Array, default: () => [] },
  journalStats: { type: Object, default: null },
  journalLoading: { type: Boolean, required: true },
  journalFilterPresets: { type: Array, default: () => [] },
  journalFilterScope: { type: String, required: true },
  journalFilters: { type: Object, required: true },
  dbStats: { type: Object, default: null },
  dbStatsLoading: { type: Boolean, required: true },
  dbStatsError: { type: String, default: "" },
  syncingAll: { type: Boolean, required: true },
});

const emit = defineEmits([
  "set-right-tab",
  "toggle-indicator",
  "toggle-panel",
  "update-indicator-setting",
  "apply-indicator-preset",
  "open-alert-modal",
  "open-watch-group",
  "toggle-alert-active",
  "toggle-alert-log",
  "delete-alert",
  "update-backtest-field",
  "run-backtest",
  "load-backtest",
  "toggle-backtest-compare",
  "clear-backtest-compare",
  "update-journal-field",
  "update-journal-filter",
  "apply-journal-filter-preset",
  "save-journal-filter-preset",
  "load-journal-filter-preset",
  "delete-journal-filter-preset",
  "save-journal-entry",
  "delete-journal-entry",
  "select-journal-entry",
  "reset-journal-form",
  "add-journal-attachment",
  "remove-journal-attachment",
  "create-watch-group",
  "add-watchlist",
  "sync-all",
]);

function buildSparklinePath(points) {
  if (!Array.isArray(points) || points.length < 2) return "";
  const values = points.map((item) => Number(item?.equity ?? 0)).filter((value) => Number.isFinite(value));
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 240;
  const height = 90;
  const xStep = width / Math.max(values.length - 1, 1);
  return values.map((value, index) => {
    const x = Number((index * xStep).toFixed(2));
    const ratio = max === min ? 0.5 : (value - min) / (max - min);
    const y = Number((height - (ratio * (height - 12)) - 6).toFixed(2));
    return `${index === 0 ? "M" : "L"}${x} ${y}`;
  }).join(" ");
}

function formatPct(value) {
  if (value == null || value === "") return "—";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

function formatPositionSizing(value) {
  const labels = {
    full_equity: "100% 資金",
    half_equity: "50% 資金",
    quarter_equity: "25% 資金",
  };
  return labels[String(value || "full_equity")] || String(value || "100% 資金");
}

function isBacktestRunCompared(runId) {
  return (props.backtestCompareIds || []).some((id) => String(id) === String(runId));
}

const journalPresetName = ref("");
const journalPresetDescription = ref("");
const editingJournalPresetId = ref(null);
const showAllJournalEntries = ref(false);

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
    const labels = {
      high: "高異常",
      medium_or_high: "中度以上異常",
    };
    return labels[normalizedCondition] || rawCondition || "—";
  }
  if (normalizedType === "event") {
    const labels = {
      within_days: "事件前提醒",
    };
    return labels[normalizedCondition] || rawCondition || "—";
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
  if (normalizedType === "event") {
    return `${numericValue.toFixed(0)} 日內`;
  }
  if (normalizedType === "pct") {
    return `${numericValue.toFixed(2)}%`;
  }
  if (normalizedType === "volume") {
    return `${numericValue.toFixed(2)}x`;
  }
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
  const cacheKey = String(alert?.id ?? "");
  return props.alertTriggerLogs?.[cacheKey] || [];
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

const overlayRows = computed(() => [
  { key: "cycleMa", label: "周 / 月 / 季 / 年線", value: "MA 5 / 20 / 60 / 240", color: "#7be7ff", hint: "清指標模式下仍會保留的核心均線組" },
  { key: "ma20", label: `MA ${props.indicatorSettings.ma20Period}`, value: props.indicatorSnapshot.ma20, color: "#3b8bff" },
  { key: "ma50", label: `MA ${props.indicatorSettings.ma50Period}`, value: props.indicatorSnapshot.ma50, color: "#f5a623" },
  { key: "ma200", label: `MA ${props.indicatorSettings.ma200Period}`, value: props.indicatorSnapshot.ma200, color: "#9b6dff" },
  { key: "ema12", label: `EMA ${props.indicatorSettings.emaPeriod}`, value: props.indicatorSnapshot.ema12, color: "#00d4ff" },
  { key: "bb", label: `布林通道 (${props.indicatorSettings.bbPeriod}, ${props.indicatorSettings.bbMultiplier})`, value: props.indicatorSnapshot.bb, color: "#ffd166" },
  { key: "psar", label: `Parabolic SAR (${props.indicatorSettings.psarStep}, ${props.indicatorSettings.psarMax})`, value: props.indicatorSnapshot.psar, color: "#ff6b6b", hint: "拋物線停損反轉" },
  { key: "keltner", label: `Keltner (${props.indicatorSettings.kcPeriod}, ${props.indicatorSettings.kcMultiplier})`, value: props.indicatorSnapshot.keltner, color: "#7be7ff", hint: "EMA + ATR 通道" },
  { key: "donchian", label: `Donchian (${props.indicatorSettings.donchianPeriod})`, value: props.indicatorSnapshot.donchian, color: "#9b6dff", hint: "區間突破通道" },
  { key: "vwap", label: "VWAP", value: "ON", color: "#ff8c42", hint: "盤中量價基準線" },
  { key: "ichimoku", label: `Ichimoku (${props.indicatorSettings.ichimokuConversion}, ${props.indicatorSettings.ichimokuBase}, ${props.indicatorSettings.ichimokuSpanB})`, value: props.indicatorSnapshot.ichimoku, color: "#8dc1ff", hint: `位移 ${props.indicatorSettings.ichimokuDisplacement}` },
  { key: "supertrend", label: `SuperTrend (${props.indicatorSettings.supertrendPeriod}, ${props.indicatorSettings.supertrendMultiplier})`, value: props.indicatorSnapshot.supertrend, color: "#7be7ff", hint: "多空切換支撐線" },
]);

const panelRows = computed(() => [
  { key: "rsi", label: `RSI(${props.indicatorSettings.rsiPeriod})`, hint: "70 超買 / 30 超賣", value: props.indicatorSnapshot.rsi, valueClass: props.indicatorSnapshot.rsiClass },
  { key: "aroon", label: `Aroon(${props.indicatorSettings.aroonPeriod})`, hint: "Up / Down 趨勢強度", value: props.indicatorSnapshot.aroon, valueClass: "" },
  { key: "trix", label: `TRIX(${props.indicatorSettings.trixPeriod},${props.indicatorSettings.trixSignal})`, hint: props.indicatorSnapshot.trixSignal, value: props.indicatorSnapshot.trix, valueClass: "" },
  { key: "williamsr", label: `Williams %R(${props.indicatorSettings.williamsrPeriod})`, hint: "-20 超買 / -80 超賣", value: props.indicatorSnapshot.williamsr, valueClass: "" },
  { key: "mfi", label: `MFI(${props.indicatorSettings.mfiPeriod})`, hint: "量價資金流", value: props.indicatorSnapshot.mfi, valueClass: "" },
  { key: "roc", label: `ROC(${props.indicatorSettings.rocPeriod})`, hint: "價格動能百分比", value: props.indicatorSnapshot.roc, valueClass: "" },
  { key: "bbPercent", label: `Bollinger %B(${props.indicatorSettings.bbPeriod})`, hint: "0 下軌 / 100 上軌", value: props.indicatorSnapshot.bbPercent, valueClass: "" },
  { key: "bbWidth", label: `Bollinger Width(${props.indicatorSettings.bbPeriod})`, hint: "通道寬度 / 壓縮偵測", value: props.indicatorSnapshot.bbWidth, valueClass: "" },
  { key: "macd", label: `MACD(${props.indicatorSettings.macdFast},${props.indicatorSettings.macdSlow},${props.indicatorSettings.macdSignal})`, hint: props.indicatorSnapshot.macdSignal, value: props.indicatorSnapshot.macd, valueClass: "" },
  { key: "stoch", label: `KD Stoch(${props.indicatorSettings.stochK},${props.indicatorSettings.stochD})`, hint: "擺盪強弱", value: props.indicatorSnapshot.stoch, valueClass: "" },
  { key: "atr", label: `ATR(${props.indicatorSettings.atrPeriod})`, hint: "波動幅度 / 停損參考", value: props.indicatorSnapshot.atr, valueClass: "" },
  { key: "cci", label: `CCI(${props.indicatorSettings.cciPeriod})`, hint: "±100 強弱區間", value: props.indicatorSnapshot.cci, valueClass: "" },
  { key: "obv", label: "OBV", hint: "量能趨勢累積", value: props.indicatorSnapshot.obv, valueClass: "" },
  { key: "adx", label: `ADX(${props.indicatorSettings.adxPeriod})`, hint: props.indicatorSnapshot.adxSignal, value: props.indicatorSnapshot.adx, valueClass: "" },
  { key: "cmf", label: `CMF(${props.indicatorSettings.cmfPeriod})`, hint: "Chaikin 資金流", value: props.indicatorSnapshot.cmf, valueClass: "" },
]);

const settingSections = computed(() => [
  {
    title: "主圖參數",
    items: [
      { key: "ma20Period", label: "MA 快線", step: 1, min: 2, max: 400, range: "2-400" },
      { key: "ma50Period", label: "MA 中線", step: 1, min: 2, max: 600, range: "2-600" },
      { key: "ma200Period", label: "MA 長線", step: 1, min: 2, max: 1200, range: "2-1200" },
      { key: "emaPeriod", label: "EMA", step: 1, min: 2, max: 400, range: "2-400" },
      { key: "bbPeriod", label: "BB 週期", step: 1, min: 5, max: 300, range: "5-300" },
      { key: "bbMultiplier", label: "BB 倍數", step: 0.1, min: 0.5, max: 6, range: "0.5-6" },
      { key: "psarStep", label: "PSAR Step", step: 0.005, min: 0.005, max: 0.2, range: "0.005-0.2" },
      { key: "psarMax", label: "PSAR Max", step: 0.01, min: 0.02, max: 1, range: "0.02-1" },
      { key: "kcPeriod", label: "Keltner 週期", step: 1, min: 2, max: 300, range: "2-300" },
      { key: "kcMultiplier", label: "Keltner 倍數", step: 0.1, min: 0.5, max: 6, range: "0.5-6" },
      { key: "donchianPeriod", label: "Donchian 週期", step: 1, min: 2, max: 300, range: "2-300" },
      { key: "volumeMaPeriod", label: "量均線", step: 1, min: 2, max: 200, range: "2-200" },
      { key: "ichimokuConversion", label: "轉換線", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "ichimokuBase", label: "基準線", step: 1, min: 3, max: 120, range: "3-120" },
      { key: "ichimokuSpanB", label: "先行 B", step: 1, min: 4, max: 240, range: "4-240" },
      { key: "ichimokuDisplacement", label: "雲圖位移", step: 1, min: 1, max: 120, range: "1-120" },
      { key: "supertrendPeriod", label: "SuperTrend 週期", step: 1, min: 2, max: 120, range: "2-120" },
      { key: "supertrendMultiplier", label: "SuperTrend 倍數", step: 0.1, min: 0.5, max: 10, range: "0.5-10" },
    ],
  },
  {
    title: "副圖參數",
    items: [
      { key: "rsiPeriod", label: "RSI", step: 1, min: 2, max: 100, range: "2-100" },
      { key: "aroonPeriod", label: "Aroon", step: 1, min: 2, max: 150, range: "2-150" },
      { key: "trixPeriod", label: "TRIX", step: 1, min: 2, max: 120, range: "2-120" },
      { key: "trixSignal", label: "TRIX 訊號", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "williamsrPeriod", label: "Williams %R", step: 1, min: 2, max: 100, range: "2-100" },
      { key: "mfiPeriod", label: "MFI", step: 1, min: 2, max: 100, range: "2-100" },
      { key: "rocPeriod", label: "ROC", step: 1, min: 1, max: 120, range: "1-120" },
      { key: "macdFast", label: "MACD 快線", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "macdSlow", label: "MACD 慢線", step: 1, min: 3, max: 120, range: "3-120" },
      { key: "macdSignal", label: "MACD 訊號", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "stochK", label: "KD K", step: 1, min: 3, max: 100, range: "3-100" },
      { key: "stochD", label: "KD D", step: 1, min: 2, max: 20, range: "2-20" },
      { key: "atrPeriod", label: "ATR", step: 1, min: 2, max: 120, range: "2-120" },
      { key: "cciPeriod", label: "CCI", step: 1, min: 3, max: 120, range: "3-120" },
      { key: "adxPeriod", label: "ADX", step: 1, min: 2, max: 120, range: "2-120" },
      { key: "cmfPeriod", label: "CMF", step: 1, min: 2, max: 120, range: "2-120" },
    ],
  },
]);

const backtestEquityPath = computed(() => buildSparklinePath(props.backtestResult?.equity_curve || []));
const backtestTradeRows = computed(() => (props.backtestResult?.trades || []).slice(-5).reverse());
const backtestHistoryRows = computed(() => (props.backtestHistory || []).slice(0, 8));
const backtestCompareRows = computed(() => (props.backtestCompareRuns || []).slice(0, 3));
</script>

<style scoped>
.alert-summary-card {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(123, 231, 255, 0.18);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 26, 36, 0.96), rgba(5, 16, 24, 0.96));
}

.alert-summary-title {
  font-family: "Syne", sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--text1);
}

.alert-summary-subtitle {
  margin-top: 4px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--text3);
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.alert-card {
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(8, 14, 22, 0.92);
}

.alert-card.triggered {
  border-color: rgba(245, 166, 35, 0.34);
  box-shadow: 0 0 0 1px rgba(245, 166, 35, 0.12) inset;
}

.alert-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.alert-tk {
  font-family: "Syne", sans-serif;
  font-size: 14px;
  font-weight: 700;
}

.alert-cond {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text2);
}

.alert-badge {
  flex-shrink: 0;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
}

.alert-badge.active {
  background: rgba(0, 217, 163, 0.12);
  color: var(--green);
}

.alert-badge.paused {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
}

.alert-badge.triggered {
  background: rgba(245, 166, 35, 0.14);
  color: var(--yellow);
}

.alert-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.alert-meta-item {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  font-size: 10px;
  line-height: 1.5;
  color: var(--text3);
}

.alert-meta-item span:last-child {
  display: block;
  margin-top: 2px;
  color: var(--text1);
}

.alert-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.alert-action-btn {
  flex: 1;
  min-width: 0;
  padding: 7px 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text1);
  font-size: 11px;
  cursor: pointer;
}

.alert-action-btn.pause {
  border-color: rgba(123, 231, 255, 0.24);
}

.alert-action-btn.log {
  border-color: rgba(255, 209, 102, 0.24);
}

.alert-action-btn.delete {
  border-color: rgba(255, 77, 106, 0.24);
  color: #ff7d91;
}

.alert-log-card {
  margin-top: 10px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(3, 10, 16, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.alert-log-title {
  font-size: 10px;
  letter-spacing: 0.04em;
  color: var(--text3);
}

.alert-log-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.alert-log-row {
  padding: 8px 9px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}

.alert-log-row-top,
.alert-log-row-bottom {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 10px;
  line-height: 1.5;
}

.alert-log-row-top {
  color: var(--text2);
}

.alert-log-row-bottom {
  margin-top: 4px;
  color: var(--text3);
}

.alert-log-empty {
  margin-top: 8px;
  font-size: 10px;
  color: var(--text3);
}

.alert-context-card {
  margin-top: 10px;
  padding: 9px 10px;
  border-radius: 10px;
  background: rgba(123, 231, 255, 0.05);
  border: 1px solid rgba(123, 231, 255, 0.12);
}

.alert-context-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 10px;
  line-height: 1.5;
  color: var(--text2);
}

.alert-context-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.alert-context-tag {
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.12);
  color: #bfefff;
  font-size: 10px;
  line-height: 1.4;
}

</style>
