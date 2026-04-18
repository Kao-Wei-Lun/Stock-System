<template>
  <div class="chip-tabs-shell">
    <div class="chip-tabs">
      <button
        type="button"
        class="chip-tab-btn"
        :class="{ active: activeView === 'stock' }"
        @click="$emit('change', 'stock')"
      >
        個股籌碼追蹤
      </button>
      <button
        type="button"
        class="chip-tab-btn"
        :class="{ active: activeView === 'market' }"
        @click="$emit('change', 'market')"
      >
        大盤 / TAIFEX 法人籌碼
      </button>
    </div>
    <div v-if="!stockSupported" class="chip-tabs-note">
      目前標的不支援個股籌碼，切換到台股個股後會自動帶出歷史追蹤。
    </div>
  </div>
</template>

<script setup>
defineProps({
  activeView: { type: String, default: "market" },
  stockSupported: { type: Boolean, default: false },
});

defineEmits(["change"]);
</script>

<style scoped>
.chip-tabs-shell {
  display: grid;
  gap: 10px;
  padding: 16px 18px 0;
}

.chip-tabs {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  padding: 6px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(7, 12, 20, 0.72);
}

.chip-tab-btn {
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--text2);
  font-family: "JetBrains Mono", monospace;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.chip-tab-btn:hover {
  color: var(--text);
  border-color: rgba(255, 255, 255, 0.08);
}

.chip-tab-btn.active {
  border-color: rgba(123, 231, 255, 0.24);
  background: linear-gradient(135deg, rgba(123, 231, 255, 0.16), rgba(59, 139, 255, 0.14));
  color: #eefcff;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.chip-tabs-note {
  color: var(--text3);
  font-size: 11px;
  line-height: 1.5;
}

@media (max-width: 720px) {
  .chip-tabs-shell {
    padding: 12px 12px 0;
  }

  .chip-tabs {
    width: 100%;
    flex-wrap: wrap;
    border-radius: 18px;
  }

  .chip-tab-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
