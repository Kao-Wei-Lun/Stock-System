<template>
  <div class="chip-insight-grid">
    <div class="institutional-section">
      <div class="institutional-section-head">
        <div>
          <div class="ind-group-title">最近轉折</div>
          <div class="institutional-section-note">用方向切換與連續性來抓出最近值得回頭看的日期。</div>
        </div>
      </div>

      <div class="institutional-card">
        <div v-if="turningPoints.length" class="institutional-rows">
          <div v-for="item in turningPoints" :key="`${item.date}-${item.label}`" class="inst-row wide">
            <div>
              <strong>{{ item.label }}</strong>
              <div class="inst-row-sub">{{ item.date }}</div>
            </div>
            <div class="inst-row-metrics">
              <span :class="item.tone">{{ item.value }}</span>
              <span>{{ item.note }}</span>
            </div>
          </div>
        </div>
        <div v-else class="institutional-empty institutional-empty-compact">
          近幾日還沒有明顯翻向訊號，先觀察區間累積與價格配合。
        </div>
      </div>
    </div>

    <div class="institutional-section">
      <div class="institutional-section-head">
        <div>
          <div class="ind-group-title">研究提醒</div>
          <div class="institutional-section-note">把籌碼背離、主導法人與區間強弱濃縮成幾句可以直接採取行動的提示。</div>
        </div>
      </div>

      <div class="institutional-card">
        <div class="institutional-rows">
          <div v-for="item in insights" :key="item.title" class="inst-row wide">
            <div>
              <strong>{{ item.title }}</strong>
              <div class="inst-row-sub">{{ item.detail }}</div>
            </div>
            <div class="inst-row-metrics">
              <span :class="item.tone">{{ item.value }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  chipHistory: { type: Object, default: null },
  rangeDays: { type: Number, default: 20 },
});

function formatSigned(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "±0";
  return `${numeric > 0 ? "+" : "-"}${Math.abs(numeric).toLocaleString()}`;
}

const series = computed(() => props.chipHistory?.series || []);
const priceSeries = computed(() => props.chipHistory?.price_series || []);
const stats = computed(() => props.chipHistory?.stats || {});

function getDirection(value) {
  const numeric = Number(value || 0);
  if (!numeric) return "flat";
  return numeric > 0 ? "buy" : "sell";
}

const turningPoints = computed(() => {
  const items = [];
  for (let index = 1; index < series.value.length; index += 1) {
    const previous = series.value[index - 1];
    const current = series.value[index];

    if (getDirection(previous?.foreign_net_buy_sell) !== getDirection(current?.foreign_net_buy_sell)) {
      items.push({
        date: current.snapshot_date,
        label: "外資方向切換",
        value: formatSigned(current.foreign_net_buy_sell),
        note: getDirection(current.foreign_net_buy_sell) === "buy" ? "由賣轉買" : "由買轉賣",
        tone: getDirection(current.foreign_net_buy_sell) === "buy" ? "up" : "dn",
      });
    }

    if (getDirection(previous?.institutional_net_buy_sell) !== getDirection(current?.institutional_net_buy_sell)) {
      items.push({
        date: current.snapshot_date,
        label: "法人合計翻向",
        value: formatSigned(current.institutional_net_buy_sell),
        note: getDirection(current.institutional_net_buy_sell) === "buy" ? "由賣轉買" : "由買轉賣",
        tone: getDirection(current.institutional_net_buy_sell) === "buy" ? "up" : "dn",
      });
    }
  }

  return items.slice(-4).reverse();
});

const priceMove = computed(() => {
  if (priceSeries.value.length < 2) return null;
  const first = Number(priceSeries.value[0]?.close);
  const last = Number(priceSeries.value[priceSeries.value.length - 1]?.close);
  if (!Number.isFinite(first) || !Number.isFinite(last) || !first) return null;
  return {
    absolute: last - first,
    percent: ((last - first) / first) * 100,
  };
});

const insights = computed(() => {
  const result = [];
  const institutional20d = Number(stats.value.institutional_20d_sum || 0);
  const foreign20d = Number(stats.value.foreign_20d_sum || 0);
  const trust20d = Number(stats.value.investment_trust_20d_sum || 0);

  if (priceMove.value) {
    const divergence = institutional20d > 0 && priceMove.value.percent <= 0
      ? "籌碼偏多但價格尚未同步"
      : institutional20d < 0 && priceMove.value.percent >= 0
        ? "價格偏強但法人在退場"
        : "籌碼與價格方向大致同步";
    result.push({
      title: "籌碼 / 價格關係",
      detail: `近 ${props.rangeDays} 日股價變動 ${priceMove.value.percent >= 0 ? "+" : ""}${priceMove.value.percent.toFixed(2)}%。`,
      value: divergence,
      tone: divergence.includes("同步") ? "" : divergence.includes("偏多") ? "up" : "dn",
    });
  }

  const dominant = [
    { label: "外資", value: foreign20d },
    { label: "投信", value: trust20d },
    { label: "法人合計", value: institutional20d },
  ].sort((left, right) => Math.abs(right.value) - Math.abs(left.value))[0];
  result.push({
    title: "主導力量",
    detail: `近 20 日累積變化最大的角色是 ${dominant.label}。`,
    value: formatSigned(dominant.value),
    tone: dominant.value >= 0 ? "up" : "dn",
  });

  result.push({
    title: "連續性",
    detail: Number(stats.value.institutional_streak_days || 0)
      ? `法人合計已連續 ${stats.value.institutional_streak_days} 日${stats.value.institutional_streak_direction === "buy" ? "買超" : "賣超"}。`
      : "目前沒有明顯的連續買賣超。",
    value: Number(stats.value.institutional_streak_days || 0)
      ? `${stats.value.institutional_streak_days} 日`
      : "觀望",
    tone: stats.value.institutional_streak_direction === "sell" ? "dn" : "up",
  });

  return result.slice(0, 3);
});
</script>

<style scoped>
.chip-insight-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 960px) {
  .chip-insight-grid {
    grid-template-columns: 1fr;
  }
}
</style>
