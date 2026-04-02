<template>
  <div class="overlay" :class="{ open: isOpen }">
    <div class="modal">
      <div class="modal-title">設定警報條件</div>
      <div class="modal-row">
        <div class="modal-label">{{ tickerLabel }}</div>
        <input
          class="modal-input"
          :value="form.ticker"
          :placeholder="tickerPlaceholder"
          style="text-transform:uppercase"
          :disabled="tickerDisabled"
          @input="$emit('update-field', { key: 'ticker', value: $event.target.value })"
        >
      </div>
      <div class="modal-row">
        <div class="modal-label">警報類型</div>
        <select class="modal-select" :value="form.type" @change="$emit('update-field', { key: 'type', value: $event.target.value })">
          <option value="price">價格條件</option>
          <option value="rsi">RSI 條件</option>
          <option value="macd">MACD 交叉</option>
          <option value="pct">單日漲跌幅</option>
          <option value="volume">量比異常</option>
          <option value="market_risk">市場風險</option>
        </select>
      </div>
      <div class="modal-row">
        <div class="modal-label">條件</div>
        <select class="modal-select" :value="form.cond" @change="$emit('update-field', { key: 'cond', value: $event.target.value })">
          <option v-for="option in conditionOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
      </div>
      <div class="modal-row">
        <div class="modal-label">{{ valueLabel }}</div>
        <input
          class="modal-input"
          :value="form.value"
          type="number"
          :placeholder="valuePlaceholder"
          :disabled="!requiresNumericValue"
          @input="$emit('update-field', { key: 'value', value: $event.target.value })"
        >
      </div>
      <div class="modal-row modal-note">
        <span>{{ helperText }}</span>
      </div>
      <div class="modal-actions">
        <button class="modal-btn primary" @click="$emit('save')">儲存</button>
        <button class="modal-btn secondary" @click="$emit('close')">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  isOpen: { type: Boolean, required: true },
  form: { type: Object, required: true },
});

defineEmits(["close", "save", "update-field"]);

const genericConditions = [
  { label: "大於", value: "大於" },
  { label: "小於", value: "小於" },
  { label: "上穿", value: "上穿" },
  { label: "下穿", value: "下穿" },
];

const macdConditions = [
  { label: "黃金交叉", value: "上穿" },
  { label: "死亡交叉", value: "下穿" },
  { label: "大於", value: "大於" },
  { label: "小於", value: "小於" },
];

const volumeConditions = [
  { label: "大於", value: "大於" },
  { label: "小於", value: "小於" },
];

const marketRiskConditions = [
  { label: "進入高風險", value: "high" },
  { label: "進入中風險以上", value: "medium_or_high" },
  { label: "進入 risk-off", value: "risk_off" },
  { label: "進入偏進攻", value: "offensive" },
];

const conditionOptions = computed(() => {
  if (props.form.type === "macd") return macdConditions;
  if (props.form.type === "volume") return volumeConditions;
  if (props.form.type === "market_risk") return marketRiskConditions;
  return genericConditions;
});

const requiresNumericValue = computed(() => {
  if (props.form.type === "market_risk") return false;
  return !(
    props.form.type === "macd" && ["上穿", "下穿", "cross_up", "cross_down"].includes(props.form.cond)
  );
});

const tickerDisabled = computed(() => props.form.type === "market_risk");
const tickerLabel = computed(() => (props.form.type === "market_risk" ? "市場範圍" : "股票代號"));
const tickerPlaceholder = computed(() => (props.form.type === "market_risk" ? "MARKET" : "AAPL"));

const valueLabel = computed(() => {
  if (props.form.type === "market_risk") return "市場條件";
  if (props.form.type === "volume") return "量比門檻";
  if (props.form.type === "pct") return "漲跌幅(%)";
  if (props.form.type === "rsi") return "RSI 數值";
  return "數值";
});

const valuePlaceholder = computed(() => {
  if (props.form.type === "market_risk") return "市場型警報不需填數值";
  if (!requiresNumericValue.value) return "交叉條件不需填寫";
  if (props.form.type === "rsi") return "70 或 30";
  if (props.form.type === "pct") return "5 或 -3";
  if (props.form.type === "volume") return "2.0";
  if (props.form.type === "macd") return "0";
  return "190.00";
});

const helperText = computed(() => {
  if (props.form.type === "macd" && !requiresNumericValue.value) {
    return "MACD 黃金交叉 / 死亡交叉會使用 MACD 線與訊號線的交叉判斷。";
  }
  if (props.form.type === "volume") {
    return "量比異常會以近 20 根日 K 的平均量作為基準。";
  }
  if (props.form.type === "rsi") {
    return "RSI 可設定大於 / 小於 / 上穿 / 下穿，例如 70 與 30。";
  }
  if (props.form.type === "market_risk") {
    return "市場風險警報會直接讀取本地 macro_snapshots，不依賴外部即時報價。";
  }
  return "所有警報都會記錄觸發時間、數值與資料來源。";
});
</script>
