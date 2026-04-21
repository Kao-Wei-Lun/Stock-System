<template>
  <div class="asset-holdings-pane">
    <div class="asset-holdings-head">
      <div>
        <div class="asset-card-title">持倉與流水</div>
        <div class="bt-trade-sub">把帳戶摘要、目前持倉與最近交易集中在同一頁查詢。</div>
      </div>
      <button class="asset-inline-btn" type="button" @click="$emit('open-tab', 'maintenance')">
        前往資料維護
      </button>
    </div>

    <div class="asset-preview-grid">
      <section class="asset-card">
        <div class="asset-card-title">帳戶摘要</div>
        <div v-if="assetAccountsSummary.length" class="asset-list">
          <div v-for="account in assetAccountsSummary" :key="account.account_id" class="asset-list-item static">
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
        <div v-else class="bt-history-empty">先建立至少一個資產帳戶。</div>
      </section>

      <section class="asset-card">
        <div class="asset-card-title">最近現金事件</div>
        <div v-if="assetCashEntries.length" class="asset-list">
          <div v-for="entry in assetCashEntries.slice(0, 8)" :key="entry.id" class="asset-list-item static">
            <div>
              <strong>{{ flowTypeLabel(entry.flow_type) }}</strong>
              <div class="bt-trade-sub">{{ resolveAccountName(entry.account_id) }} · {{ formatDateTime(entry.flow_date) }}</div>
            </div>
            <div class="asset-list-metrics">
              <span :class="cashTone(entry.flow_type)">{{ formatSignedCurrency(entry.amount, entry.currency, entry.flow_type) }}</span>
            </div>
          </div>
        </div>
        <div v-else class="bt-history-empty">尚無現金事件。</div>
      </section>
    </div>

    <section class="asset-card asset-card-wide">
      <div class="asset-card-head">
        <div class="asset-card-title">目前持倉</div>
        <div class="bt-trade-sub">{{ assetHoldings.length }} 檔 · 依市值排序</div>
      </div>
      <div v-if="assetHoldings.length" class="asset-table-wrap">
        <table class="asset-table">
          <thead>
            <tr>
              <th>標的</th>
              <th>帳戶</th>
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
            <tr v-for="holding in assetHoldings" :key="`${holding.account_id}-${holding.ticker}`">
              <td>
                <div class="asset-table-main">
                  <strong>{{ holding.ticker }}</strong>
                  <small>{{ holding.display_name || holding.ticker }}</small>
                </div>
              </td>
              <td>{{ holding.account_name }}</td>
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
      <div v-else class="bt-history-empty">尚無持倉，先新增現金與交易事件。</div>
    </section>

    <section class="asset-card asset-card-wide">
      <div class="asset-card-head">
        <div class="asset-card-title">最近交易</div>
        <div class="bt-trade-sub">{{ assetTradeEntries.length }} 筆記錄</div>
      </div>
      <div v-if="assetTradeEntries.length" class="asset-list">
        <div v-for="entry in assetTradeEntries.slice(0, 12)" :key="entry.id" class="asset-list-item static">
          <div>
            <strong>{{ entry.ticker }} · {{ entry.side }}</strong>
            <div class="bt-trade-sub">{{ resolveAccountName(entry.account_id) }} · {{ formatDateTime(entry.trade_date) }}</div>
          </div>
          <div class="asset-list-metrics">
            <span>{{ formatNumber(entry.quantity, 4) }} @ {{ formatNumber(entry.price, 2) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="bt-history-empty">尚無交易事件。</div>
    </section>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  assetBaseCurrency: { type: String, default: "TWD" },
  assetAccountsSummary: { type: Array, default: () => [] },
  assetHoldings: { type: Array, default: () => [] },
  assetCashEntries: { type: Array, default: () => [] },
  assetTradeEntries: { type: Array, default: () => [] },
});

defineEmits(["open-tab"]);

const totalHoldingsValue = computed(() => (props.assetHoldings || []).reduce((sum, item) => sum + Number(item?.market_value_base || 0), 0));

function resolveAccountName(accountId) {
  return props.assetAccountsSummary.find((item) => String(item.account_id) === String(accountId))?.account_name || `帳戶 #${accountId}`;
}

function holdingWeight(holding) {
  const value = Number(holding?.market_value_base || 0);
  if (!totalHoldingsValue.value) return "—";
  return `${((value / totalHoldingsValue.value) * 100).toFixed(2)}%`;
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

function cashTone(flowType) {
  return ["withdraw", "fee", "tax", "fx_fee", "transfer_out"].includes(String(flowType)) ? "dn" : "up";
}
</script>

<style scoped>
.asset-holdings-pane {
  padding: 18px;
}

.asset-holdings-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.asset-preview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-bottom: 18px;
}

@media (max-width: 960px) {
  .asset-holdings-head,
  .asset-preview-grid {
    grid-template-columns: 1fr;
    display: grid;
  }
}
</style>
