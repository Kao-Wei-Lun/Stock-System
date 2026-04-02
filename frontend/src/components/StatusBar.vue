<template>
  <div class="statusbar">
    <div class="status-block">
      <div class="sb-dot" :class="connected ? 'live' : 'err'"></div>
      <span>{{ connected ? "連線中" : "重連中..." }}</span>
    </div>
    <div class="status-block">後端：<span class="status-accent">{{ backendUrl }}</span></div>
    <div class="status-block">延遲：<span class="status-accent">{{ latency }}</span></div>
    <div class="status-block">來源：<span>{{ quoteSource }}</span></div>
    <div class="status-block">模式：<span>{{ quoteMode }}</span></div>
    <div class="status-block">
      狀態：
      <span class="status-badge" :class="freshnessClass">{{ freshnessLabel }}</span>
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
  lastUpdate: { type: String, required: true },
  clockTime: { type: String, required: true },
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
  return freshnessState.value === "live" ? "即時" : "延遲快照";
});

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
</style>
