<template>
  <TransitionGroup name="toast-stack" tag="div" class="toast-stack-shell">
    <article
      v-for="item in visibleToasts"
      :key="item.id"
      class="toast-card"
      :class="item.level || item.type || 'info'"
      :tabindex="item.ticker || item.workspaceTarget ? 0 : -1"
      @click="handleSelect(item)"
      @keydown.enter.prevent="handleSelect(item)"
    >
      <div class="toast-icon">{{ item.icon || "•" }}</div>
      <div class="toast-copy">
        <div class="toast-title">{{ item.title }}</div>
        <div class="toast-msg">{{ item.msg }}</div>
      </div>
      <button
        class="toast-dismiss"
        type="button"
        aria-label="關閉提示"
        @click.stop="$emit('dismiss', item.id)"
      >
        ×
      </button>
    </article>
  </TransitionGroup>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  notifications: { type: Array, required: true },
  limit: { type: Number, default: 3 },
});

const emit = defineEmits(["dismiss", "select"]);

const visibleToasts = computed(() =>
  (props.notifications || [])
    .filter((item) => ["session", "alert"].includes(item?.category) && item?.read !== true)
    .slice(-props.limit)
    .reverse(),
);

function handleSelect(item) {
  if (!item) return;
  emit("select", item);
}
</script>

<style scoped>
.toast-stack-shell {
  position: fixed;
  right: 18px;
  bottom: 92px;
  z-index: 42;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(360px, calc(100vw - 24px));
  pointer-events: none;
}

.toast-card {
  display: grid;
  grid-template-columns: 36px 1fr auto;
  gap: 10px;
  align-items: start;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-left-width: 4px;
  border-radius: 14px;
  background: rgba(5, 10, 17, 0.94);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
  backdrop-filter: blur(16px);
  pointer-events: auto;
  cursor: pointer;
}

.toast-card.info {
  border-left-color: #7be7ff;
}

.toast-card.success {
  border-left-color: #5dd39e;
}

.toast-card.warning {
  border-left-color: #ffd166;
}

.toast-card.error {
  border-left-color: #ff7b72;
}

.toast-icon {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text1);
  font-size: 16px;
}

.toast-copy {
  min-width: 0;
}

.toast-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text1);
}

.toast-msg {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text2);
  word-break: break-word;
}

.toast-dismiss {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text3);
  cursor: pointer;
}

.toast-stack-enter-active,
.toast-stack-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-stack-enter-from,
.toast-stack-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@media (max-width: 640px) {
  .toast-stack-shell {
    right: 12px;
    left: 12px;
    bottom: 92px;
    width: auto;
  }
}
</style>
