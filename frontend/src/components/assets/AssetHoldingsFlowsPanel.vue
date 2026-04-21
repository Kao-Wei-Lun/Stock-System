<template>
  <div class="asset-holdings-pane">
    <div class="asset-holdings-head">
      <div>
        <div class="asset-card-title">持倉與流水</div>
        <div class="bt-trade-sub">把帳戶摘要、目前持倉與最近交易集中在同一頁查詢。</div>
      </div>
      <div class="asset-holdings-head-actions">
        <button v-if="hasActiveFilter" class="asset-inline-btn" type="button" @click="$emit('clear-filter')">
          清除篩選
        </button>
        <button class="asset-inline-btn" type="button" @click="$emit('open-tab', 'maintenance')">
          前往資料維護
        </button>
      </div>
    </div>

    <div v-if="hasActiveFilter" class="asset-filter-bar">
      <div class="asset-filter-copy">目前是從總覽帶入的 drilldown 篩選：</div>
      <div class="asset-filter-chip-row">
        <span v-for="chip in filterChips" :key="chip.key" class="asset-filter-chip">{{ chip.label }}</span>
      </div>
    </div>

    <div class="asset-preview-grid">
      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">帳戶摘要</div>
          <div class="bt-trade-sub">{{ filteredAccountsSummary.length }} 個帳戶</div>
        </div>
        <div v-if="filteredAccountsSummary.length" class="asset-list">
          <div v-for="account in filteredAccountsSummary" :key="account.account_id" class="asset-list-item static">
            <div>
              <strong>{{ account.account_name }}</strong>
              <div class="bt-trade-sub">{{ account.account_type || "account" }} · {{ account.base_currency }}</div>
            </div>
            <div class="asset-list-metrics">
              <span>{{ formatCurrency(account.cash_total_base) }}</span>
              <small>{{ account.include_in_total ? "列入總額" : "僅供追蹤" }}</small>
            </div>
          </div>
        </div>
        <div v-else class="bt-history-empty">目前篩選條件下沒有帳戶摘要。</div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">最近現金事件</div>
          <div class="bt-trade-sub">{{ filteredCashEntries.length }} 筆</div>
        </div>
        <div v-if="filteredCashEntries.length" class="asset-list">
          <div v-for="entry in filteredCashEntries.slice(0, 8)" :key="entry.id" class="asset-list-item static">
            <div>
              <strong>{{ flowTypeLabel(entry.flow_type) }}</strong>
              <div class="bt-trade-sub">{{ resolveAccountName(entry.account_id) }} · {{ formatDateTime(entry.flow_date) }}</div>
            </div>
            <div class="asset-list-metrics">
              <span :class="cashTone(entry.flow_type)">{{ formatSignedCurrency(entry.amount, entry.currency, entry.flow_type) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="bt-history-empty">目前篩選條件下沒有現金事件。</div>
      </section>
    </div>

    <section class="asset-card asset-card-wide">
      <div class="asset-card-head">
        <div class="asset-card-title">目前持倉</div>
        <div class="bt-trade-sub">{{ filteredHoldings.length }} 檔 · 依市值排序</div>
      </div>
      <div v-if="filteredHoldings.length" class="asset-holdings-detail-layout">
        <div class="asset-table-wrap">
          <table class="asset-table">
            <thead>
              <tr>
                <th>標的</th>
                <th>帳戶</th>
                <th>市場</th>
                <th>數量</th>
                <th>均價</th>
                <th>最新價</th>
                <th>市值</th>
                <th>未實現</th>
                <th>已實現</th>
                <th>權重</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="holding in filteredHoldings"
                :key="holdingKey(holding)"
                class="asset-holding-row"
                :class="{ 'is-active': selectedHoldingKey === holdingKey(holding) }"
                @click="selectHolding(holding)"
              >
                <td>
                  <div class="asset-table-main">
                    <strong>{{ holding.ticker }}</strong>
                    <small>{{ holding.display_name || holding.ticker }}</small>
                  </div>
                </td>
                <td>{{ holding.account_name }}</td>
                <td>{{ holding.market || "—" }}</td>
                <td>{{ formatNumber(holding.quantity, 4) }}</td>
                <td>{{ formatNumber(holding.avg_cost, 2) }}</td>
                <td>
                  <span>{{ holding.last_price == null ? "—" : formatNumber(holding.last_price, 2) }}</span>
                  <small v-if="holding.is_delayed" class="asset-badge delayed">Delayed</small>
                  <small v-if="holding.manual_price_override_id" class="asset-badge manual">Manual</small>
                </td>
                <td>{{ formatCurrency(holding.market_value_base) }}</td>
                <td :class="Number(holding.unrealized_pnl_base || 0) >= 0 ? 'up' : 'dn'">{{ formatSignedCurrency(holding.unrealized_pnl_base, assetBaseCurrency) }}</td>
                <td :class="Number(holding.realized_pnl_base || 0) >= 0 ? 'up' : 'dn'">{{ formatSignedCurrency(holding.realized_pnl_base, assetBaseCurrency) }}</td>
                <td>{{ holdingWeight(holding) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <aside v-if="selectedHolding" class="asset-card asset-holding-drawer">
          <div class="asset-card-head">
            <div>
              <div class="asset-card-title">焦點持倉</div>
              <div class="bt-trade-sub">{{ selectedHolding.account_name }} · {{ selectedHolding.market || "—" }}</div>
            </div>
            <div class="asset-list-metrics">
              <span>{{ selectedHolding.ticker }}</span>
              <small>{{ selectedHolding.display_name || selectedHolding.ticker }}</small>
            </div>
          </div>
          <div class="asset-holding-drawer-grid">
            <div class="asset-mini-block">
              <span>數量</span>
              <strong>{{ formatNumber(selectedHolding.quantity, 4) }}</strong>
            </div>
            <div class="asset-mini-block">
              <span>平均成本</span>
              <strong>{{ formatNumber(selectedHolding.avg_cost, 2) }}</strong>
            </div>
            <div class="asset-mini-block">
              <span>最新市值</span>
              <strong>{{ formatCurrency(selectedHolding.market_value_base) }}</strong>
            </div>
            <div class="asset-mini-block">
              <span>未實現損益</span>
              <strong :class="Number(selectedHolding.unrealized_pnl_base || 0) >= 0 ? 'up' : 'dn'">
                {{ formatSignedCurrency(selectedHolding.unrealized_pnl_base, assetBaseCurrency) }}
              </strong>
            </div>
            <div class="asset-mini-block">
              <span>已實現損益</span>
              <strong :class="Number(selectedHolding.realized_pnl_base || 0) >= 0 ? 'up' : 'dn'">
                {{ formatSignedCurrency(selectedHolding.realized_pnl_base, assetBaseCurrency) }}
              </strong>
            </div>
            <div class="asset-mini-block">
              <span>最新價格</span>
              <strong>{{ selectedHolding.last_price == null ? "—" : formatNumber(selectedHolding.last_price, 2) }}</strong>
            </div>
          </div>
          <div class="asset-subsection">
            <div class="asset-card-head">
              <div class="asset-card-title">最近相關交易</div>
              <div class="bt-trade-sub">{{ selectedHoldingTrades.length }} 筆</div>
            </div>
            <div v-if="selectedHoldingTrades.length" class="asset-list">
              <div v-for="entry in selectedHoldingTrades.slice(0, 5)" :key="entry.id" class="asset-list-item static">
                <div>
                  <strong>{{ tradeSideLabel(entry.side) }}</strong>
                  <div class="bt-trade-sub">{{ formatDateTime(entry.trade_date) }}</div>
                </div>
                <div class="asset-list-metrics">
                  <span>{{ formatNumber(entry.quantity, 4) }} @ {{ formatNumber(entry.price, 2) }}</span>
                </div>
              </div>
            </div>
            <div v-else class="bt-history-empty">目前沒有這檔標的的交易記錄。</div>
          </div>
        </aside>
      </div>
      <div v-else class="bt-history-empty">目前篩選條件下沒有持倉。</div>
    </section>

    <section class="asset-card asset-card-wide">
      <div class="asset-card-head">
        <div class="asset-card-title">流水時間軸</div>
        <div class="bt-trade-sub">{{ flowTimelineItems.length }} 筆事件</div>
      </div>
      <div v-if="flowTimelineItems.length" class="asset-list">
        <div v-for="entry in flowTimelineItems" :key="entry.key" class="asset-list-item static">
          <div>
            <strong>{{ entry.title }}</strong>
            <div class="bt-trade-sub">{{ entry.meta }}</div>
          </div>
          <div class="asset-list-metrics">
            <span>{{ entry.value }}</span>
            <small>{{ entry.kind }}</small>
          </div>
        </div>
      </div>
      <div v-else class="bt-history-empty">目前篩選條件下沒有流水事件。</div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  assetBaseCurrency: { type: String, default: "TWD" },
  assetAccountsSummary: { type: Array, default: () => [] },
  assetHoldings: { type: Array, default: () => [] },
  assetCashEntries: { type: Array, default: () => [] },
  assetTradeEntries: { type: Array, default: () => [] },
  assetFilter: {
    type: Object,
    default: () => ({
      accountKey: "",
      marketKey: "",
      ticker: "",
      month: "",
    }),
  },
});

defineEmits(["open-tab", "clear-filter"]);

const normalizedFilter = computed(() => ({
  accountKey: String(props.assetFilter?.accountKey || "").trim(),
  marketKey: String(props.assetFilter?.marketKey || "").trim().toUpperCase(),
  ticker: String(props.assetFilter?.ticker || "").trim().toUpperCase(),
  month: String(props.assetFilter?.month || "").trim(),
}));

const hasActiveFilter = computed(() => Object.values(normalizedFilter.value).some(Boolean));

const filterChips = computed(() => {
  const chips = [];
  if (normalizedFilter.value.accountKey) chips.push({ key: "account", label: `帳戶：${normalizedFilter.value.accountKey}` });
  if (normalizedFilter.value.marketKey) chips.push({ key: "market", label: `市場：${normalizedFilter.value.marketKey}` });
  if (normalizedFilter.value.ticker) chips.push({ key: "ticker", label: `標的：${normalizedFilter.value.ticker}` });
  if (normalizedFilter.value.month) chips.push({ key: "month", label: `月份：${normalizedFilter.value.month}` });
  return chips;
});

const filteredAccountsSummary = computed(() => {
  if (!normalizedFilter.value.accountKey) return props.assetAccountsSummary || [];
  return (props.assetAccountsSummary || []).filter((item) => String(item.account_name || "").trim() === normalizedFilter.value.accountKey);
});

const filteredHoldings = computed(() => (
  (props.assetHoldings || []).filter((holding) => matchesHolding(holding))
));

const filteredCashEntries = computed(() => (
  (props.assetCashEntries || [])
    .filter((entry) => matchesCashEntry(entry))
    .sort((left, right) => new Date(right.flow_date || 0).getTime() - new Date(left.flow_date || 0).getTime())
));

const filteredTradeEntries = computed(() => (
  (props.assetTradeEntries || [])
    .filter((entry) => matchesTradeEntry(entry))
    .sort((left, right) => new Date(right.trade_date || 0).getTime() - new Date(left.trade_date || 0).getTime())
));

const totalHoldingsValue = computed(() => filteredHoldings.value.reduce((sum, item) => sum + Number(item?.market_value_base || 0), 0));
const selectedHoldingKey = ref("");

watch(
  filteredHoldings,
  (items) => {
    const nextKey = items[0] ? holdingKey(items[0]) : "";
    if (!items.some((item) => holdingKey(item) === selectedHoldingKey.value)) {
      selectedHoldingKey.value = nextKey;
    }
  },
  { immediate: true },
);

const selectedHolding = computed(() => filteredHoldings.value.find((item) => holdingKey(item) === selectedHoldingKey.value) || null);
const selectedHoldingTrades = computed(() => (
  filteredTradeEntries.value.filter((entry) => (
    selectedHolding.value
    && String(entry?.ticker || "").trim().toUpperCase() === String(selectedHolding.value?.ticker || "").trim().toUpperCase()
    && String(resolveAccountName(entry?.account_id)) === String(selectedHolding.value?.account_name || "")
  ))
));
const flowTimelineItems = computed(() => {
  const trades = filteredTradeEntries.value.map((entry) => ({
    key: `trade-${entry.id}`,
    title: `${entry.ticker} · ${tradeSideLabel(entry.side)}`,
    meta: `${resolveAccountName(entry.account_id)} · ${formatDateTime(entry.trade_date)}`,
    value: `${formatNumber(entry.quantity, 4)} @ ${formatNumber(entry.price, 2)}`,
    kind: `交易 · ${entry.market || "—"}`,
    timestamp: new Date(entry.trade_date || 0).getTime(),
  }));
  const cash = filteredCashEntries.value.map((entry) => ({
    key: `cash-${entry.id}`,
    title: flowTypeLabel(entry.flow_type),
    meta: `${resolveAccountName(entry.account_id)} · ${formatDateTime(entry.flow_date)}`,
    value: formatSignedCurrency(entry.amount, entry.currency, entry.flow_type),
    kind: "現金",
    timestamp: new Date(entry.flow_date || 0).getTime(),
  }));
  return [...trades, ...cash]
    .sort((left, right) => right.timestamp - left.timestamp)
    .slice(0, 20);
});

function matchesHolding(holding) {
  if (normalizedFilter.value.accountKey && String(holding?.account_name || "").trim() !== normalizedFilter.value.accountKey) {
    return false;
  }
  if (normalizedFilter.value.marketKey && String(holding?.market || "").trim().toUpperCase() !== normalizedFilter.value.marketKey) {
    return false;
  }
  if (normalizedFilter.value.ticker && String(holding?.ticker || "").trim().toUpperCase() !== normalizedFilter.value.ticker) {
    return false;
  }
  return true;
}

function matchesCashEntry(entry) {
  if (normalizedFilter.value.accountKey && resolveAccountName(entry?.account_id) !== normalizedFilter.value.accountKey) {
    return false;
  }
  if (normalizedFilter.value.month && extractMonth(entry?.flow_date) !== normalizedFilter.value.month) {
    return false;
  }
  return true;
}

function matchesTradeEntry(entry) {
  if (normalizedFilter.value.accountKey && resolveAccountName(entry?.account_id) !== normalizedFilter.value.accountKey) {
    return false;
  }
  if (normalizedFilter.value.marketKey && String(entry?.market || "").trim().toUpperCase() !== normalizedFilter.value.marketKey) {
    return false;
  }
  if (normalizedFilter.value.ticker && String(entry?.ticker || "").trim().toUpperCase() !== normalizedFilter.value.ticker) {
    return false;
  }
  if (normalizedFilter.value.month && extractMonth(entry?.trade_date) !== normalizedFilter.value.month) {
    return false;
  }
  return true;
}

function resolveAccountName(accountId) {
  return props.assetAccountsSummary.find((item) => String(item.account_id) === String(accountId))?.account_name || `帳戶 #${accountId}`;
}

function holdingKey(holding) {
  return `${holding?.account_id}-${holding?.ticker}`;
}

function selectHolding(holding) {
  selectedHoldingKey.value = holdingKey(holding);
}

function holdingWeight(holding) {
  const value = Number(holding?.market_value_base || 0);
  if (!totalHoldingsValue.value) return "—";
  return `${((value / totalHoldingsValue.value) * 100).toFixed(2)}%`;
}

function extractMonth(value) {
  return String(value || "").slice(0, 7);
}

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

function tradeSideLabel(value) {
  return String(value || "").toLowerCase() === "sell" ? "賣出" : "買進";
}

function cashTone(flowType) {
  return ["withdraw", "fee", "tax", "fx_fee", "transfer_out"].includes(String(flowType)) ? "dn" : "up";
}
</script>

<style scoped>
.asset-holdings-pane {
  padding: 18px;
}

.asset-holdings-head,
.asset-holdings-head-actions {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.asset-holdings-head {
  margin-bottom: 18px;
}

.asset-filter-bar {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(123, 231, 255, 0.16);
  background: linear-gradient(135deg, rgba(123, 231, 255, 0.1), rgba(15, 28, 44, 0.92));
}

.asset-filter-copy {
  color: rgba(219, 229, 240, 0.72);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.asset-filter-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.asset-filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(7, 17, 27, 0.68);
  color: #f5fbff;
  font-size: 11px;
}

.asset-preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-bottom: 18px;
}

.asset-holdings-detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.9fr);
  gap: 14px;
  align-items: start;
}

.asset-holding-row {
  cursor: pointer;
}

.asset-holding-row.is-active {
  background: rgba(123, 231, 255, 0.08);
}

.asset-holding-drawer {
  position: sticky;
  top: 18px;
}

.asset-holding-drawer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

@media (max-width: 960px) {
  .asset-holdings-head,
  .asset-holdings-head-actions,
  .asset-preview-grid,
  .asset-holdings-detail-layout,
  .asset-holding-drawer-grid {
    display: grid;
    grid-template-columns: 1fr;
  }
}
</style>
