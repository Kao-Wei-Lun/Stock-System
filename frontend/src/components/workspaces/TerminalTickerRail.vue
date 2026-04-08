<template>
  <aside class="terminal-rail">
    <div class="terminal-rail-head">
      <div>
        <div class="terminal-rail-kicker">Quick Switch</div>
        <div class="terminal-rail-title">{{ activeGroupLabel }}</div>
      </div>
      <button class="terminal-rail-btn" type="button" @click="$emit('open-overview')">
        總覽
      </button>
    </div>

    <div class="terminal-rail-list">
      <button
        v-for="item in visibleItems"
        :key="`${item.group_id || 'watch'}-${item.ticker}`"
        class="terminal-rail-item"
        :class="{ active: item.ticker === activeTicker }"
        :style="getGroupAccentStyle(item)"
        type="button"
        @click="$emit('select-ticker', item)"
      >
        <span class="terminal-rail-accent" :style="getGroupColorStyle(item.group_color)"></span>
        <div class="terminal-rail-main">
          <div class="terminal-rail-symbol">{{ item.ticker }}</div>
          <div class="terminal-rail-name">{{ item.name || item.group_name || "" }}</div>
        </div>
        <div class="terminal-rail-side">
          <div class="terminal-rail-price" :class="Number(item.change_pct || 0) >= 0 ? 'up' : 'dn'">
            {{ formatPrice(item.close) }}
          </div>
          <div class="terminal-rail-change" :class="Number(item.change_pct || 0) >= 0 ? 'up' : 'dn'">
            {{ Number(item.change_pct || 0) >= 0 ? "+" : "" }}{{ Number(item.change_pct || 0).toFixed(2) }}%
          </div>
        </div>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from "vue";

import { fmtPrice } from "../../utils/formatters";

const props = defineProps({
  items: { type: Array, default: () => [] },
  groups: { type: Array, default: () => [] },
  activeGroupId: { type: Number, default: null },
  activeTicker: { type: String, default: "" },
});

defineEmits(["select-ticker", "open-overview"]);

const activeGroupLabel = computed(() => {
  const group = (props.groups || []).find((item) => item.id === props.activeGroupId);
  return group?.name || "當前觀察池";
});

const visibleItems = computed(() => {
  const items = Array.isArray(props.items) ? props.items : [];
  if (!items.length) return [];
  const scoped = props.activeGroupId == null
    ? items
    : items.filter((item) => Number(item.group_id) === Number(props.activeGroupId));
  const source = scoped.length ? scoped : items;
  return source.slice(0, 18);
});

function formatPrice(value) {
  return fmtPrice(value);
}

function getGroupColorStyle(color) {
  return {
    background: color || "rgba(255, 255, 255, 0.12)",
  };
}

function getGroupAccentStyle(item) {
  return item?.group_color
    ? {
      borderColor: `${item.group_color}33`,
      boxShadow: `inset 0 0 0 1px ${item.group_color}16`,
    }
    : {};
}
</script>

<style scoped>
.terminal-rail {
  width: 248px;
  min-width: 248px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  background:
    linear-gradient(180deg, rgba(9, 14, 23, 0.98), rgba(7, 12, 20, 0.98)),
    radial-gradient(circle at top left, rgba(123, 231, 255, 0.12), transparent 30%);
}

.terminal-rail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 14px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.terminal-rail-kicker {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text3);
}

.terminal-rail-title {
  margin-top: 4px;
  font-family: "Syne", sans-serif;
  font-size: 15px;
  font-weight: 700;
  color: var(--text1);
}

.terminal-rail-btn {
  padding: 7px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  font-size: 10px;
}

.terminal-rail-list {
  flex: 1;
  overflow: auto;
  padding: 10px;
}

.terminal-rail-item {
  position: relative;
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 10px 11px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  color: var(--text1);
  cursor: pointer;
  text-align: left;
}

.terminal-rail-item + .terminal-rail-item {
  margin-top: 8px;
}

.terminal-rail-item.active {
  border-color: rgba(123, 231, 255, 0.28);
  background: rgba(123, 231, 255, 0.08);
}

.terminal-rail-accent {
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 4px;
  border-radius: 999px;
}

.terminal-rail-main,
.terminal-rail-side {
  min-width: 0;
}

.terminal-rail-symbol {
  font-size: 13px;
  font-weight: 700;
}

.terminal-rail-name {
  margin-top: 3px;
  font-size: 10px;
  color: var(--text3);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.terminal-rail-side {
  text-align: right;
}

.terminal-rail-price {
  font-size: 12px;
  font-weight: 700;
}

.terminal-rail-change {
  margin-top: 2px;
  font-size: 10px;
}

.up {
  color: var(--green);
}

.dn {
  color: var(--red);
}
</style>
