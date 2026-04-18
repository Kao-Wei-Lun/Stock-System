<template>
  <div class="asset-shell">
    <div class="asset-toolbar">
      <div>
        <div class="bt-section-title">資產追蹤</div>
        <div class="asset-toolbar-copy">
          以手動帳戶、現金事件與台美股交易為來源，自動推導目前資產現值與損益。
        </div>
      </div>
      <button class="hero-action" type="button" :disabled="assetLoading" @click="$emit('reload-asset-data')">
        {{ assetLoading ? "重算中..." : "重新估值" }}
      </button>
    </div>

    <div v-if="assetWarnings.length || assetQuoteGaps.length" class="asset-warning-stack">
      <div v-for="warning in assetWarnings" :key="warning" class="asset-warning-card">
        {{ warning }}
      </div>
      <div v-for="gap in assetQuoteGaps" :key="`${gap.account_id}-${gap.ticker}`" class="asset-warning-card">
        {{ gap.ticker }} 暫時抓不到最新報價，目前未納入未實現損益。
      </div>
    </div>

    <div class="asset-summary-grid">
      <article v-for="card in summaryCards" :key="card.key" class="asset-summary-card">
        <span>{{ card.label }}</span>
        <strong :class="card.tone">{{ card.value }}</strong>
      </article>
    </div>

    <div class="asset-form-grid">
      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">帳戶管理</div>
          <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-account-form')">清空</button>
        </div>
        <div class="bt-row"><div class="bt-label">帳戶名稱</div><input class="bt-inp" :value="assetAccountForm.name" @input="$emit('update-asset-account-field', { key: 'name', value: $event.target.value })" placeholder="Main Broker"></div>
        <div class="bt-row"><div class="bt-label">機構</div><input class="bt-inp" :value="assetAccountForm.institution" @input="$emit('update-asset-account-field', { key: 'institution', value: $event.target.value })" placeholder="Manual / IBKR"></div>
        <div class="bt-row">
          <div class="bt-label">類型</div>
          <select class="bt-sel" :value="assetAccountForm.account_type" @change="$emit('update-asset-account-field', { key: 'account_type', value: $event.target.value })">
            <option value="brokerage">券商帳戶</option>
            <option value="bank">銀行帳戶</option>
            <option value="cash">現金帳戶</option>
          </select>
        </div>
        <div class="bt-row">
          <div class="bt-label">基準幣別</div>
          <select class="bt-sel" :value="assetAccountForm.base_currency" @change="$emit('update-asset-account-field', { key: 'base_currency', value: $event.target.value })">
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">排序</div><input class="bt-inp" type="number" :value="assetAccountForm.sort_order" @input="$emit('update-asset-account-field', { key: 'sort_order', value: $event.target.value })"></div>
        <label class="asset-checkbox">
          <input type="checkbox" :checked="assetAccountForm.include_in_total" @change="$emit('update-asset-account-field', { key: 'include_in_total', value: $event.target.checked })">
          <span>列入總資產</span>
        </label>
        <div class="journal-text-row">
          <div class="bt-label">備註</div>
          <textarea class="journal-textarea" :value="assetAccountForm.notes" @input="$emit('update-asset-account-field', { key: 'notes', value: $event.target.value })"></textarea>
        </div>
        <div class="asset-action-row">
          <button class="run-btn" type="button" @click="$emit('save-asset-account')">{{ assetAccountForm.id ? "更新帳戶" : "建立帳戶" }}</button>
          <button v-if="assetAccountForm.id" class="sync-btn" type="button" @click="$emit('delete-asset-account', assetAccountForm.id)">刪除帳戶</button>
        </div>

        <div class="asset-subsection">
          <div class="asset-card-title">帳戶摘要</div>
          <div v-if="assetAccountsSummary.length" class="asset-list">
            <button v-for="account in assetAccountsSummary" :key="account.account_id" type="button" class="asset-list-item" @click="selectAccount(account.account_id)">
              <div>
                <strong>{{ account.account_name }}</strong>
                <div class="bt-trade-sub">{{ account.account_type || "account" }} · {{ account.base_currency }}</div>
              </div>
              <div class="asset-list-metrics">
                <span>{{ formatCurrency(account.cash_total_base) }}</span>
                <small>{{ account.include_in_total ? "列入總額" : "僅供追蹤" }}</small>
              </div>
            </button>
          </div>
          <div v-else class="bt-history-empty">先建立至少一個資產帳戶。</div>
        </div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">現金事件</div>
          <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-cash-form')">清空</button>
        </div>
        <div class="bt-row">
          <div class="bt-label">帳戶</div>
          <select class="bt-sel" :value="assetCashForm.account_id" @change="$emit('update-asset-cash-field', { key: 'account_id', value: $event.target.value })">
            <option value="">請選擇帳戶</option>
            <option v-for="account in assetAccounts" :key="account.id" :value="account.id">{{ account.name }}</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">日期</div><input class="bt-inp" type="datetime-local" :value="assetCashForm.flow_date" @input="$emit('update-asset-cash-field', { key: 'flow_date', value: $event.target.value })"></div>
        <div class="bt-row">
          <div class="bt-label">類型</div>
          <select class="bt-sel" :value="assetCashForm.flow_type" @change="$emit('update-asset-cash-field', { key: 'flow_type', value: $event.target.value })">
            <option v-for="type in cashFlowTypes" :key="type.value" :value="type.value">{{ type.label }}</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">金額</div><input class="bt-inp" type="number" :value="assetCashForm.amount" @input="$emit('update-asset-cash-field', { key: 'amount', value: $event.target.value })"></div>
        <div class="bt-row">
          <div class="bt-label">幣別</div>
          <select class="bt-sel" :value="assetCashForm.currency" @change="$emit('update-asset-cash-field', { key: 'currency', value: $event.target.value })">
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">換算匯率</div><input class="bt-inp" type="number" step="0.0001" :value="assetCashForm.fx_rate_to_base" @input="$emit('update-asset-cash-field', { key: 'fx_rate_to_base', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">對象</div><input class="bt-inp" :value="assetCashForm.counterparty" @input="$emit('update-asset-cash-field', { key: 'counterparty', value: $event.target.value })" placeholder="銀行 / 券商 / 公司"></div>
        <div class="journal-text-row">
          <div class="bt-label">備註</div>
          <textarea class="journal-textarea" :value="assetCashForm.note" @input="$emit('update-asset-cash-field', { key: 'note', value: $event.target.value })"></textarea>
        </div>
        <div class="asset-action-row">
          <button class="run-btn" type="button" @click="$emit('save-asset-cash-entry')">{{ assetCashForm.id ? "更新事件" : "新增事件" }}</button>
          <button v-if="assetCashForm.id" class="sync-btn" type="button" @click="$emit('delete-asset-cash-entry', assetCashForm.id)">刪除事件</button>
        </div>

        <div class="asset-subsection">
          <div class="asset-card-title">最近現金事件</div>
          <div v-if="assetCashEntries.length" class="asset-list">
            <button v-for="entry in assetCashEntries" :key="entry.id" type="button" class="asset-list-item" @click="$emit('edit-asset-cash-entry', entry)">
              <div>
                <strong>{{ flowTypeLabel(entry.flow_type) }}</strong>
                <div class="bt-trade-sub">{{ resolveAccountName(entry.account_id) }} · {{ formatDateTime(entry.flow_date) }}</div>
              </div>
              <div class="asset-list-metrics">
                <span :class="cashTone(entry.flow_type)">{{ formatSignedCurrency(entry.amount, entry.currency, entry.flow_type) }}</span>
                <small>編輯</small>
              </div>
            </button>
          </div>
          <div v-else class="bt-history-empty">尚無現金事件。</div>
        </div>
      </section>
    </div>

    <section class="asset-card asset-card-wide">
      <div class="asset-card-head">
        <div>
          <div class="asset-card-title">交易事件</div>
          <div class="bt-trade-sub">目前標的 {{ currentTicker }} 可直接帶入成為新交易草稿。</div>
        </div>
        <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-trade-form')">帶入目前標的</button>
      </div>
      <div class="asset-trade-grid">
        <div class="bt-row">
          <div class="bt-label">帳戶</div>
          <select class="bt-sel" :value="assetTradeForm.account_id" @change="$emit('update-asset-trade-field', { key: 'account_id', value: $event.target.value })">
            <option value="">請選擇帳戶</option>
            <option v-for="account in assetAccounts" :key="account.id" :value="account.id">{{ account.name }}</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">日期</div><input class="bt-inp" type="datetime-local" :value="assetTradeForm.trade_date" @input="$emit('update-asset-trade-field', { key: 'trade_date', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">Ticker</div><input class="bt-inp" :value="assetTradeForm.ticker" @input="$emit('update-asset-trade-field', { key: 'ticker', value: $event.target.value })" placeholder="2330 / AAPL"></div>
        <div class="bt-row"><div class="bt-label">名稱</div><input class="bt-inp" :value="assetTradeForm.display_name" @input="$emit('update-asset-trade-field', { key: 'display_name', value: $event.target.value })" placeholder="TSMC / Apple"></div>
        <div class="bt-row">
          <div class="bt-label">市場</div>
          <select class="bt-sel" :value="assetTradeForm.market" @change="$emit('update-asset-trade-field', { key: 'market', value: $event.target.value })">
            <option value="TW">TW</option>
            <option value="US">US</option>
            <option value="HK">HK</option>
          </select>
        </div>
        <div class="bt-row">
          <div class="bt-label">方向</div>
          <select class="bt-sel" :value="assetTradeForm.side" @change="$emit('update-asset-trade-field', { key: 'side', value: $event.target.value })">
            <option value="buy">買進</option>
            <option value="sell">賣出</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">數量</div><input class="bt-inp" type="number" step="0.0001" :value="assetTradeForm.quantity" @input="$emit('update-asset-trade-field', { key: 'quantity', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">成交價</div><input class="bt-inp" type="number" step="0.0001" :value="assetTradeForm.price" @input="$emit('update-asset-trade-field', { key: 'price', value: $event.target.value })"></div>
        <div class="bt-row">
          <div class="bt-label">幣別</div>
          <select class="bt-sel" :value="assetTradeForm.currency" @change="$emit('update-asset-trade-field', { key: 'currency', value: $event.target.value })">
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">手續費</div><input class="bt-inp" type="number" step="0.0001" :value="assetTradeForm.fee_amount" @input="$emit('update-asset-trade-field', { key: 'fee_amount', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">稅費</div><input class="bt-inp" type="number" step="0.0001" :value="assetTradeForm.tax_amount" @input="$emit('update-asset-trade-field', { key: 'tax_amount', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">換算匯率</div><input class="bt-inp" type="number" step="0.0001" :value="assetTradeForm.fx_rate_to_base" @input="$emit('update-asset-trade-field', { key: 'fx_rate_to_base', value: $event.target.value })"></div>
      </div>
      <div class="journal-text-row">
        <div class="bt-label">備註</div>
        <textarea class="journal-textarea" :value="assetTradeForm.note" @input="$emit('update-asset-trade-field', { key: 'note', value: $event.target.value })"></textarea>
      </div>
      <div class="asset-action-row">
        <button class="run-btn" type="button" @click="$emit('save-asset-trade-entry')">{{ assetTradeForm.id ? "更新交易" : "新增交易" }}</button>
        <button class="sync-btn" type="button" @click="$emit('reset-asset-trade-form')">重設表單</button>
        <button v-if="assetTradeForm.id" class="sync-btn" type="button" @click="$emit('delete-asset-trade-entry', assetTradeForm.id)">刪除交易</button>
      </div>

      <div class="asset-subsection">
        <div class="asset-card-title">最近交易</div>
        <div v-if="assetTradeEntries.length" class="asset-list">
          <button v-for="entry in assetTradeEntries" :key="entry.id" type="button" class="asset-list-item" @click="$emit('edit-asset-trade-entry', entry)">
            <div>
              <strong>{{ entry.ticker }} · {{ entry.side }}</strong>
              <div class="bt-trade-sub">{{ resolveAccountName(entry.account_id) }} · {{ formatDateTime(entry.trade_date) }}</div>
            </div>
            <div class="asset-list-metrics">
              <span>{{ formatNumber(entry.quantity, 4) }} @ {{ formatNumber(entry.price, 2) }}</span>
              <small>編輯</small>
            </div>
          </button>
        </div>
        <div v-else class="bt-history-empty">尚無交易事件。</div>
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
        <div v-else class="bt-history-empty">目前沒有持倉市值。</div>
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
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  currentTicker: { type: String, required: true },
  assetLoading: { type: Boolean, required: true },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetAccounts: { type: Array, default: () => [] },
  assetAccountsSummary: { type: Array, default: () => [] },
  assetHoldings: { type: Array, default: () => [] },
  assetWarnings: { type: Array, default: () => [] },
  assetQuoteGaps: { type: Array, default: () => [] },
  assetAccountAllocation: { type: Array, default: () => [] },
  assetMarketAllocation: { type: Array, default: () => [] },
  assetContributors: { type: Object, default: () => ({ top_gainers: [], top_losers: [] }) },
  assetCashEntries: { type: Array, default: () => [] },
  assetTradeEntries: { type: Array, default: () => [] },
  assetAccountForm: { type: Object, required: true },
  assetCashForm: { type: Object, required: true },
  assetTradeForm: { type: Object, required: true },
});

const emit = defineEmits([
  "reload-asset-data",
  "edit-asset-account",
  "update-asset-account-field",
  "update-asset-cash-field",
  "update-asset-trade-field",
  "save-asset-account",
  "save-asset-cash-entry",
  "save-asset-trade-entry",
  "reset-asset-account-form",
  "reset-asset-cash-form",
  "reset-asset-trade-form",
  "edit-asset-cash-entry",
  "edit-asset-trade-entry",
  "delete-asset-account",
  "delete-asset-cash-entry",
  "delete-asset-trade-entry",
]);

const cashFlowTypes = [
  { value: "deposit", label: "入金" },
  { value: "withdraw", label: "出金" },
  { value: "dividend", label: "股利" },
  { value: "interest", label: "利息" },
  { value: "fee", label: "費用" },
  { value: "tax", label: "稅" },
  { value: "fx_fee", label: "匯費" },
  { value: "transfer_in", label: "轉入" },
  { value: "transfer_out", label: "轉出" },
  { value: "adjustment", label: "調整" },
];

const summaryCards = computed(() => [
  { key: "total", label: "總資產現值", value: formatCurrency(props.assetSummary.total_asset_value_base), tone: "neutral" },
  { key: "cash", label: "現金總額", value: formatCurrency(props.assetSummary.cash_total_base), tone: "neutral" },
  { key: "market", label: "持倉市值", value: formatCurrency(props.assetSummary.market_value_total_base), tone: "neutral" },
  { key: "unrealized", label: "未實現損益", value: formatSignedCurrency(props.assetSummary.unrealized_total_base, props.assetBaseCurrency), tone: Number(props.assetSummary.unrealized_total_base || 0) >= 0 ? "up" : "dn" },
  { key: "realized", label: "已實現損益", value: formatSignedCurrency(props.assetSummary.realized_total_base, props.assetBaseCurrency), tone: Number(props.assetSummary.realized_total_base || 0) >= 0 ? "up" : "dn" },
  { key: "positions", label: "持倉檔數", value: String(props.assetSummary.holding_count || 0), tone: "neutral" },
]);

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

function flowTypeLabel(flowType) {
  return cashFlowTypes.find((item) => item.value === flowType)?.label || flowType;
}

function cashTone(flowType) {
  return ["withdraw", "fee", "tax", "fx_fee", "transfer_out"].includes(String(flowType)) ? "dn" : "up";
}

function resolveAccountName(accountId) {
  return props.assetAccounts.find((item) => String(item.id) === String(accountId))?.name || `帳戶 #${accountId}`;
}

function selectAccount(accountId) {
  const target = props.assetAccounts.find((item) => String(item.id) === String(accountId));
  if (!target) return;
  emit("edit-asset-account", target);
}

function contributorLabel(item) {
  if (!item) return "尚無資料";
  return `${item.ticker} · ${formatSignedCurrency(item.unrealized_pnl_base, props.assetBaseCurrency)}`;
}

function holdingWeight(holding) {
  const total = Number(props.assetSummary.total_asset_value_base || 0);
  const marketValue = Number(holding?.market_value_base || 0);
  if (!total || !marketValue) return "—";
  return `${((marketValue / total) * 100).toFixed(2)}%`;
}
</script>

<style scoped>
.asset-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.asset-toolbar,
.asset-card-head,
.asset-action-row,
.asset-list-item,
.asset-mini-block {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.asset-toolbar-copy {
  margin-top: 6px;
  color: var(--text2);
  font-size: 12px;
  line-height: 1.6;
}

.asset-warning-stack {
  display: grid;
  gap: 8px;
}

.asset-warning-card {
  padding: 10px 12px;
  border: 1px solid rgba(255, 209, 102, 0.22);
  border-radius: 12px;
  background: rgba(255, 209, 102, 0.08);
  color: #ffe1a0;
  font-size: 11px;
  line-height: 1.6;
}

.asset-summary-grid,
.asset-form-grid,
.asset-analytics-grid {
  display: grid;
  gap: 12px;
}

.asset-summary-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.asset-form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.asset-analytics-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.asset-summary-card,
.asset-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
}

.asset-summary-card {
  padding: 14px;
}

.asset-summary-card span,
.asset-mini-block span {
  display: block;
  color: var(--text3);
  font-size: 10px;
}

.asset-summary-card strong,
.asset-mini-block strong {
  display: block;
  margin-top: 6px;
  font-size: 16px;
  color: var(--text1);
}

.asset-card {
  padding: 16px;
}

.asset-card-wide {
  grid-column: 1 / -1;
}

.asset-card-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text1);
}

.asset-inline-btn {
  border: 0;
  border-radius: 999px;
  padding: 7px 10px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
  cursor: pointer;
  font-size: 10px;
}

.asset-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  color: var(--text2);
  font-size: 11px;
}

.asset-subsection {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.asset-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.asset-list-item {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  background: rgba(8, 14, 24, 0.75);
  color: var(--text1);
  text-align: left;
  cursor: pointer;
}

.asset-list-item.static {
  cursor: default;
}

.asset-list-metrics {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.asset-list-metrics span {
  font-size: 12px;
  color: var(--text1);
}

.asset-list-metrics small,
.asset-table-main small {
  color: var(--text3);
  font-size: 10px;
}

.asset-action-row {
  margin-top: 12px;
  justify-content: flex-start;
}

.asset-trade-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px 12px;
}

.asset-table-wrap {
  margin-top: 10px;
  overflow: auto;
}

.asset-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 980px;
}

.asset-table th,
.asset-table td {
  padding: 10px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  text-align: left;
  font-size: 11px;
}

.asset-table th {
  color: var(--text3);
  font-weight: 600;
}

.asset-table-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.asset-badge {
  display: inline-flex;
  align-items: center;
  margin-left: 6px;
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 9px;
}

.asset-badge.delayed {
  background: rgba(255, 209, 102, 0.12);
  color: #ffe1a0;
}

.up {
  color: var(--green);
}

.dn {
  color: var(--red);
}

.neutral {
  color: var(--text1);
}

@media (max-width: 1320px) {
  .asset-summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .asset-trade-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1120px) {
  .asset-form-grid,
  .asset-analytics-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .asset-summary-grid,
  .asset-trade-grid {
    grid-template-columns: 1fr;
  }
}
</style>
