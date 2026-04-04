<template>
  <div class="institutional-section">
    <div class="institutional-section-head">
      <div class="ind-group-title">主力多空排行</div>
      <div class="institutional-section-note">依未平倉與交易淨口數排序，快速抓出最強多頭與空頭商品</div>
    </div>
    <div class="institutional-ranking-grid">
      <div class="institutional-card">
        <div class="ind-group-title">未平倉偏多排行</div>
        <div class="institutional-rows compact">
          <div v-for="row in topLongRank" :key="`long-${row.commodity}-${row.institution}`" class="inst-row wide">
            <div>
              <strong>{{ row.commodity }}</strong>
              <div class="inst-row-sub">{{ row.institution }}</div>
            </div>
            <div class="inst-row-metrics">
              <span class="up">{{ formatSigned(row.oi_net_volume) }}</span>
              <span :class="row.trade_net_volume >= 0 ? 'up' : 'dn'">交易 {{ formatSigned(row.trade_net_volume) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="institutional-card">
        <div class="ind-group-title">未平倉偏空排行</div>
        <div class="institutional-rows compact">
          <div v-for="row in topShortRank" :key="`short-${row.commodity}-${row.institution}`" class="inst-row wide">
            <div>
              <strong>{{ row.commodity }}</strong>
              <div class="inst-row-sub">{{ row.institution }}</div>
            </div>
            <div class="inst-row-metrics">
              <span class="dn">{{ formatSigned(row.oi_net_volume) }}</span>
              <span :class="row.trade_net_volume >= 0 ? 'up' : 'dn'">交易 {{ formatSigned(row.trade_net_volume) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="institutional-card">
        <div class="ind-group-title">當日偏多交易排行</div>
        <div class="institutional-rows compact">
          <div v-for="row in topTradeLongRank" :key="`trade-long-${row.commodity}-${row.institution}`" class="inst-row wide">
            <div>
              <strong>{{ row.commodity }}</strong>
              <div class="inst-row-sub">{{ row.institution }}</div>
            </div>
            <div class="inst-row-metrics">
              <span class="up">{{ formatSigned(row.trade_net_volume) }}</span>
              <span :class="row.oi_net_volume >= 0 ? 'up' : 'dn'">OI {{ formatSigned(row.oi_net_volume) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="institutional-card">
        <div class="ind-group-title">當日偏空交易排行</div>
        <div class="institutional-rows compact">
          <div v-for="row in topTradeShortRank" :key="`trade-short-${row.commodity}-${row.institution}`" class="inst-row wide">
            <div>
              <strong>{{ row.commodity }}</strong>
              <div class="inst-row-sub">{{ row.institution }}</div>
            </div>
            <div class="inst-row-metrics">
              <span class="dn">{{ formatSigned(row.trade_net_volume) }}</span>
              <span :class="row.oi_net_volume >= 0 ? 'up' : 'dn'">OI {{ formatSigned(row.oi_net_volume) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  topLongRank: { type: Array, default: () => [] },
  topShortRank: { type: Array, default: () => [] },
  topTradeLongRank: { type: Array, default: () => [] },
  topTradeShortRank: { type: Array, default: () => [] },
  formatSigned: { type: Function, required: true },
});
</script>
