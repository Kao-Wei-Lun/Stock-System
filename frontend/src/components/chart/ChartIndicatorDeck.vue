<template>
  <section v-if="open" class="indicator-deck">
    <div class="indicator-deck-head">
      <div>
        <div class="indicator-deck-kicker">Indicator Deck</div>
        <div class="indicator-deck-title">主圖疊加與副圖面板</div>
      </div>
      <button class="tool-btn compact" type="button" @click="$emit('close')">
        收合
      </button>
    </div>

    <div class="indicator-deck-summary">
      <span>{{ enabledOverlayCount }} 個主圖疊加啟用中</span>
      <span>{{ enabledPanelCount }} 個副圖面板啟用中</span>
    </div>

    <div class="indicator-deck-group">
      <div class="indicator-deck-label">快速模板</div>
      <div class="indicator-chip-grid presets">
        <button
          v-for="preset in presets"
          :key="preset.key"
          class="indicator-chip preset"
          type="button"
          @click="$emit('apply-indicator-preset', preset.key)"
        >
          <span>{{ preset.label }}</span>
          <small>{{ preset.hint }}</small>
        </button>
      </div>
    </div>

    <div class="indicator-deck-group">
      <div class="indicator-deck-label">主圖疊加</div>
      <div class="indicator-chip-grid">
        <button
          v-for="item in overlayItems"
          :key="item.key"
          class="indicator-chip"
          :class="{ active: activeInd[item.key] }"
          type="button"
          @click="$emit('toggle-indicator', item.key)"
        >
          <span>{{ item.label }}</span>
          <strong>{{ activeInd[item.key] ? "ON" : "OFF" }}</strong>
        </button>
      </div>
    </div>

    <div class="indicator-deck-group">
      <div class="indicator-deck-label">副圖面板</div>
      <div class="indicator-chip-grid">
        <button
          v-for="item in panelItems"
          :key="item.key"
          class="indicator-chip"
          :class="{ active: activePanels[item.key] }"
          type="button"
          @click="$emit('toggle-panel', item.key)"
        >
          <span>{{ item.label }}</span>
          <strong>{{ activePanels[item.key] ? "ON" : "OFF" }}</strong>
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  open: { type: Boolean, default: false },
  activeInd: { type: Object, required: true },
  activePanels: { type: Object, required: true },
});

defineEmits([
  "close",
  "toggle-indicator",
  "toggle-panel",
  "apply-indicator-preset",
]);

const presets = [
  { key: "trend", label: "趨勢模板", hint: "均線 / 趨勢通道 / ADX" },
  { key: "swing", label: "擺盪模板", hint: "RSI / MACD / KD" },
  { key: "volume", label: "量價模板", hint: "VWAP / MFI / OBV / CMF" },
  { key: "clean", label: "清爽模板", hint: "回到乾淨畫面" },
];

const overlayItems = [
  { key: "cycleMa", label: "週月季年線" },
  { key: "ma20", label: "MA20" },
  { key: "ma50", label: "MA50" },
  { key: "ma200", label: "MA200" },
  { key: "ema12", label: "EMA" },
  { key: "bb", label: "Bollinger" },
  { key: "psar", label: "PSAR" },
  { key: "keltner", label: "Keltner" },
  { key: "donchian", label: "Donchian" },
  { key: "vwap", label: "VWAP" },
  { key: "ichimoku", label: "Ichimoku" },
  { key: "supertrend", label: "SuperTrend" },
];

const panelItems = [
  { key: "rsi", label: "RSI" },
  { key: "aroon", label: "Aroon" },
  { key: "trix", label: "TRIX" },
  { key: "williamsr", label: "Williams %R" },
  { key: "mfi", label: "MFI" },
  { key: "roc", label: "ROC" },
  { key: "bbPercent", label: "BB %B" },
  { key: "bbWidth", label: "BB Width" },
  { key: "macd", label: "MACD" },
  { key: "stoch", label: "KD Stoch" },
  { key: "atr", label: "ATR" },
  { key: "cci", label: "CCI" },
  { key: "obv", label: "OBV" },
  { key: "adx", label: "ADX" },
  { key: "cmf", label: "CMF" },
];

const enabledOverlayCount = computed(() =>
  overlayItems.filter((item) => Boolean(props.activeInd[item.key])).length,
);

const enabledPanelCount = computed(() =>
  panelItems.filter((item) => Boolean(props.activePanels[item.key])).length,
);
</script>

<style scoped>
.indicator-deck {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 10px 12px 12px;
  border-bottom: 1px solid var(--border);
  background:
    linear-gradient(180deg, rgba(8, 13, 22, 0.98) 0%, rgba(10, 16, 26, 0.98) 100%),
    radial-gradient(circle at top right, rgba(123, 231, 255, 0.08), transparent 28%);
}

.indicator-deck-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.indicator-deck-kicker {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text3);
}

.indicator-deck-title {
  margin-top: 4px;
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.indicator-deck-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 10px;
  color: var(--text2);
}

.indicator-deck-summary span {
  padding: 5px 8px;
  border-radius: 999px;
  background: rgba(17, 25, 39, 0.96);
  border: 1px solid rgba(59, 139, 255, 0.16);
}

.indicator-deck-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.indicator-deck-label {
  font-size: 10px;
  color: var(--text3);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.indicator-chip-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
  gap: 8px;
}

.indicator-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
}

.indicator-chip:hover {
  color: var(--text);
  border-color: rgba(123, 231, 255, 0.26);
}

.indicator-chip strong,
.indicator-chip small {
  font-size: 9px;
  font-weight: 600;
}

.indicator-chip.active {
  border-color: rgba(123, 231, 255, 0.4);
  background: rgba(123, 231, 255, 0.12);
  color: #d7fbff;
}

.indicator-chip.preset {
  align-items: flex-start;
  flex-direction: column;
}

.indicator-chip.preset small {
  color: var(--text3);
  font-weight: 500;
}
</style>
