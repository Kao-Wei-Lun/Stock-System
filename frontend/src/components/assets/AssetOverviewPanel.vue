<template>
  <div class="asset-overview">
    <div v-if="assetWarnings.length || assetQuoteGaps.length || assetAlerts.length || reconciliationGapItems.length" class="asset-warning-stack">
      <div v-for="warning in assetWarnings" :key="warning" class="asset-warning-card">
        {{ warning }}
      </div>
      <div v-for="gap in assetQuoteGaps" :key="`${gap.account_id}-${gap.ticker}`" class="asset-warning-card">
        {{ gap.ticker }} 暫時抓不到最新報價，目前未納入估值；可到資料維護補手動價格覆蓋。
      </div>
      <div v-for="item in reconciliationGapItems" :key="`reco-${item.account_id}-${item.snapshot_id}`" class="asset-warning-card">
        {{ item.account_name }} 對帳差異 {{ formatSignedCurrency(item.total_difference, assetBaseCurrency) }}
      </div>
      <div
        v-for="alert in assetAlerts"
        :key="`${alert.code}-${alert.title}`"
        class="asset-warning-card"
        :class="alert.level === 'info' ? 'info' : 'warning'"
      >
        <strong>{{ alert.title }}</strong>
        <span>{{ alert.message }}</span>
      </div>
    </div>

    <div class="asset-range-row">
      <button
        v-for="item in performanceRangeOptions"
        :key="item.value"
        class="asset-range-btn"
        :class="{ active: assetPerformanceRange === item.value }"
        type="button"
        @click="$emit('set-asset-performance-range', item.value)"
      >
        {{ item.label }}
      </button>
    </div>

    <div class="asset-summary-grid">
      <article v-for="card in summaryCards" :key="card.key" class="asset-summary-card">
        <span>{{ card.label }}</span>
        <strong :class="card.tone">{{ card.value }}</strong>
      </article>
    </div>

    <section class="asset-card asset-card-wide">
      <div class="asset-card-head">
        <div>
          <div class="asset-card-title">績效概覽</div>
          <div class="bt-trade-sub">
            {{ assetPerformanceSeries.length }} 個觀察點 · 最新日期 {{ assetPerformanceSummary.latest_snapshot_date || "—" }}
          </div>
        </div>
        <div class="asset-list-metrics">
          <span>{{ formatSignedCurrency(assetPerformanceSummary.true_performance_base, assetBaseCurrency) }}</span>
          <small>真實績效</small>
        </div>
      </div>
      <div class="asset-performance-grid">
        <div class="asset-curve-card">
          <div class="asset-curve-metrics">
            <div class="asset-mini-block">
              <span>區間起點</span>
              <strong>{{ formatCurrency(assetPerformanceSummary.start_value_base) }}</strong>
            </div>
            <div class="asset-mini-block">
              <span>區間終點</span>
              <strong>{{ formatCurrency(assetPerformanceSummary.end_value_base) }}</strong>
            </div>
            <div class="asset-mini-block">
              <span>期間淨流入</span>
              <strong>{{ formatSignedCurrency(assetPerformanceSummary.net_flow_base, assetBaseCurrency) }}</strong>
            </div>
          </div>
          <div class="asset-sparkline-shell">
            <svg viewBox="0 0 320 120" class="asset-sparkline">
              <path v-if="performanceSparklinePath" :d="performanceSparklinePath" class="asset-sparkline-line" />
            </svg>
          </div>
        </div>
        <div class="asset-side-analytics">
          <div class="asset-mini-block">
            <span>已實現 / 未實現</span>
            <strong>{{ realizedVsUnrealizedLabel }}</strong>
          </div>
          <div class="asset-mini-block">
            <span>高水位</span>
            <strong>{{ formatCurrency(assetPerformanceSummary.high_water_mark_base) }}</strong>
          </div>
          <div class="asset-mini-block">
            <span>最大回撤</span>
            <strong :class="Number(assetPerformanceSummary.max_drawdown_pct || 0) >= 0 ? 'neutral' : 'dn'">
              {{ formatPercent(assetPerformanceSummary.max_drawdown_pct) }}
            </strong>
          </div>
          <div class="asset-mini-block">
            <span>提醒數</span>
            <strong>{{ assetAlerts.length }}</strong>
          </div>
        </div>
      </div>

      <div class="asset-subsection">
        <div class="asset-card-head">
          <div class="asset-card-title">月度熱力圖</div>
          <div class="bt-trade-sub">依期間真實績效計算</div>
        </div>
        <div v-if="assetMonthlyHeatmap.length" class="asset-heatmap-grid">
          <div
            v-for="item in assetMonthlyHeatmap"
            :key="item.month"
            class="asset-heatmap-cell"
            :class="heatmapTone(item.return_pct)"
          >
            <strong>{{ item.month }}</strong>
            <span>{{ formatPercent(item.return_pct) }}</span>
          </div>
        </div>
        <div v-else class="bt-history-empty">目前沒有足夠的歷史資料可繪製熱力圖。</div>
      </div>
    </section>

    <div class="asset-analytics-grid">
      <section class="asset-card">
        <div class="asset-card-title">帳戶配置</div>
        <div v-if="assetAccountAllocation.length" class="asset-list">
          <div v-for="item in assetAccountAllocation" :key="item.key" class="asset-list-item static">
            <div>
              <strong>{{ item.key }}</strong>
              <div class="bt-trade-sub">{{ formatCurrency(item.value_base) }}</div>
            </div>
            <div class="asset-list-metrics">
              <span>{{ formatPercent(item.weight_pct) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="bt-history-empty">尚無配置資料。</div>
      </section>

      <section class="asset-card">
        <div class="asset-card-title">市場配置</div>
        <div v-if="assetMarketAllocation.length" class="asset-list">
          <div v-for="item in assetMarketAllocation" :key="item.key" class="asset-list-item static">
            <div>
              <strong>{{ item.key }}</strong>
              <div class="bt-trade-sub">{{ formatCurrency(item.value_base) }}</div>
            </div>
            <div class="asset-list-metrics">
              <span>{{ formatPercent(item.weight_pct) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="bt-history-empty">目前沒有持股市值。</div>
      </section>

      <section class="asset-card">
        <div class="asset-card-title">損益貢獻</div>
        <div class="asset-mini-block">
          <span>Top Gainer</span>
          <strong>{{ contributorLabel(assetContributors.top_gainers?.[0]) }}</strong>
        </div>
        <div class="asset-mini-block">
          <span>Top Loser</span>
          <strong>{{ contributorLabel(assetContributors.top_losers?.[0]) }}</strong>
        </div>
        <div class="asset-mini-block">
          <span>估值幣別</span>
          <strong>{{ assetBaseCurrency }}</strong>
        </div>
      </section>
    </div>

    <div class="asset-preview-grid">
      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">持倉預覽</div>
          <button class="asset-inline-btn" type="button" @click="$emit('open-tab', 'holdings')">查看全部</button>
        </div>
        <div v-if="assetHoldings.length" class="asset-list">
          <div v-for="holding in assetHoldings.slice(0, 5)" :key="`${holding.account_id}-${holding.ticker}`" class="asset-list-item static">
            <div>
              <strong>{{ holding.ticker }}</strong>
              <div class="bt-trade-sub">{{ holding.account_name }}</div>
            </div>
            <div class="asset-list-metrics">
              <span>{{ formatCurrency(holding.market_value_base) }}</span>
              <small :class="Number(holding.unrealized_pnl_base || 0) >= 0 ? 'up' : 'dn'">
                {{ formatSignedCurrency(holding.unrealized_pnl_base, assetBaseCurrency) }}
              </small>
            </div>
          </div>
        </div>
        <div v-else class="bt-history-empty">尚無持倉。</div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">最近流水</div>
          <button class="asset-inline-btn" type="button" @click="$emit('open-tab', 'holdings')">查看明細</button>
        </div>
        <div v-if="recentFlowItems.length" class="asset-list">
          <div v-for="item in recentFlowItems" :key="item.key" class="asset-list-item static">
            <div>
              <strong>{{ item.title }}</strong>
              <div class="bt-trade-sub">{{ item.meta }}</div>
            </div>
            <div class="asset-list-metrics">
              <span>{{ item.value }}</span>
              <small>{{ item.kind }}</small>
            </div>
          </div>
        </div>
        <div v-else class="bt-history-empty">目前沒有最近流水。</div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  assetPerformanceRange: { type: String, default: "1y" },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetWarnings: { type: Array, default: () => [] },
  assetQuoteGaps: { type: Array, default: () => [] },
  assetReconciliation: { type: Object, default: () => ({ items: [], summary: {} }) },
  assetPerformanceSummary: { type: Object, default: () => ({}) },
  assetPerformanceSeries: { type: Array, default: () => [] },
  assetMonthlyHeatmap: { type: Array, default: () => [] },
  assetAlerts: { type: Array, default: () => [] },
  assetAccountAllocation: { type: Array, default: () => [] },
  assetMarketAllocation: { type: Array, default: () => [] },
  assetContributors: { type: Object, default: () => ({ top_gainers: [], top_losers: [] }) },
  assetHoldings: { type: Array, default: () => [] },
  assetCashEntries: { type: Array, default: () => [] },
  assetTradeEntries: { type: Array, default: () => [] },
});

defineEmits([
  "set-asset-performance-range",
  "open-tab",
]);

const performanceRangeOptions = [
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "1y", label: "1Y" },
  { value: "all", label: "All" },
];

const reconciliationItems = computed(() => props.assetReconciliation?.items || []);
const reconciliationGapItems = computed(() => reconciliationItems.value.filter((item) => item?.has_gap));

const summaryCards = computed(() => [
  { key: "total", label: "總資產現值", value: formatCurrency(props.assetSummary.total_asset_value_base), tone: "neutral" },
  { key: "true", label: "區間真實績效", value: formatSignedCurrency(props.assetPerformanceSummary.true_performance_base, props.assetBaseCurrency), tone: Number(props.assetPerformanceSummary.true_performance_base || 0) >= 0 ? "up" : "dn" },
  { key: "return", label: "區間報酬率", value: formatPercent(props.assetPerformanceSummary.true_return_pct), tone: Number(props.assetPerformanceSummary.true_return_pct || 0) >= 0 ? "up" : "dn" },
  { key: "drawdown", label: "最大回撤", value: formatPercent(props.assetPerformanceSummary.max_drawdown_pct), tone: Number(props.assetPerformanceSummary.max_drawdown_pct || 0) >= 0 ? "neutral" : "dn" },
  { key: "cash", label: "現金總額", value: formatCurrency(props.assetSummary.cash_total_base), tone: "neutral" },
  { key: "market", label: "持倉市值", value: formatCurrency(props.assetSummary.market_value_total_base), tone: "neutral" },
  { key: "unrealized", label: "未實現損益", value: formatSignedCurrency(props.assetSummary.unrealized_total_base, props.assetBaseCurrency), tone: Number(props.assetSummary.unrealized_total_base || 0) >= 0 ? "up" : "dn" },
  { key: "realized", label: "已實現損益", value: formatSignedCurrency(props.assetSummary.realized_total_base, props.assetBaseCurrency), tone: Number(props.assetSummary.realized_total_base || 0) >= 0 ? "up" : "dn" },
]);

const performanceSparklinePath = computed(() => {
  const points = props.assetPerformanceSeries || [];
  if (points.length < 2) return "";
  const values = points
    .map((item) => Number(item?.total_asset_value_base ?? 0))
    .filter((value) => Number.isFinite(value));
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 320;
  const height = 120;
  const xStep = width / Math.max(values.length - 1, 1);
  return values.map((value, index) => {
    const x = Number((index * xStep).toFixed(2));
    const ratio = max === min ? 0.5 : (value - min) / (max - min);
    const y = Number((height - ratio * (height - 20) - 10).toFixed(2));
    return `${index === 0 ? "M" : "L"}${x} ${y}`;
  }).join(" ");
});

const realizedVsUnrealizedLabel = computed(() => {
  const realized = formatSignedCurrency(props.assetPerformanceSummary.realized_end_base, props.assetBaseCurrency);
  const unrealized = formatSignedCurrency(props.assetPerformanceSummary.unrealized_end_base, props.assetBaseCurrency);
  return `${realized} / ${unrealized}`;
});

const recentFlowItems = computed(() => {
  const trades = (props.assetTradeEntries || []).slice(0, 3).map((entry) => ({
    key: `trade-${entry.id}`,
    title: `${entry.ticker} · ${entry.side}`,
    meta: `${entry.account_name || entry.account_id || "帳戶"} · ${formatDateTime(entry.trade_date)}`,
    value: `${formatNumber(entry.quantity, 4)} @ ${formatNumber(entry.price, 2)}`,
    kind: "交易",
    timestamp: new Date(entry.trade_date || 0).getTime(),
  }));
  const cash = (props.assetCashEntries || []).slice(0, 3).map((entry) => ({
    key: `cash-${entry.id}`,
    title: flowTypeLabel(entry.flow_type),
    meta: `${entry.account_name || entry.account_id || "帳戶"} · ${formatDateTime(entry.flow_date)}`,
    value: formatSignedCurrency(entry.amount, entry.currency, entry.flow_type),
    kind: "現金",
    timestamp: new Date(entry.flow_date || 0).getTime(),
  }));
  return [...trades, ...cash]
    .sort((left, right) => right.timestamp - left.timestamp)
    .slice(0, 5);
});

function formatNumber(value, digits = 2) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return numeric.toLocaleString("zh-TW", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function formatCurrency(value, currency = props.assetBaseCurrency) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${currency} ${numeric.toLocaleString("zh-TW", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function formatSignedCurrency(value, currency = props.assetBaseCurrency, flowType = "") {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  const sign = flowType
    ? (["withdraw", "fee", "tax", "fx_fee", "transfer_out"].includes(String(flowType)) ? "-" : "+")
    : (numeric >= 0 ? "+" : "-");
  return `${sign}${currency} ${Math.abs(numeric).toLocaleString("zh-TW", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

function formatPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${numeric.toFixed(2)}%`;
}

function formatDateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("zh-TW", { hour12: false });
}

function flowTypeLabel(value) {
  return ({
    deposit: "入金",
    withdraw: "出金",
    transfer_in: "轉入",
    transfer_out: "轉出",
    dividend: "股利",
    fee: "手續費",
    tax: "稅費",
    fx_fee: "匯費",
    interest: "利息",
  }[String(value || "")] || String(value || "事件"));
}

function contributorLabel(item) {
  if (!item?.ticker) return "—";
  return `${item.ticker} ${formatSignedCurrency(item.unrealized_pnl_base, props.assetBaseCurrency)}`;
}

function heatmapTone(value) {
  const numeric = Number(value || 0);
  if (numeric >= 8) return "strong-up";
  if (numeric > 0) return "up";
  if (numeric <= -8) return "strong-dn";
  if (numeric < 0) return "dn";
  return "";
}
</script>

<style scoped>
.asset-overview {
  padding: 18px;
}

.asset-preview-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

@media (max-width: 960px) {
  .asset-preview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
