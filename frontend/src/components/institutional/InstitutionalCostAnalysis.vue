<template>
  <div class="institutional-section">
    <div class="institutional-section-head">
      <div class="ind-group-title">未平倉成本帶與成本推估</div>
      <div class="institutional-section-note">依契約價值反推三大法人長短倉平均持倉成本，並估算非三大法人對手方成本</div>
    </div>

    <div class="institutional-kpi-strip">
      <div class="inst-kpi">
        <div class="inst-kpi-label">法人合成成本</div>
        <div class="inst-kpi-value">{{ fmtPrice(futuresCostEstimate?.institution_estimate?.price) }}</div>
        <div class="inst-kpi-change">{{ futuresCostEstimate?.institution_estimate?.side || "—" }}</div>
      </div>
      <div class="inst-kpi">
        <div class="inst-kpi-label">散戶 / 非三大法人推估</div>
        <div class="inst-kpi-value">{{ fmtPrice(futuresCostEstimate?.retail_estimate?.price) }}</div>
        <div class="inst-kpi-change">{{ futuresCostEstimate?.retail_estimate?.side || "—" }}</div>
      </div>
      <div class="inst-kpi">
        <div class="inst-kpi-label">成本帶下緣</div>
        <div class="inst-kpi-value">{{ fmtPrice(futuresCostEstimate?.band_low) }}</div>
        <div class="inst-kpi-change">Low</div>
      </div>
      <div class="inst-kpi">
        <div class="inst-kpi-label">成本帶上緣</div>
        <div class="inst-kpi-value">{{ fmtPrice(futuresCostEstimate?.band_high) }}</div>
        <div class="inst-kpi-change">High</div>
      </div>
    </div>

    <div class="institutional-ranking-grid">
      <div class="institutional-table-wrap">
        <table class="institutional-table">
          <thead>
            <tr>
              <th>法人</th>
              <th>淨未平倉</th>
              <th>偏向</th>
              <th>多方均價</th>
              <th>空方均價</th>
              <th>主成本</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in futuresCostEstimate?.institutions || []" :key="`cost-${row.institution}`">
              <td>{{ row.institution }}</td>
              <td :class="row.net_volume >= 0 ? 'up' : 'dn'">{{ formatSigned(row.net_volume) }}</td>
              <td>{{ row.dominant_side }}</td>
              <td>{{ fmtPrice(row.avg_long_price) }}</td>
              <td>{{ fmtPrice(row.avg_short_price) }}</td>
              <td>{{ fmtPrice(row.dominant_price) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="institutional-table-wrap">
        <table class="institutional-table">
          <thead>
            <tr>
              <th>法人</th>
              <th>買權 OI</th>
              <th>賣權 OI</th>
              <th>Call / Put 差</th>
              <th>買權均價</th>
              <th>賣權均價</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in optionsCostEstimate?.institutions || []" :key="`opt-cost-${row.institution}`">
              <td>{{ row.institution }}</td>
              <td :class="row.call_oi_net >= 0 ? 'up' : 'dn'">{{ formatSigned(row.call_oi_net) }}</td>
              <td :class="row.put_oi_net >= 0 ? 'up' : 'dn'">{{ formatSigned(row.put_oi_net) }}</td>
              <td :class="row.balance >= 0 ? 'up' : 'dn'">{{ formatSigned(row.balance) }}</td>
              <td>{{ fmtPrice(row.call_avg_buy) }}</td>
              <td>{{ fmtPrice(row.put_avg_buy) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { fmtPrice } from "../../utils/formatters";

defineProps({
  futuresCostEstimate: { type: Object, default: () => ({}) },
  optionsCostEstimate: { type: Object, default: () => ({}) },
  formatSigned: { type: Function, required: true },
});
</script>
