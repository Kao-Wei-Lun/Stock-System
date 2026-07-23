<template>
  <div class="statusbar">
    <div class="status-block">
      <div class="sb-dot" :class="connected ? 'live' : 'err'"></div>
      <span>{{ connected ? "連線中" : "重連中..." }}</span>
    </div>
    <div class="status-block">後端：<span class="status-accent">{{ backendUrl }}</span></div>
    <div class="status-block">延遲：<span class="status-accent">{{ latency }}</span></div>
    <div class="status-block">來源：<span>{{ quoteSource }}</span></div>
    <div class="status-block">模式：<span>{{ normalizedQuoteMode }}</span></div>
    <div class="status-block">
      K線：
      <span class="status-badge" :class="`origin-${klineDataOrigin}`">{{ klineOriginLabel }}</span>
    </div>
    <div class="status-block">
      狀態：
      <span class="status-badge" :class="freshnessClass">{{ freshnessDisplayLabel }}</span>
    </div>
    <div class="status-block status-push">
      更新：
      <span class="status-badge" :class="freshnessClass">{{ lastUpdate }}</span>
    </div>
    <div class="status-block">{{ clockTime }}</div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  connected: { type: Boolean, required: true },
  backendUrl: { type: String, required: true },
  latency: { type: String, required: true },
  quoteSource: { type: String, required: true },
  quoteMode: { type: String, required: true },
  quoteTimestamp: { type: String, default: null },
  quoteSyncedAt: { type: String, default: null },
  quoteDelayed: { type: Boolean, default: true },
  klineDataOrigin: { type: String, default: "loading" },
  klineCacheSavedAt: { type: Number, default: null },
  lastUpdate: { type: String, required: true },
  clockTime: { type: String, required: true },
});

const normalizedQuoteMode = computed(() => {
  if (props.quoteDelayed === false) return "即時";
  if (props.quoteMode === "延遲快照") return "盤後快照";
  if (props.quoteMode === "最新快照") return "即時";
  return props.quoteMode || "快照";
});

const klineOriginLabel = computed(() => {
  if (props.klineDataOrigin === "cache") return "快取資料";
  if (props.klineDataOrigin === "database") return "資料庫資料";
  if (props.klineDataOrigin === "realtime") return "即時更新";
  return "載入中";
});

const freshnessState = computed(() => {
  const rawValue = props.quoteTimestamp || props.quoteSyncedAt;
  if (!rawValue) return "missing";
  const parsed = new Date(rawValue);
  if (Number.isNaN(parsed.getTime())) return "missing";
  const ageMs = Date.now() - parsed.getTime();
  if (ageMs > 24 * 60 * 60 * 1000) return "stale";
  return props.quoteDelayed ? "delayed" : "live";
});

const freshnessLabel = computed(() => {
  if (freshnessState.value === "missing") return "無時間戳";
  if (freshnessState.value === "stale") return "資料較舊";
  return props.quoteDelayed ? normalizedQuoteMode.value : "即時資料";
});

function formatAgeLabel(ageMs) {
  if (!Number.isFinite(ageMs)) return "";
  if (ageMs < 0) return "剛剛";
  const totalSeconds = Math.floor(ageMs / 1000);
  if (totalSeconds < 60) return "剛剛";
  const totalMinutes = Math.floor(totalSeconds / 60);
  if (totalMinutes < 60) return `${totalMinutes}分鐘前`;
  const totalHours = Math.floor(totalMinutes / 60);
  if (totalHours < 24) return `${totalHours}小時前`;
  const totalDays = Math.floor(totalHours / 24);
  if (totalDays < 30) return `${totalDays}天前`;
  const totalMonths = Math.floor(totalDays / 30);
  if (totalMonths < 12) return `${totalMonths}個月前`;
  return `${Math.floor(totalDays / 365)}年前`;
}

const freshnessAgeLabel = computed(() => {
  const rawValue = props.quoteTimestamp || props.quoteSyncedAt;
  if (!rawValue) return "";
  const parsed = new Date(rawValue);
  if (Number.isNaN(parsed.getTime())) return "";
  return formatAgeLabel(Date.now() - parsed.getTime());
});

const freshnessDisplayLabel = computed(() => (
  freshnessAgeLabel.value ? `${freshnessLabel.value} / ${freshnessAgeLabel.value}` : freshnessLabel.value
));

const freshnessClass = computed(() => freshnessState.value);
</script>

<style scoped>
.statusbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.status-block {
  display: flex;
  align-items: center;
  gap: 5px;
}

.status-push {
  margin-left: auto;
}

.status-accent {
  color: var(--green);
}

.status-badge {
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
}

.status-badge.live {
  color: var(--green);
  background: rgba(0, 217, 163, 0.12);
}

.status-badge.delayed {
  color: #ffd166;
  background: rgba(255, 209, 102, 0.14);
}

.status-badge.stale,
.status-badge.missing {
  color: #ff8a9d;
  background: rgba(255, 77, 106, 0.14);
}

.status-badge.origin-cache {
  color: #ffd166;
  background: rgba(255, 209, 102, 0.14);
}

.status-badge.origin-database {
  color: #7be7ff;
  background: rgba(123, 231, 255, 0.12);
}

.status-badge.origin-realtime {
  color: var(--green);
  background: rgba(0, 217, 163, 0.12);
}
</style>
