<template>
  <div class="institutional-section">
    <div class="institutional-section-head">
      <div class="ind-group-title">法人籌碼歷史趨勢</div>
      <div class="institutional-section-note">期貨淨口數、選擇權買賣權失衡、現貨買賣超與未平倉成本帶</div>
    </div>
    <div class="institutional-trend-grid">
      <InstitutionalTrendChart
        class="trend-card-wide"
        title="期貨未平倉淨口數"
        :subtitle="`${selectedFuturesCommodity} / 分法人絕對口數`"
        :points="insights?.history?.futures_oi || []"
        :series="trendSeries"
        split-series
        show-zero-line
      />
      <InstitutionalTrendChart
        title="期貨交易淨口數"
        :subtitle="selectedFuturesCommodity"
        :points="insights?.history?.futures_trade || []"
        :series="trendSeries"
      />
      <InstitutionalTrendChart
        title="選擇權未平倉淨口數"
        :subtitle="selectedOptionsCommodity"
        :points="insights?.history?.options_oi || []"
        :series="trendSeries"
      />
      <InstitutionalTrendChart
        title="買權 / 賣權 OI 失衡"
        :subtitle="selectedOptionsCommodity"
        :points="insights?.history?.call_put_balance || []"
        :series="trendSeries"
      />
      <InstitutionalTrendChart
        title="現貨三大法人買賣超"
        subtitle="TWSE 現貨市場"
        :points="insights?.history?.cash_net || []"
        :series="trendSeries"
        value-format="amount"
      />
      <InstitutionalTrendChart
        title="未平倉成本帶"
        :subtitle="selectedFuturesCommodity"
        :points="insights?.history?.cost_band || []"
        :series="costSeries"
        band-min-key="成本帶低"
        band-max-key="成本帶高"
        value-format="price"
      />
    </div>
  </div>
</template>

<script setup>
import InstitutionalTrendChart from "../InstitutionalTrendChart.vue";

defineProps({
  insights: { type: Object, default: null },
  selectedFuturesCommodity: { type: String, default: "" },
  selectedOptionsCommodity: { type: String, default: "" },
  trendSeries: { type: Array, default: () => [] },
  costSeries: { type: Array, default: () => [] },
});
</script>
