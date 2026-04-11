<template>
  <div class="chart-header">
    <div>
      <div class="ticker-row">
        <div class="ch-ticker">{{ currentTicker || "-" }}</div>
        <div class="ch-name">{{ currentName || "載入中..." }}</div>
      </div>
      <div class="quote-meta-row">
        <span class="quote-meta-pill" :class="quote.is_delayed === false ? 'live' : 'delayed'">
          {{ quoteModeLabel }}
        </span>
        <span class="quote-meta-pill">{{ quoteTimestampLabel }}</span>
        <span v-if="quote.bid != null || quote.ask != null" class="quote-meta-pill">
          B {{ fmtPrice(quote.bid) }} / A {{ fmtPrice(quote.ask) }}
        </span>
      </div>
      <div v-if="quoteFreshnessState !== 'live'" class="quote-risk-banner" :class="quoteFreshnessState">
        {{ quoteFreshnessHint }}
      </div>
      <div v-if="showMacroRegimeBanner" class="market-regime-banner" :class="macroRegimeClass">
        <span class="market-regime-pill">{{ macroRiskLabel }}</span>
        <strong>{{ macroPostureLabel }}</strong>
        <span>{{ macroDecisionHint }}</span>
      </div>
    </div>
    <div class="ch-price" :class="quote.change_pct >= 0 ? 'up' : 'dn'">{{ displayPrice }}</div>
    <div class="ch-chg" :class="quote.change_pct >= 0 ? 'up' : 'dn'">{{ displayChange }}</div>
    <div class="ch-stats">
      <div class="ch-stat"><span>開盤</span><span>{{ fmtPrice(quote.open) }}</span></div>
      <div class="ch-stat"><span>最高</span><span style="color: var(--green)">{{ fmtPrice(quote.high) }}</span></div>
      <div class="ch-stat"><span>最低</span><span style="color: var(--red)">{{ fmtPrice(quote.low) }}</span></div>
      <div class="ch-stat"><span>成交量</span><span>{{ fmtVol(quote.volume) }}</span></div>
      <div class="ch-stat"><span>市值</span><span>{{ fmtMktCap(quote.market_cap) }}</span></div>
    </div>
  </div>
</template>

<script setup>
import { fmtMktCap, fmtPrice, fmtVol } from "../../utils/formatters";

defineProps({
  currentTicker: { type: String, required: true },
  currentName: { type: String, required: true },
  quote: { type: Object, required: true },
  displayPrice: { type: String, required: true },
  displayChange: { type: String, required: true },
  quoteTimestampLabel: { type: String, required: true },
  quoteModeLabel: { type: String, required: true },
  quoteFreshnessState: { type: String, required: true },
  quoteFreshnessHint: { type: String, required: true },
  showMacroRegimeBanner: { type: Boolean, default: false },
  macroRegimeClass: { type: String, required: true },
  macroRiskLabel: { type: String, required: true },
  macroPostureLabel: { type: String, required: true },
  macroDecisionHint: { type: String, required: true },
});
</script>

<style scoped>
.ticker-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.ch-name {
  font-size: 11px;
  color: var(--text3);
}

.quote-meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.quote-meta-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 4px 8px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  font-size: 11px;
  line-height: 1.4;
}

.quote-meta-pill.live {
  border-color: rgba(0, 217, 163, 0.24);
  color: var(--green);
}

.quote-meta-pill.delayed {
  border-color: rgba(255, 209, 102, 0.22);
  color: #ffd166;
}

.quote-risk-banner {
  display: inline-flex;
  align-items: center;
  margin-top: 6px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  line-height: 1.4;
}

.quote-risk-banner.delayed {
  background: rgba(255, 209, 102, 0.14);
  color: #ffd166;
}

.quote-risk-banner.stale,
.quote-risk-banner.missing {
  background: rgba(255, 77, 106, 0.14);
  color: #ff8a9d;
}

.market-regime-banner {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 12px;
  font-size: 11px;
  line-height: 1.5;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text2);
}

.market-regime-banner strong {
  color: var(--text1);
}

.market-regime-pill {
  border-radius: 999px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.08);
}

.market-regime-banner.is-defensive {
  background: rgba(255, 107, 107, 0.12);
}

.market-regime-banner.is-defensive .market-regime-pill {
  background: rgba(255, 107, 107, 0.2);
  color: #ffd0d0;
}

.market-regime-banner.is-selective,
.market-regime-banner.is-balanced {
  background: rgba(255, 209, 102, 0.12);
}

.market-regime-banner.is-selective .market-regime-pill,
.market-regime-banner.is-balanced .market-regime-pill {
  background: rgba(255, 209, 102, 0.2);
  color: #ffe2a6;
}

.market-regime-banner.is-offensive {
  background: rgba(0, 217, 163, 0.12);
}

.market-regime-banner.is-offensive .market-regime-pill {
  background: rgba(0, 217, 163, 0.2);
  color: #bfffea;
}
</style>
