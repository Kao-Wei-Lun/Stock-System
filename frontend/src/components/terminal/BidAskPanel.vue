<template>
  <aside class="book-panel">
    <div class="book-head">
      <div>
        <div class="book-kicker">Order Book</div>
        <div class="book-title">五檔</div>
      </div>
      <div class="book-spread">{{ spreadLabel }}</div>
    </div>

    <div v-if="hasBookData" class="book-grid">
      <div class="book-section ask">
        <div v-for="row in askRows" :key="row.key" class="book-row">
          <span class="book-level">{{ row.label }}</span>
          <span class="book-price">{{ fmtPrice(row.price) }}</span>
          <span class="book-size">{{ formatSize(row.size) }}</span>
          <span class="book-bar"><span class="book-bar-fill ask" :style="{ width: `${row.ratio}%` }"></span></span>
        </div>
      </div>

      <div class="book-mid">
        <span>{{ symbolLabel }}</span>
        <strong>{{ midPriceLabel }}</strong>
      </div>

      <div class="book-section bid">
        <div v-for="row in bidRows" :key="row.key" class="book-row">
          <span class="book-level">{{ row.label }}</span>
          <span class="book-price">{{ fmtPrice(row.price) }}</span>
          <span class="book-size">{{ formatSize(row.size) }}</span>
          <span class="book-bar"><span class="book-bar-fill bid" :style="{ width: `${row.ratio}%` }"></span></span>
        </div>
      </div>
    </div>

    <div v-else class="book-empty">等待五檔資料</div>
  </aside>
</template>

<script setup>
import { computed } from "vue";

import { fmtPrice } from "../../utils/formatters";

const props = defineProps({
  quote: { type: Object, default: () => ({}) },
  ticker: { type: String, default: "" },
});

function normalizeLevels(levels, fallbackPrice, fallbackSize) {
  const source = Array.isArray(levels) ? levels.slice(0, 5) : [];
  if (!source.length && (fallbackPrice != null || fallbackSize != null)) {
    source.push({ price: fallbackPrice, size: fallbackSize });
  }
  const normalized = source.map((row) => ({
    price: row?.price == null ? null : Number(row.price),
    size: row?.size == null ? null : Number(row.size),
  }));
  while (normalized.length < 5) {
    normalized.push({ price: null, size: null });
  }
  return normalized;
}

const baseAskLevels = computed(() => normalizeLevels(props.quote?.asks, props.quote?.ask, props.quote?.ask_size));
const baseBidLevels = computed(() => normalizeLevels(props.quote?.bids, props.quote?.bid, props.quote?.bid_size));
const maxVisibleSize = computed(() => {
  const sizes = [...baseAskLevels.value, ...baseBidLevels.value]
    .map((row) => Number(row.size || 0))
    .filter((value) => value > 0);
  return sizes.length ? Math.max(...sizes) : 0;
});

function enrichRows(rows, prefix, reverse = false) {
  const ordered = reverse ? [...rows].reverse() : [...rows];
  return ordered.map((row, index) => {
    const level = reverse ? 5 - index : index + 1;
    const size = Number(row.size || 0);
    return {
      ...row,
      key: `${prefix}-${level}-${row.price ?? 'na'}-${size}`,
      label: `${prefix}${level}`,
      ratio: maxVisibleSize.value ? Math.max(8, Math.round((size / maxVisibleSize.value) * 100)) : 0,
    };
  });
}

const askRows = computed(() => enrichRows(baseAskLevels.value, "A", true));
const bidRows = computed(() => enrichRows(baseBidLevels.value, "B"));
const hasBookData = computed(() => [...baseAskLevels.value, ...baseBidLevels.value].some((row) => row.price != null || row.size != null));
const symbolLabel = computed(() => props.quote?.resolved_symbol || props.quote?.ticker || props.ticker || "-");
const midPriceLabel = computed(() => {
  const bid = Number(props.quote?.bid);
  const ask = Number(props.quote?.ask);
  if (Number.isFinite(bid) && Number.isFinite(ask)) {
    return fmtPrice((bid + ask) / 2);
  }
  if (props.quote?.price != null) return fmtPrice(props.quote.price);
  return "-";
});
const spreadLabel = computed(() => {
  const bid = Number(props.quote?.bid);
  const ask = Number(props.quote?.ask);
  if (Number.isFinite(bid) && Number.isFinite(ask)) {
    return `價差 ${fmtPrice(Math.max(ask - bid, 0))}`;
  }
  return "價差 -";
});

function formatSize(value) {
  if (value == null || value == "" || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString();
}
</script>

<style scoped>
.book-panel {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  padding: 16px 14px;
  background: rgba(9, 14, 23, 0.9);
}

.book-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.book-kicker {
  font-size: 10px;
  color: var(--text3);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.book-title {
  margin-top: 4px;
  font-size: 18px;
  font-weight: 700;
}

.book-spread {
  padding: 5px 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  font-size: 11px;
}

.book-grid {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.book-section {
  display: grid;
  gap: 6px;
}

.book-row {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr) minmax(0, 1fr) 44px;
  align-items: center;
  gap: 8px;
  min-height: 28px;
  font-size: 11px;
}

.book-level {
  color: var(--text3);
}

.book-price {
  font-variant-numeric: tabular-nums;
}

.book-section.ask .book-price {
  color: #ff8a9d;
}

.book-section.bid .book-price {
  color: #6ef3c8;
}

.book-size {
  color: var(--text2);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.book-bar {
  display: flex;
  justify-content: flex-end;
  width: 44px;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.05);
}

.book-bar-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
}

.book-bar-fill.ask {
  background: rgba(255, 77, 106, 0.76);
}

.book-bar-fill.bid {
  background: rgba(0, 217, 163, 0.76);
}

.book-mid {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  color: var(--text2);
}

.book-mid strong {
  color: var(--text1);
  font-size: 16px;
}

.book-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  margin-top: 16px;
  border: 1px dashed rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  color: var(--text3);
  font-size: 12px;
}
</style>
