<template>
  <div class="overlay" :class="{ open: isOpen }">
    <div class="modal">
      <div class="modal-title">🔔 設定警報條件</div>
      <div class="modal-row">
        <div class="modal-label">股票代號</div>
        <input class="modal-input" :value="form.ticker" placeholder="AAPL" style="text-transform:uppercase" @input="$emit('update-field', { key: 'ticker', value: $event.target.value })">
      </div>
      <div class="modal-row">
        <div class="modal-label">警報類型</div>
        <select class="modal-select" :value="form.type" @change="$emit('update-field', { key: 'type', value: $event.target.value })">
          <option value="price">價格突破</option>
          <option value="rsi">RSI 條件</option>
          <option value="macd">MACD 交叉</option>
          <option value="pct">單日漲跌幅</option>
        </select>
      </div>
      <div class="modal-row">
        <div class="modal-label">條件</div>
        <select class="modal-select" :value="form.cond" @change="$emit('update-field', { key: 'cond', value: $event.target.value })">
          <option>大於</option>
          <option>小於</option>
          <option>上穿</option>
          <option>下穿</option>
        </select>
      </div>
      <div class="modal-row">
        <div class="modal-label">數值</div>
        <input class="modal-input" :value="form.value" type="number" placeholder="190.00" @input="$emit('update-field', { key: 'value', value: $event.target.value })">
      </div>
      <div class="modal-actions">
        <button class="modal-btn primary" @click="$emit('save')">儲存</button>
        <button class="modal-btn secondary" @click="$emit('close')">取消</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  isOpen: { type: Boolean, required: true },
  form: { type: Object, required: true },
});

defineEmits(["close", "save", "update-field"]);
</script>
