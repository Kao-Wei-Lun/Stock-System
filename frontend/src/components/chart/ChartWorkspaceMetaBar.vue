<template>
  <div class="chart-meta">
    <div class="meta-chip">{{ visibleRangeLabel }}</div>
    <div class="meta-chip">{{ visibleBarsLabel }}</div>
    <div class="meta-chip" :class="visibleChangeClass">{{ visibleChangeLabel }}</div>
    <div class="meta-chip">{{ zoomLabel }}</div>
    <button
      class="meta-chip y-scale-chip"
      :class="{ warn: yScaleClipped, interactive: yScaleLabel.includes('手動') || yScaleClipped }"
      type="button"
      :disabled="!yScaleLabel.includes('手動') && !yScaleClipped"
      :aria-label="yScaleClipped ? 'K 線超出手動 Y 軸範圍，恢復自動縮放' : '恢復 Y 軸自動縮放'"
      @click="$emit('reset-y-scale')"
    >
      {{ yScaleClipped ? `⚠ 資料超出範圍 · ${yScaleLabel}` : yScaleLabel }}
    </button>
    <div class="meta-chip">{{ priceScaleModeLabel }}</div>
    <div class="meta-chip">{{ quoteTimestampLabel }}</div>
    <div class="meta-chip">{{ quoteSourceLabel }}</div>
    <div class="meta-chip" :class="{ up: !quote.is_delayed, dn: quote.is_delayed }">{{ quoteDelayLabel }}</div>
    <div class="meta-chip" :class="quoteFreshnessChipClass">{{ quoteFreshnessLabel }}</div>
    <div v-if="institutionalOverlay" class="meta-chip">
      {{ institutionalOverlay.label }} / Basis
      {{ institutionalOverlay.basis == null ? "—" : `${institutionalOverlay.basis >= 0 ? "+" : ""}${fmtPrice(institutionalOverlay.basis)} (${institutionalOverlay.basisPct >= 0 ? "+" : ""}${Number(institutionalOverlay.basisPct || 0).toFixed(2)}%)` }}
    </div>
    <div class="meta-chip is-hint">{{ interactionHint }}</div>
  </div>
</template>

<script setup>
import { fmtPrice } from "../../utils/formatters";

defineProps({
  visibleRangeLabel: { type: String, required: true },
  visibleBarsLabel: { type: String, required: true },
  visibleChangeLabel: { type: String, required: true },
  visibleChangeClass: { type: [String, Object, Array], default: "" },
  zoomLabel: { type: String, required: true },
  yScaleLabel: { type: String, required: true },
  yScaleClipped: { type: Boolean, default: false },
  priceScaleModeLabel: { type: String, required: true },
  quoteTimestampLabel: { type: String, required: true },
  quoteSourceLabel: { type: String, required: true },
  quoteDelayLabel: { type: String, required: true },
  quoteFreshnessLabel: { type: String, required: true },
  quoteFreshnessChipClass: { type: [String, Object, Array], default: "" },
  institutionalOverlay: { type: Object, default: null },
  interactionHint: { type: String, required: true },
  quote: { type: Object, required: true },
});

defineEmits(["reset-y-scale"]);
</script>

<style scoped>
.meta-chip.warn {
  color: #ffd166;
  border-color: rgba(255, 209, 102, 0.24);
}

.y-scale-chip {
  font: inherit;
}

.y-scale-chip:disabled {
  cursor: default;
  opacity: 1;
}

.y-scale-chip.interactive {
  cursor: pointer;
}
</style>
