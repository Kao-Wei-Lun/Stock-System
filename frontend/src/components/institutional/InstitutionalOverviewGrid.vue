<template>
  <div class="institutional-grid">
    <div class="institutional-card">
      <div class="ind-group-title">現貨參考</div>
      <div class="institutional-kpis">
        <div v-for="item in data?.spot_reference || []" :key="item.ticker" class="inst-kpi">
          <div class="inst-kpi-label">{{ item.label }}</div>
          <div class="inst-kpi-value">{{ fmtPrice(item.price) }}</div>
          <div class="inst-kpi-change" :class="Number(item.change_pct) >= 0 ? 'up' : 'dn'">
            {{ Number(item.change_pct) >= 0 ? "+" : "" }}{{ Number(item.change_pct || 0).toFixed(2) }}%
          </div>
        </div>
      </div>
    </div>

    <div class="institutional-card">
      <div class="ind-group-title">現貨三大法人買賣超</div>
      <div class="institutional-rows compact">
        <div v-for="row in aggregatedCashSummary" :key="row.institution" class="inst-row">
          <span>{{ row.institution }}</span>
          <span :class="Number(row.net_amount) >= 0 ? 'up' : 'dn'">
            {{ formatSigned(row.net_amount, true) }}
          </span>
        </div>
      </div>
    </div>

    <div class="institutional-card">
      <div class="ind-group-title">期貨 / 選擇權總覽</div>
      <div class="institutional-rows">
        <div v-for="row in data?.overview || []" :key="row.institution" class="inst-row wide">
          <div>
            <strong>{{ row.institution }}</strong>
            <div class="inst-row-sub">
              期貨淨口數
              <span :class="row.trade_net_futures_volume >= 0 ? 'up' : 'dn'">
                {{ formatSigned(row.trade_net_futures_volume) }}
              </span>
            </div>
          </div>
          <div class="inst-row-metrics">
            <span :class="row.trade_net_futures_volume_change >= 0 ? 'up' : 'dn'">
              Δ {{ formatSigned(row.trade_net_futures_volume_change) }}
            </span>
            <span :class="row.trade_net_options_volume >= 0 ? 'up' : 'dn'">
              選擇權 {{ formatSigned(row.trade_net_options_volume) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="institutional-card">
      <div class="ind-group-title">重點籌碼</div>
      <div class="institutional-rows">
        <div class="inst-row wide">
          <div>
            <strong>{{ selectedFuturesCommodity || "—" }}</strong>
            <div class="inst-row-sub">法人合成淨未平倉 / 散戶推估對手方</div>
          </div>
          <div class="inst-row-metrics">
            <span :class="futuresCostEstimate?.institution_estimate?.net_volume >= 0 ? 'up' : 'dn'">
              {{ formatSigned(futuresCostEstimate?.institution_estimate?.net_volume) }}
            </span>
            <span>{{ futuresCostEstimate?.institution_estimate?.side || "—" }} / {{ fmtPrice(futuresCostEstimate?.institution_estimate?.price) }}</span>
          </div>
        </div>
        <div class="inst-row wide">
          <div>
            <strong>{{ selectedOptionsCommodity || "—" }}</strong>
            <div class="inst-row-sub">外資 Put / Call OI 差</div>
          </div>
          <div class="inst-row-metrics">
            <span :class="foreignCallPutBalance >= 0 ? 'up' : 'dn'">{{ formatSigned(foreignCallPutBalance) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { fmtPrice } from "../../utils/formatters";

defineProps({
  data: { type: Object, default: null },
  aggregatedCashSummary: { type: Array, default: () => [] },
  selectedFuturesCommodity: { type: String, default: "" },
  selectedOptionsCommodity: { type: String, default: "" },
  futuresCostEstimate: { type: Object, default: () => ({}) },
  foreignCallPutBalance: { type: Number, default: 0 },
  formatSigned: { type: Function, required: true },
});
</script>
