<template>
  <div>
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
    <div v-else class="alert-empty">尚無警報</div>
    <button class="add-btn" @click="$emit('open-alert-modal')">＋ 新增警報</button>
  </div>
</template>

<script setup>
defineProps({
  alerts: { type: Array, default: () => [] },
  formatDateTime: { type: Function, required: true },
  formatAlertTarget: { type: Function, required: true },
  formatAlertSummary: { type: Function, required: true },
  formatAlertStatus: { type: Function, required: true },
  formatAlertType: { type: Function, required: true },
  getAlertContextSource: { type: Function, required: true },
  getAlertContextGroupName: { type: Function, required: true },
  getAlertContextTags: { type: Function, required: true },
  getAlertSnapshotLabel: { type: Function, required: true },
  isAlertLogOpen: { type: Function, required: true },
  isAlertLogLoading: { type: Function, required: true },
  getAlertLogs: { type: Function, required: true },
  formatLogSource: { type: Function, required: true },
  formatAlertMetricValue: { type: Function, required: true },
  formatLogMacroContext: { type: Function, required: true },
  formatLogContextSummary: { type: Function, required: true },
});

defineEmits([
  "open-watch-group",
  "toggle-alert-active",
  "toggle-alert-log",
  "delete-alert",
  "open-alert-modal",
]);
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

.alert-empty {
  color: var(--text3);
  font-size: 11px;
  text-align: center;
  padding: 16px;
}
</style>
