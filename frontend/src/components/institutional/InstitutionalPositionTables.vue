<template>
  <div>
    <div class="institutional-section">
      <div class="institutional-section-head">
        <div class="ind-group-title">期貨法人籌碼</div>
        <div class="institutional-section-note">依未平倉淨口數排序，右側顯示與前一交易日差異</div>
      </div>
      <div class="institutional-table-wrap">
        <table class="institutional-table">
          <thead>
            <tr>
              <th>商品</th>
              <th>法人</th>
              <th>交易淨口數</th>
              <th>未平倉淨口數</th>
              <th>未平倉淨變化</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredFutures" :key="`f-${row.commodity}-${row.institution}`">
              <td>{{ row.commodity }}</td>
              <td>{{ row.institution }}</td>
              <td :class="row.trade_net_volume >= 0 ? 'up' : 'dn'">{{ formatSigned(row.trade_net_volume) }}</td>
              <td :class="row.oi_net_volume >= 0 ? 'up' : 'dn'">{{ formatSigned(row.oi_net_volume) }}</td>
              <td :class="row.oi_net_volume_change >= 0 ? 'up' : 'dn'">{{ formatSigned(row.oi_net_volume_change) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="institutional-section">
      <div class="institutional-section-head">
        <div class="ind-group-title">選擇權法人籌碼</div>
        <div class="institutional-section-note">觀察各契約交易與未平倉淨口數</div>
      </div>
      <div class="institutional-table-wrap">
        <table class="institutional-table">
          <thead>
            <tr>
              <th>商品</th>
              <th>法人</th>
              <th>交易淨口數</th>
              <th>未平倉淨口數</th>
              <th>未平倉淨變化</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredOptions" :key="`o-${row.commodity}-${row.institution}`">
              <td>{{ row.commodity }}</td>
              <td>{{ row.institution }}</td>
              <td :class="row.trade_net_volume >= 0 ? 'up' : 'dn'">{{ formatSigned(row.trade_net_volume) }}</td>
              <td :class="row.oi_net_volume >= 0 ? 'up' : 'dn'">{{ formatSigned(row.oi_net_volume) }}</td>
              <td :class="row.oi_net_volume_change >= 0 ? 'up' : 'dn'">{{ formatSigned(row.oi_net_volume_change) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="institutional-section">
      <div class="institutional-section-head">
        <div class="ind-group-title">選擇權買賣權分計</div>
        <div class="institutional-section-note">買權 / 賣權拆開看，更容易判斷偏多偏空部位</div>
      </div>
      <div class="institutional-table-wrap">
        <table class="institutional-table">
          <thead>
            <tr>
              <th>商品</th>
              <th>權別</th>
              <th>法人</th>
              <th>交易買賣差</th>
              <th>未平倉買賣差</th>
              <th>未平倉差變化</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredCallPuts" :key="`cp-${row.commodity}-${row.option_side}-${row.institution}`">
              <td>{{ row.commodity }}</td>
              <td>{{ row.option_side }}</td>
              <td>{{ row.institution }}</td>
              <td :class="row.trade_net_volume >= 0 ? 'up' : 'dn'">{{ formatSigned(row.trade_net_volume) }}</td>
              <td :class="row.oi_net_volume >= 0 ? 'up' : 'dn'">{{ formatSigned(row.oi_net_volume) }}</td>
              <td :class="row.oi_net_volume_change >= 0 ? 'up' : 'dn'">{{ formatSigned(row.oi_net_volume_change) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  filteredFutures: { type: Array, default: () => [] },
  filteredOptions: { type: Array, default: () => [] },
  filteredCallPuts: { type: Array, default: () => [] },
  formatSigned: { type: Function, required: true },
});
</script>
