<template>
  <div class="chart-meta">
    <div class="meta-chip">{{ visibleRangeLabel }}</div>
    <div class="meta-chip">{{ visibleBarsLabel }}</div>
    <div class="meta-chip" :class="visibleChangeClass">{{ visibleChangeLabel }}</div>
    <div class="meta-chip">{{ zoomLabel }}</div>
    <div class="meta-chip">{{ yScaleLabel }}</div>
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
</script>

<style scoped>
.meta-chip.warn {
  color: #ffd166;
  border-color: rgba(255, 209, 102, 0.24);
}
</style>
