<template>
  <div class="statusbar">
    <div style="display:flex;align-items:center;gap:5px">
      <div class="sb-dot" :class="connected ? 'live' : 'err'"></div>
      <span>{{ connected ? "連線中" : "重連中..." }}</span>
    </div>
    <div>後端：<span style="color:var(--green)">{{ backendUrl }}</span></div>
    <div>延遲：<span style="color:var(--green)">{{ latency }}</span></div>
    <div style="margin-left:auto">更新：<span>{{ lastUpdate }}</span></div>
    <div>{{ clockTime }}</div>
  </div>
</template>

<script setup>
defineProps({
  connected: { type: Boolean, required: true },
  backendUrl: { type: String, required: true },
  latency: { type: String, required: true },
  lastUpdate: { type: String, required: true },
  clockTime: { type: String, required: true },
});
</script>
