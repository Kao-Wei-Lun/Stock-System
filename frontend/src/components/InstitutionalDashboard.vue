<template>
  <div class="institutional-shell">
    <div class="institutional-toolbar">
      <div>
        <div class="institutional-title">TAIFEX 三大法人籌碼</div>
        <div class="institutional-subtitle">
          期貨、選擇權、現貨與成本推估整合檢視
        </div>
      </div>
      <div class="institutional-toolbar-actions">
        <button class="tool-btn" @click="$emit('shift-date', -1)">← 前一日</button>
        <input
          class="workspace-select institutional-date-input"
          type="date"
          :value="selectedDate"
          @change="$emit('set-date', $event.target.value)"
        >
        <button class="tool-btn" @click="$emit('shift-date', 1)">後一日 →</button>
        <button class="tool-btn active" :disabled="loading" @click="$emit('refresh-dashboard')">
          {{ loading ? "載入中..." : "重新整理" }}
        </button>
      </div>
    </div>

    <div class="chart-meta institutional-meta">
      <div class="meta-chip">查詢日 {{ selectedDate || "—" }}</div>
      <div class="meta-chip">實際資料日 {{ data?.resolved_date || "—" }}</div>
      <div class="meta-chip">對比日 {{ data?.previous_date || "—" }}</div>
      <div class="meta-chip">歷史區間 {{ historyDaysLabel }}</div>
      <div class="meta-chip is-hint">資料來源：TAIFEX 三大法人依日期查詢、TWSE 三大法人現貨買賣超摘要</div>
    </div>

    <div v-if="loading" class="institutional-loading">
      <div class="spinner"></div>
      <p>正在載入法人籌碼資料...</p>
    </div>
    <div v-else-if="error" class="institutional-error">{{ error }}</div>
    <template v-else-if="data">
      <div class="institutional-grid">
        <div class="institutional-card">
          <div class="ind-group-title">現貨參考</div>
          <div class="institutional-kpis">
            <div v-for="item in data.spot_reference || []" :key="item.ticker" class="inst-kpi">
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
            <div v-for="row in data.overview || []" :key="row.institution" class="inst-row wide">
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

      <div class="institutional-filters">
        <select class="workspace-select" :value="selectedFuturesCommodity" @change="$emit('set-futures-commodity', $event.target.value)">
          <option v-for="name in data.futures_commodities || []" :key="name" :value="name">{{ name }}</option>
        </select>
        <select class="workspace-select" :value="selectedOptionsCommodity" @change="$emit('set-options-commodity', $event.target.value)">
          <option v-for="name in data.options_commodities || []" :key="name" :value="name">{{ name }}</option>
        </select>
        <select class="workspace-select institutional-range-select" :value="historyDays" @change="$emit('set-history-days', Number($event.target.value))">
          <option v-for="value in [10, 20, 30, 60, 90]" :key="value" :value="value">{{ value }} 日趨勢</option>
        </select>
        <button class="tool-btn" :disabled="insightsLoading" @click="$emit('refresh-insights')">
          {{ insightsLoading ? "整理趨勢中..." : "刷新趨勢" }}
        </button>
        <select class="workspace-select" v-model="institutionFilter">
          <option value="">全部法人</option>
          <option v-for="name in institutionOptions" :key="name" :value="name">{{ name }}</option>
        </select>
        <input v-model.trim="keyword" class="compare-input" placeholder="搜尋商品名稱，例如 臺股期貨 / 臺指選擇權">
      </div>

      <div v-if="insightsError" class="institutional-inline-error">{{ insightsError }}</div>
      <div v-else-if="insightsLoading" class="institutional-inline-loading">正在彙整法人歷史趨勢與成本推估...</div>

      <template v-if="insights">
        <div class="institutional-section">
          <div class="institutional-section-head">
            <div class="ind-group-title">法人籌碼歷史趨勢</div>
            <div class="institutional-section-note">期貨淨口數、選擇權買賣權失衡、現貨買賣超與未平倉成本帶</div>
          </div>
          <div class="institutional-trend-grid">
            <InstitutionalTrendChart
              title="期貨未平倉淨口數"
              :subtitle="selectedFuturesCommodity"
              :points="insights.history?.futures_oi || []"
              :series="trendSeries"
            />
            <InstitutionalTrendChart
              title="期貨交易淨口數"
              :subtitle="selectedFuturesCommodity"
              :points="insights.history?.futures_trade || []"
              :series="trendSeries"
            />
            <InstitutionalTrendChart
              title="選擇權未平倉淨口數"
              :subtitle="selectedOptionsCommodity"
              :points="insights.history?.options_oi || []"
              :series="trendSeries"
            />
            <InstitutionalTrendChart
              title="買權 / 賣權 OI 失衡"
              :subtitle="selectedOptionsCommodity"
              :points="insights.history?.call_put_balance || []"
              :series="trendSeries"
            />
            <InstitutionalTrendChart
              title="現貨三大法人買賣超"
              subtitle="TWSE 現貨市場"
              :points="insights.history?.cash_net || []"
              :series="trendSeries"
              value-format="amount"
            />
            <InstitutionalTrendChart
              title="未平倉成本帶"
              :subtitle="selectedFuturesCommodity"
              :points="insights.history?.cost_band || []"
              :series="costSeries"
              band-min-key="成本帶低"
              band-max-key="成本帶高"
              value-format="price"
            />
          </div>
        </div>

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

        <div class="institutional-section">
          <div class="institutional-section-head">
            <div class="ind-group-title">未平倉成本帶與成本推估</div>
            <div class="institutional-section-note">依契約價值反推三大法人長短倉平均持倉成本，並估計非三大法人對手方成本</div>
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
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import InstitutionalTrendChart from "./InstitutionalTrendChart.vue";
import { fmtPrice } from "../utils/formatters";

const props = defineProps({
  data: { type: Object, default: null },
  insights: { type: Object, default: null },
  loading: { type: Boolean, required: true },
  error: { type: String, default: "" },
  insightsLoading: { type: Boolean, default: false },
  insightsError: { type: String, default: "" },
  selectedDate: { type: String, required: true },
  selectedFuturesCommodity: { type: String, default: "" },
  selectedOptionsCommodity: { type: String, default: "" },
  historyDays: { type: Number, default: 30 },
});

defineEmits([
  "set-date",
  "shift-date",
  "refresh-dashboard",
  "refresh-insights",
  "set-futures-commodity",
  "set-options-commodity",
  "set-history-days",
]);

const institutionFilter = ref("");
const keyword = ref("");

const trendSeries = [
  { key: "外資", label: "外資", color: "#00d9a3" },
  { key: "投信", label: "投信", color: "#ffd166" },
  { key: "自營商", label: "自營商", color: "#3b8bff" },
  { key: "合計", label: "合計", color: "#9b6dff" },
];

const costSeries = [
  { key: "法人合成", label: "法人合成", color: "#00d9a3" },
  { key: "散戶推估", label: "散戶推估", color: "#ffd166" },
];

function matchesFilters(row) {
  const text = `${row.commodity || ""} ${row.institution || ""} ${row.option_side || ""}`.toUpperCase();
  const keywordValue = keyword.value.trim().toUpperCase();
  if (institutionFilter.value && row.institution !== institutionFilter.value) return false;
  if (keywordValue && !text.includes(keywordValue)) return false;
  return true;
}

function sortByAbsOi(rows) {
  return [...rows].sort((a, b) => Math.abs(Number(b.oi_net_volume || 0)) - Math.abs(Number(a.oi_net_volume || 0)));
}

function formatSigned(value, compact = false) {
  const numeric = Number(value || 0);
  if (!numeric) return compact ? "0" : "±0";
  const formatted = Math.abs(numeric).toLocaleString();
  return `${numeric > 0 ? "+" : "-"}${formatted}`;
}

const aggregatedCashSummary = computed(() => props.data?.cash_summary_aggregated || []);

const institutionOptions = computed(() => {
  const source = [
    ...(props.data?.overview || []).map((row) => row.institution),
    ...(props.data?.futures || []).map((row) => row.institution),
    ...(props.data?.options || []).map((row) => row.institution),
  ];
  return [...new Set(source.filter(Boolean))];
});

const filteredFutures = computed(() => sortByAbsOi((props.data?.futures || []).filter(matchesFilters)));
const filteredOptions = computed(() => sortByAbsOi((props.data?.options || []).filter(matchesFilters)));
const filteredCallPuts = computed(() => sortByAbsOi((props.data?.call_puts || []).filter(matchesFilters)));
const topLongRank = computed(() => (props.insights?.leaderboards?.futures_long || props.data?.leaderboards?.futures_long || []).slice(0, 6));
const topShortRank = computed(() => (props.insights?.leaderboards?.futures_short || props.data?.leaderboards?.futures_short || []).slice(0, 6));
const topTradeLongRank = computed(() => (props.insights?.leaderboards?.futures_trade_long || props.data?.leaderboards?.futures_trade_long || []).slice(0, 6));
const topTradeShortRank = computed(() => (props.insights?.leaderboards?.futures_trade_short || props.data?.leaderboards?.futures_trade_short || []).slice(0, 6));
const futuresCostEstimate = computed(() => props.insights?.cost_estimates?.futures || props.data?.cost_estimates?.futures || {});
const optionsCostEstimate = computed(() => props.insights?.cost_estimates?.options || props.data?.cost_estimates?.options || {});
const historyDaysLabel = computed(() => `${props.historyDays || 30} 日`);

const foreignCallPutBalance = computed(() => {
  const row = (optionsCostEstimate.value?.institutions || []).find((item) => item.institution === "外資");
  return Number(row?.balance || 0);
});
</script>
