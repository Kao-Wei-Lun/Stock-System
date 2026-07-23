<template>
  <section class="health-panel">
    <div class="health-head">
      <div>
        <div class="health-title-row">
          <h2>系統與資料品質</h2>
          <span v-if="snapshot" class="status-pill" :class="snapshot.status">
            {{ statusLabel(snapshot.status) }}
          </span>
        </div>
        <p>集中檢查資料庫、備份、排程、即時連線、觀察池行情與期貨 1 分 K 持久化狀態。</p>
      </div>
      <button type="button" :disabled="loading" data-testid="refresh-health" @click="loadSnapshot">
        {{ loading ? "檢查中" : "重新檢查" }}
      </button>
    </div>

    <div v-if="error" class="health-message error" role="alert">{{ error }}</div>
    <div v-if="loading && !snapshot" class="health-empty">正在讀取系統狀態</div>

    <template v-else-if="snapshot">
      <div class="summary-grid" aria-label="健康狀態摘要">
        <div class="summary-card">
          <span>正常</span>
          <strong>{{ snapshot.summary?.healthy_count || 0 }}</strong>
        </div>
        <div class="summary-card idle">
          <span>待命</span>
          <strong>{{ snapshot.summary?.idle_count || 0 }}</strong>
        </div>
        <div class="summary-card warning">
          <span>警告</span>
          <strong>{{ snapshot.summary?.warning_count || 0 }}</strong>
        </div>
        <div class="summary-card error">
          <span>錯誤</span>
          <strong>{{ snapshot.summary?.error_count || 0 }}</strong>
        </div>
      </div>

      <section class="trend-section" aria-label="最近 24 小時營運趨勢">
        <div class="trend-head">
          <div>
            <h3>最近 24 小時</h3>
            <p>僅保存效能數值與狀態，不包含行情、帳號或個人資產資料。</p>
          </div>
          <span>{{ history?.point_count || 0 }} 個取樣點</span>
        </div>
        <div v-if="historyError" class="health-message warning" data-testid="history-error">
          {{ historyError }}
        </div>
        <div v-if="trendCards.length" class="trend-grid">
          <article v-for="card in trendCards" :key="card.key" class="trend-card">
            <span>{{ card.label }}</span>
            <strong>{{ formatTrendValue(card.latest, card.unit) }}</strong>
            <svg
              viewBox="0 0 120 34"
              preserveAspectRatio="none"
              role="img"
              :aria-label="`${card.label} 24 小時趨勢`"
            >
              <polyline :points="sparklinePoints(card.values)" />
            </svg>
            <small>最大 {{ formatTrendValue(card.maximum, card.unit) }}</small>
          </article>
        </div>
        <div v-else-if="!historyError" class="trend-empty">收集第一筆資料後會顯示趨勢</div>
      </section>

      <div v-if="snapshot.issues?.length" class="issue-list">
        <div v-for="issue in snapshot.issues" :key="issue.component" class="health-message" :class="issue.status">
          <strong>{{ componentName(issue.component) }}</strong>
          <span>{{ issue.message }}</span>
        </div>
      </div>

      <div class="component-grid">
        <article v-for="([key, component]) in componentEntries" :key="key" class="component-card">
          <div class="component-head">
            <h3>{{ componentName(key) }}</h3>
            <span class="status-dot" :class="component.status"></span>
          </div>
          <p>{{ component.label }}</p>
          <dl>
            <template v-for="metric in componentMetrics(key, component)" :key="metric.label">
              <dt>{{ metric.label }}</dt>
              <dd>{{ metric.value }}</dd>
            </template>
          </dl>

          <div v-if="key === 'watchlist' && component.stale_items?.length" class="detail-list">
            <span v-for="item in component.stale_items.slice(0, 8)" :key="item.ticker">
              {{ item.ticker }} · {{ freshnessLabel(item) }}
            </span>
          </div>
          <div v-if="key === 'futures_recorder' && component.persisted_records?.length" class="detail-list">
            <span v-for="item in component.persisted_records" :key="item.symbol">
              {{ item.symbol }} · {{ freshnessLabel(item) }}
            </span>
          </div>
        </article>
      </div>

      <div class="generated-time">最後檢查：{{ formatTime(snapshot.generated_at) }}</div>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { dashboardApi } from "../../api/dashboardApi";
import { getOperationalMetricsHistory } from "../../api/operationalMetricsApi";
import { createVisibilityPoller } from "../../utils/visibilityPoller";

const snapshot = ref(null);
const history = ref(null);
const loading = ref(false);
const error = ref("");
const historyError = ref("");

const componentEntries = computed(() => Object.entries(snapshot.value?.components || {}));
const trendCards = computed(() => {
  const points = history.value?.points || [];
  const definitions = [
    { key: "api", label: "API P95", unit: "ms", read: (item) => item.api?.p95_ms },
    { key: "db", label: "DB 等待 P95", unit: "ms", read: (item) => item.database?.wait_p95_ms },
    { key: "broadcast", label: "即時廣播 P95", unit: "ms", read: (item) => item.realtime?.broadcast_p95_ms },
    { key: "stale", label: "過期商品", unit: "count", read: (item) => item.freshness?.stale_ticker_count },
  ];
  return definitions.flatMap((definition) => {
    const values = points.map(definition.read).filter((value) => Number.isFinite(Number(value))).map(Number);
    if (!values.length) return [];
    return [{
      ...definition,
      values,
      latest: values.at(-1),
      maximum: Math.max(...values),
    }];
  });
});

const COMPONENT_NAMES = {
  database: "資料庫",
  migrations: "資料庫版本",
  backups: "資料庫備份",
  scheduler: "背景排程",
  websocket: "瀏覽器即時連線",
  fubon: "富邦行情 API",
  watchlist: "觀察池行情",
  futures_recorder: "期貨 1 分 K",
};

function componentName(key) {
  return COMPONENT_NAMES[key] || key;
}

function statusLabel(status) {
  return { healthy: "正常", idle: "待命", warning: "需注意", error: "異常" }[status] || "未知";
}

function yesNo(value) {
  return value ? "是" : "否";
}

function componentMetrics(key, item) {
  const metrics = {
    database: [
      { label: "可連線", value: yesNo(item.connected) },
      { label: "延遲", value: item.latency_ms == null ? "—" : `${item.latency_ms} ms` },
    ],
    migrations: [
      { label: "目前版本", value: item.current_version || "—" },
      { label: "待套用", value: `${item.pending_count ?? "—"} 筆` },
    ],
    scheduler: [
      { label: "執行中任務", value: `${item.active_count || 0} / ${item.task_count || 0}` },
      { label: "異常停止", value: `${item.failed_count || 0}` },
      { label: "排程啟動", value: yesNo(item.running) },
    ],
    backups: [
      { label: "範圍", value: item.scope === "critical" ? "重要資料" : (item.scope === "full" ? "完整" : "—") },
      { label: "備份時間", value: formatTime(item.created_at) },
      { label: "距今", value: item.age_hours == null ? "—" : `${item.age_hours} 小時` },
      { label: "大小", value: formatBytes(item.size_bytes) },
    ],
    websocket: [
      { label: "用戶端", value: `${item.client_count || 0}` },
      { label: "訂閱數", value: `${item.subscription_count || 0}` },
    ],
    fubon: [
      { label: "已連線帳號", value: `${item.connected_account_count || 0} / ${item.account_count || 0}` },
      { label: "暖機狀態", value: warmupLabel(item.warmup?.state) },
      { label: "重連嘗試", value: `${item.reconnect_attempts || 0}` },
    ],
    watchlist: [
      { label: "有效行情", value: `${item.current_count || 0} / ${item.ticker_count || 0}` },
      { label: "過期／缺少", value: `${item.stale_count || 0}` },
    ],
    futures_recorder: [
      { label: "記錄器啟用", value: yesNo(item.enabled) },
      { label: "佇列", value: `${item.queue_size || 0} / ${item.queue_capacity || 0}` },
      { label: "遺失訊息", value: `${item.dropped_messages || 0}` },
    ],
  };
  return metrics[key] || [];
}

function warmupLabel(value) {
  return {
    idle: "待命",
    scheduled: "排程中",
    running: "連線中",
    ready: "完成",
    failed: "失敗",
    cancelled: "已取消",
    stopped: "已停止",
    unconfigured: "未設定",
  }[value] || "—";
}

function freshnessLabel(item) {
  if (!item.data_timestamp) return "無資料";
  if (item.is_stale) return `已過期 ${formatTime(item.data_timestamp)}`;
  return `最新 ${formatTime(item.data_timestamp)}`;
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let size = bytes / 1024;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[index]}`;
}

function formatTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(parsed);
}

function formatTrendValue(value, unit) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  if (unit === "count") return `${Math.round(numeric)} 檔`;
  return `${numeric >= 100 ? numeric.toFixed(0) : numeric.toFixed(1)} ms`;
}

function sparklinePoints(values) {
  if (!values?.length) return "";
  const width = 120;
  const height = 30;
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum || 1;
  return values.map((value, index) => {
    const x = values.length === 1 ? width : (index / (values.length - 1)) * width;
    const y = height - ((value - minimum) / range) * (height - 4) + 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

async function loadSnapshot() {
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  historyError.value = "";
  try {
    const [snapshotResult, historyResult] = await Promise.allSettled([
      dashboardApi.getSystemDataQuality(),
      getOperationalMetricsHistory({ hours: 24, resolution: "auto" }),
    ]);
    if (snapshotResult.status === "fulfilled") {
      snapshot.value = snapshotResult.value;
    } else {
      error.value = snapshotResult.reason?.message || "無法讀取系統狀態";
    }
    if (historyResult.status === "fulfilled") {
      history.value = historyResult.value;
    } else {
      historyError.value = historyResult.reason?.message || "暫時無法讀取 24 小時趨勢";
    }
  } finally {
    loading.value = false;
  }
}

const refreshPoller = createVisibilityPoller(loadSnapshot, {
  intervalMs: 30_000,
  runImmediately: true,
});

onMounted(() => {
  refreshPoller.start();
});

onBeforeUnmount(() => {
  refreshPoller.stop();
});
</script>

<style scoped>
.health-panel {
  display: grid;
  gap: 14px;
}

.health-head,
.health-title-row,
.component-head,
.health-message {
  display: flex;
  align-items: center;
}

.health-head {
  justify-content: space-between;
  gap: 16px;
}

.health-title-row {
  gap: 10px;
}

.health-head h2 {
  font-family: "Syne", sans-serif;
  font-size: 19px;
}

.health-head p,
.component-card p {
  margin-top: 6px;
  color: var(--text2);
  line-height: 1.6;
}

.health-head button {
  min-width: 94px;
  min-height: 36px;
  border: 1px solid rgba(123, 231, 255, 0.35);
  border-radius: 8px;
  background: rgba(123, 231, 255, 0.1);
  color: #d7fbff;
  cursor: pointer;
}

.health-head button:disabled {
  opacity: 0.55;
  cursor: wait;
}

.status-pill {
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
}

.status-pill.healthy,
.summary-card strong {
  color: var(--green);
}

.status-pill.idle,
.summary-card.idle strong {
  color: var(--text2);
}

.status-pill.warning,
.summary-card.warning strong,
.health-message.warning strong {
  color: var(--amber);
}

.status-pill.error,
.summary-card.error strong,
.health-message.error strong {
  color: var(--red);
}

.summary-grid,
.component-grid,
.trend-grid {
  display: grid;
  gap: 10px;
}

.summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.component-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.trend-section {
  display: grid;
  gap: 10px;
  border: 1px solid var(--border2);
  border-radius: 8px;
  padding: 14px;
  background: rgba(13, 20, 32, 0.92);
}

.trend-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.trend-head h3 {
  font-size: 14px;
}

.trend-head p,
.trend-head > span,
.trend-empty {
  color: var(--text3);
  font-size: 11px;
}

.trend-head p {
  margin-top: 4px;
}

.trend-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.trend-card {
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: 7px;
  padding: 10px;
  background: rgba(8, 14, 24, 0.7);
}

.trend-card > span,
.trend-card small {
  color: var(--text3);
  font-size: 10px;
}

.trend-card strong {
  display: block;
  margin-top: 5px;
  color: var(--cyan);
  font: 600 15px "JetBrains Mono", monospace;
}

.trend-card svg {
  display: block;
  width: 100%;
  height: 34px;
  margin: 7px 0 4px;
  overflow: visible;
}

.trend-card polyline {
  fill: none;
  stroke: var(--cyan);
  stroke-width: 1.8;
  vector-effect: non-scaling-stroke;
}

.trend-empty {
  padding: 12px;
  text-align: center;
}

.summary-card,
.component-card,
.health-message,
.health-empty {
  border: 1px solid var(--border2);
  border-radius: 8px;
  background: rgba(13, 20, 32, 0.92);
}

.summary-card {
  padding: 12px;
}

.summary-card span {
  color: var(--text3);
  font-size: 11px;
}

.summary-card strong {
  display: block;
  margin-top: 5px;
  font: 600 22px "JetBrains Mono", monospace;
}

.component-card {
  min-width: 0;
  padding: 14px;
}

.component-head {
  justify-content: space-between;
  gap: 12px;
}

.component-head h3 {
  font-size: 14px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text3);
  box-shadow: 0 0 8px currentColor;
}

.status-dot.healthy { background: var(--green); color: var(--green); }
.status-dot.warning { background: var(--amber); color: var(--amber); }
.status-dot.error { background: var(--red); color: var(--red); }

dl {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 7px 12px;
  margin-top: 12px;
  font-size: 12px;
}

dt { color: var(--text3); }
dd { color: var(--text1); font-family: "JetBrains Mono", monospace; }

.issue-list,
.detail-list {
  display: grid;
  gap: 6px;
}

.health-message {
  gap: 10px;
  padding: 10px 12px;
  color: var(--text2);
  font-size: 12px;
}

.health-message.error { border-color: rgba(255, 91, 120, 0.35); }
.health-message.warning { border-color: rgba(255, 184, 77, 0.3); }

.detail-list {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  color: var(--text3);
  font: 11px "JetBrains Mono", monospace;
}

.health-empty {
  padding: 24px;
  color: var(--text2);
  text-align: center;
}

.generated-time {
  color: var(--text3);
  font: 10px "JetBrains Mono", monospace;
  text-align: right;
}

@media (max-width: 720px) {
  .health-head { align-items: flex-start; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .component-grid { grid-template-columns: 1fr; }
  .trend-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
