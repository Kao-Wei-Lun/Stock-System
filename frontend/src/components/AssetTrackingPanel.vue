<template>
  <div class="asset-shell">
    <div class="asset-toolbar">
      <div>
        <div class="bt-section-title">資產追蹤</div>
        <div class="asset-toolbar-copy">
          以手動帳戶、現金事件、交易流水、價格覆蓋與調整事件為來源，自動重建資產現值、績效與風險提醒。
        </div>
        <div v-if="assetLastRecompute?.generated_at" class="asset-toolbar-meta">
          最近重算：{{ formatDateTime(assetLastRecompute.generated_at) }}
        </div>
      </div>
      <div class="asset-toolbar-actions">
        <button class="sync-btn" type="button" :disabled="assetLoading" @click="$emit('reload-asset-data')">
          {{ assetLoading ? "載入中..." : "重新估值" }}
        </button>
        <button class="hero-action" type="button" :disabled="assetLoading" @click="$emit('recompute-asset-tracking')">
          {{ assetLoading ? "重算中..." : "批次重算" }}
        </button>
      </div>
    </div>

    <div v-if="assetWarnings.length || assetQuoteGaps.length || assetAlerts.length || reconciliationGapItems.length" class="asset-warning-stack">
      <div v-for="warning in assetWarnings" :key="warning" class="asset-warning-card">
        {{ warning }}
      </div>
      <div v-for="gap in assetQuoteGaps" :key="`${gap.account_id}-${gap.ticker}`" class="asset-warning-card">
        {{ gap.ticker }} 暫時抓不到最新報價，目前未納入估值；可補手動價格覆蓋。
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

    <template v-if="!isMaintenanceMode">
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
    </template>

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
        <div class="bt-row">
          <div class="bt-label">交割帳戶</div>
          <select
            data-testid="asset-account-settlement-account"
            class="bt-sel"
            :value="assetAccountForm.settlement_account_id"
            @change="$emit('update-asset-account-field', { key: 'settlement_account_id', value: $event.target.value })"
          >
            <option value="">不自動同步</option>
            <option v-for="account in settlementAccountOptions" :key="account.id" :value="account.id">{{ account.name }}</option>
          </select>
        </div>
        <label v-if="assetAccountForm.account_type === 'brokerage'" class="asset-checkbox">
          <input
            data-testid="asset-account-auto-sync-trade-settlement"
            type="checkbox"
            :checked="assetAccountForm.auto_sync_trade_settlement"
            @change="$emit('update-asset-account-field', { key: 'auto_sync_trade_settlement', value: $event.target.checked })"
          >
          <span>新增 / 更新交易時，自動同步交割帳戶資金</span>
        </label>
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
        <label class="asset-checkbox">
          <input
            data-testid="asset-cash-initial-balance"
            type="checkbox"
            :checked="assetCashForm.is_initial_balance"
            @change="$emit('update-asset-cash-field', { key: 'is_initial_balance', value: $event.target.checked })"
          >
          <span>視為期初現金，不列入後續入金</span>
        </label>
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
                <small>{{ entry.is_initial_balance ? "期初基線 · 編輯" : "編輯" }}</small>
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
      <div v-if="tradeSettlementHint" class="bt-trade-sub">{{ tradeSettlementHint }}</div>
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
      <label class="asset-checkbox">
        <input
          data-testid="asset-trade-initial-balance"
          type="checkbox"
          :checked="assetTradeForm.is_initial_balance"
          @change="$emit('update-asset-trade-field', { key: 'is_initial_balance', value: $event.target.checked })"
        >
        <span>視為期初持倉基線，以成本作為起始部位</span>
      </label>
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
              <small>{{ entry.is_initial_balance ? "期初基線 · 編輯" : "編輯" }}</small>
            </div>
          </button>
        </div>
        <div v-else class="bt-history-empty">尚無交易事件。</div>
      </div>
    </section>

    <div class="asset-form-grid asset-form-grid-3">
      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">對帳快照</div>
          <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-reconciliation-form')">清空</button>
        </div>
        <div class="bt-row">
          <div class="bt-label">帳戶</div>
          <select class="bt-sel" :value="assetReconciliationForm.account_id" @change="$emit('update-asset-reconciliation-field', { key: 'account_id', value: $event.target.value })">
            <option value="">請選擇帳戶</option>
            <option v-for="account in assetAccounts" :key="account.id" :value="account.id">{{ account.name }}</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">日期</div><input class="bt-inp" type="datetime-local" :value="assetReconciliationForm.snapshot_date" @input="$emit('update-asset-reconciliation-field', { key: 'snapshot_date', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">實際現金</div><input class="bt-inp" type="number" :value="assetReconciliationForm.cash_actual" @input="$emit('update-asset-reconciliation-field', { key: 'cash_actual', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">實際市值</div><input class="bt-inp" type="number" :value="assetReconciliationForm.market_value_actual" @input="$emit('update-asset-reconciliation-field', { key: 'market_value_actual', value: $event.target.value })"></div>
        <div class="journal-text-row">
          <div class="bt-label">備註</div>
          <textarea class="journal-textarea" :value="assetReconciliationForm.note" @input="$emit('update-asset-reconciliation-field', { key: 'note', value: $event.target.value })"></textarea>
        </div>
        <div class="asset-action-row">
          <button class="run-btn" type="button" @click="$emit('save-asset-reconciliation')">記錄對帳</button>
        </div>
        <div class="asset-subsection">
          <div class="asset-card-title">最近對帳</div>
          <div v-if="assetReconciliationEntries.length" class="asset-list">
            <div v-for="entry in assetReconciliationEntries" :key="entry.id" class="asset-list-item static">
              <div>
                <strong>{{ resolveAccountName(entry.account_id) }}</strong>
                <div class="bt-trade-sub">{{ formatDateTime(entry.snapshot_date) }}</div>
              </div>
              <div class="asset-list-metrics">
                <span>{{ reconciliationEntryLabel(entry) }}</span>
                <button class="asset-inline-btn danger" type="button" @click="$emit('delete-asset-reconciliation', entry.id)">刪除</button>
              </div>
            </div>
          </div>
          <div v-else class="bt-history-empty">尚無對帳快照。</div>
        </div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">手動價格覆蓋</div>
          <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-price-override-form')">清空</button>
        </div>
        <div class="bt-row">
          <div class="bt-label">帳戶</div>
          <select class="bt-sel" :value="assetPriceOverrideForm.account_id" @change="$emit('update-asset-price-override-field', { key: 'account_id', value: $event.target.value })">
            <option value="">全域套用</option>
            <option v-for="account in assetAccounts" :key="account.id" :value="account.id">{{ account.name }}</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">Ticker</div><input class="bt-inp" :value="assetPriceOverrideForm.ticker" @input="$emit('update-asset-price-override-field', { key: 'ticker', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">生效時間</div><input class="bt-inp" type="datetime-local" :value="assetPriceOverrideForm.effective_at" @input="$emit('update-asset-price-override-field', { key: 'effective_at', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">價格</div><input class="bt-inp" type="number" step="0.0001" :value="assetPriceOverrideForm.price" @input="$emit('update-asset-price-override-field', { key: 'price', value: $event.target.value })"></div>
        <div class="bt-row">
          <div class="bt-label">幣別</div>
          <select class="bt-sel" :value="assetPriceOverrideForm.currency" @change="$emit('update-asset-price-override-field', { key: 'currency', value: $event.target.value })">
            <option value="TWD">TWD</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">換算匯率</div><input class="bt-inp" type="number" step="0.0001" :value="assetPriceOverrideForm.fx_rate_to_base" @input="$emit('update-asset-price-override-field', { key: 'fx_rate_to_base', value: $event.target.value })"></div>
        <label class="asset-checkbox">
          <input type="checkbox" :checked="assetPriceOverrideForm.force_override" @change="$emit('update-asset-price-override-field', { key: 'force_override', value: $event.target.checked })">
          <span>強制覆蓋即時報價</span>
        </label>
        <div class="journal-text-row">
          <div class="bt-label">備註</div>
          <textarea class="journal-textarea" :value="assetPriceOverrideForm.note" @input="$emit('update-asset-price-override-field', { key: 'note', value: $event.target.value })"></textarea>
        </div>
        <div class="asset-action-row">
          <button class="run-btn" type="button" @click="$emit('save-asset-price-override')">{{ assetPriceOverrideForm.id ? "更新覆蓋" : "建立覆蓋" }}</button>
          <button v-if="assetPriceOverrideForm.id" class="sync-btn" type="button" @click="$emit('delete-asset-price-override', assetPriceOverrideForm.id)">刪除</button>
        </div>
        <div class="asset-subsection">
          <div class="asset-card-title">最近價格覆蓋</div>
          <div v-if="assetPriceOverrides.length" class="asset-list">
            <button v-for="item in assetPriceOverrides" :key="item.id" type="button" class="asset-list-item" @click="$emit('edit-asset-price-override', item)">
              <div>
                <strong>{{ item.ticker }}</strong>
                <div class="bt-trade-sub">{{ item.account_id ? resolveAccountName(item.account_id) : "全域" }} · {{ formatDateTime(item.effective_at) }}</div>
              </div>
              <div class="asset-list-metrics">
                <span>{{ formatCurrency(item.price, item.currency) }}</span>
                <small>{{ item.force_override ? "強制" : "備援" }}</small>
              </div>
            </button>
          </div>
          <div v-else class="bt-history-empty">尚無價格覆蓋。</div>
        </div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">FX 匯率</div>
          <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-fx-rate-form')">清空</button>
        </div>
        <div class="bt-row"><div class="bt-label">日期</div><input class="bt-inp" type="date" :value="assetFxRateForm.snapshot_date" @input="$emit('update-asset-fx-rate-field', { key: 'snapshot_date', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">From</div><input class="bt-inp" :value="assetFxRateForm.from_currency" @input="$emit('update-asset-fx-rate-field', { key: 'from_currency', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">To</div><input class="bt-inp" :value="assetFxRateForm.to_currency" @input="$emit('update-asset-fx-rate-field', { key: 'to_currency', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">Rate</div><input class="bt-inp" type="number" step="0.0001" :value="assetFxRateForm.rate" @input="$emit('update-asset-fx-rate-field', { key: 'rate', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">來源</div><input class="bt-inp" :value="assetFxRateForm.source" @input="$emit('update-asset-fx-rate-field', { key: 'source', value: $event.target.value })"></div>
        <div class="journal-text-row">
          <div class="bt-label">備註</div>
          <textarea class="journal-textarea" :value="assetFxRateForm.note" @input="$emit('update-asset-fx-rate-field', { key: 'note', value: $event.target.value })"></textarea>
        </div>
        <div class="asset-action-row">
          <button class="run-btn" type="button" @click="$emit('save-asset-fx-rate')">{{ assetFxRateForm.id ? "更新匯率" : "建立匯率" }}</button>
          <button v-if="assetFxRateForm.id" class="sync-btn" type="button" @click="$emit('delete-asset-fx-rate', assetFxRateForm.id)">刪除</button>
        </div>
        <div class="asset-subsection">
          <div class="asset-card-title">最近匯率</div>
          <div v-if="assetFxRates.length" class="asset-list">
            <button v-for="item in assetFxRates" :key="item.id" type="button" class="asset-list-item" @click="$emit('edit-asset-fx-rate', item)">
              <div>
                <strong>{{ item.from_currency }}/{{ item.to_currency }}</strong>
                <div class="bt-trade-sub">{{ item.snapshot_date }}</div>
              </div>
              <div class="asset-list-metrics">
                <span>{{ formatNumber(item.rate, 4) }}</span>
                <small>{{ item.source || "manual" }}</small>
              </div>
            </button>
          </div>
          <div v-else class="bt-history-empty">尚無 FX 設定。</div>
        </div>
      </section>
    </div>

    <div class="asset-form-grid asset-form-grid-3">
      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">調整事件</div>
          <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-adjustment-form')">清空</button>
        </div>
        <div class="bt-row">
          <div class="bt-label">帳戶</div>
          <select class="bt-sel" :value="assetAdjustmentForm.account_id" @change="$emit('update-asset-adjustment-field', { key: 'account_id', value: $event.target.value })">
            <option value="">請選擇帳戶</option>
            <option v-for="account in assetAccounts" :key="account.id" :value="account.id">{{ account.name }}</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">日期</div><input class="bt-inp" type="datetime-local" :value="assetAdjustmentForm.event_date" @input="$emit('update-asset-adjustment-field', { key: 'event_date', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">Ticker</div><input class="bt-inp" :value="assetAdjustmentForm.ticker" @input="$emit('update-asset-adjustment-field', { key: 'ticker', value: $event.target.value })"></div>
        <div class="bt-row">
          <div class="bt-label">事件類型</div>
          <select class="bt-sel" :value="assetAdjustmentForm.event_type" @change="$emit('update-asset-adjustment-field', { key: 'event_type', value: $event.target.value })">
            <option value="adjustment">一般調整</option>
            <option value="split">股票分割</option>
            <option value="symbol_change">代號變更</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">數量調整</div><input class="bt-inp" type="number" step="0.0001" :value="assetAdjustmentForm.quantity_delta" @input="$emit('update-asset-adjustment-field', { key: 'quantity_delta', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">成本調整</div><input class="bt-inp" type="number" step="0.0001" :value="assetAdjustmentForm.cost_basis_delta" @input="$emit('update-asset-adjustment-field', { key: 'cost_basis_delta', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">現金調整</div><input class="bt-inp" type="number" step="0.0001" :value="assetAdjustmentForm.cash_delta" @input="$emit('update-asset-adjustment-field', { key: 'cash_delta', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">Split Ratio</div><input class="bt-inp" type="number" step="0.0001" :value="assetAdjustmentForm.split_ratio" @input="$emit('update-asset-adjustment-field', { key: 'split_ratio', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">新 Ticker</div><input class="bt-inp" :value="assetAdjustmentForm.target_ticker" @input="$emit('update-asset-adjustment-field', { key: 'target_ticker', value: $event.target.value })"></div>
        <div class="journal-text-row">
          <div class="bt-label">備註</div>
          <textarea class="journal-textarea" :value="assetAdjustmentForm.note" @input="$emit('update-asset-adjustment-field', { key: 'note', value: $event.target.value })"></textarea>
        </div>
        <div class="asset-action-row">
          <button class="run-btn" type="button" @click="$emit('save-asset-adjustment')">{{ assetAdjustmentForm.id ? "更新事件" : "建立事件" }}</button>
          <button v-if="assetAdjustmentForm.id" class="sync-btn" type="button" @click="$emit('delete-asset-adjustment', assetAdjustmentForm.id)">刪除</button>
        </div>
        <div class="asset-subsection">
          <div class="asset-card-title">最近調整</div>
          <div v-if="assetAdjustments.length" class="asset-list">
            <button v-for="item in assetAdjustments" :key="item.id" type="button" class="asset-list-item" @click="$emit('edit-asset-adjustment', item)">
              <div>
                <strong>{{ item.ticker }} · {{ item.event_type }}</strong>
                <div class="bt-trade-sub">{{ resolveAccountName(item.account_id) }} · {{ formatDateTime(item.event_date) }}</div>
              </div>
              <div class="asset-list-metrics">
                <span>{{ adjustmentLabel(item) }}</span>
                <small>編輯</small>
              </div>
            </button>
          </div>
          <div v-else class="bt-history-empty">尚無調整事件。</div>
        </div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">交易 CSV 匯入</div>
          <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-import-forms')">清空</button>
        </div>
        <div class="bt-row">
          <div class="bt-label">預設帳戶</div>
          <select class="bt-sel" :value="assetTradeImportForm.default_account_id" @change="$emit('update-asset-trade-import-field', { key: 'default_account_id', value: $event.target.value })">
            <option value="">需在 CSV 內指定</option>
            <option v-for="account in assetAccounts" :key="account.id" :value="account.id">{{ account.name }}</option>
          </select>
        </div>
        <div class="journal-text-row">
          <div class="bt-label">CSV</div>
          <textarea class="journal-textarea asset-import-textarea" :value="assetTradeImportForm.csv_text" @input="$emit('update-asset-trade-import-field', { key: 'csv_text', value: $event.target.value })" placeholder="trade_date,ticker,side,quantity,price"></textarea>
        </div>
        <div class="asset-action-row">
          <button class="sync-btn" type="button" @click="$emit('import-asset-trades-csv', { dryRun: true })">預覽</button>
          <button class="run-btn" type="button" @click="$emit('import-asset-trades-csv', { dryRun: false })">正式匯入</button>
        </div>
        <div class="asset-subsection">
          <div class="asset-card-title">結果</div>
          <div v-if="assetTradeImportResult" class="asset-result-box">
            <strong>{{ importSummaryLabel(assetTradeImportResult) }}</strong>
            <div class="bt-trade-sub">錯誤 {{ assetTradeImportResult?.summary?.error_count || 0 }} 筆</div>
          </div>
          <div v-else class="bt-history-empty">先貼上 CSV 後預覽。</div>
        </div>
      </section>

      <section class="asset-card">
        <div class="asset-card-head">
          <div class="asset-card-title">現金 CSV 匯入</div>
          <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-import-forms')">清空</button>
        </div>
        <div class="bt-row">
          <div class="bt-label">預設帳戶</div>
          <select class="bt-sel" :value="assetCashImportForm.default_account_id" @change="$emit('update-asset-cash-import-field', { key: 'default_account_id', value: $event.target.value })">
            <option value="">需在 CSV 內指定</option>
            <option v-for="account in assetAccounts" :key="account.id" :value="account.id">{{ account.name }}</option>
          </select>
        </div>
        <div class="journal-text-row">
          <div class="bt-label">CSV</div>
          <textarea class="journal-textarea asset-import-textarea" :value="assetCashImportForm.csv_text" @input="$emit('update-asset-cash-import-field', { key: 'csv_text', value: $event.target.value })" placeholder="flow_date,flow_type,amount,currency"></textarea>
        </div>
        <div class="asset-action-row">
          <button class="sync-btn" type="button" @click="$emit('import-asset-cash-csv', { dryRun: true })">預覽</button>
          <button class="run-btn" type="button" @click="$emit('import-asset-cash-csv', { dryRun: false })">正式匯入</button>
        </div>
        <div class="asset-subsection">
          <div class="asset-card-title">結果</div>
          <div v-if="assetCashImportResult" class="asset-result-box">
            <strong>{{ importSummaryLabel(assetCashImportResult) }}</strong>
            <div class="bt-trade-sub">錯誤 {{ assetCashImportResult?.summary?.error_count || 0 }} 筆</div>
          </div>
          <div v-else class="bt-history-empty">先貼上 CSV 後預覽。</div>
        </div>
      </section>
    </div>

    <section class="asset-card asset-card-wide">
      <div class="asset-card-head">
        <div>
          <div class="asset-card-title">Journal 匯入</div>
          <div class="bt-trade-sub">將交易日誌中的 long 交易轉成資產流水。</div>
        </div>
        <button class="asset-inline-btn" type="button" @click="$emit('reset-asset-journal-import-form')">清空</button>
      </div>
      <div class="asset-journal-grid">
        <div class="bt-row">
          <div class="bt-label">目標帳戶</div>
          <select class="bt-sel" :value="assetJournalImportForm.account_id" @change="$emit('update-asset-journal-import-field', { key: 'account_id', value: $event.target.value })">
            <option value="">請選擇帳戶</option>
            <option v-for="account in assetAccounts" :key="account.id" :value="account.id">{{ account.name }}</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">Ticker</div><input class="bt-inp" :value="assetJournalImportForm.ticker" @input="$emit('update-asset-journal-import-field', { key: 'ticker', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">市場</div><input class="bt-inp" :value="assetJournalImportForm.market" @input="$emit('update-asset-journal-import-field', { key: 'market', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">策略</div><input class="bt-inp" :value="assetJournalImportForm.strategy_code" @input="$emit('update-asset-journal-import-field', { key: 'strategy_code', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">Tag</div><input class="bt-inp" :value="assetJournalImportForm.tag" @input="$emit('update-asset-journal-import-field', { key: 'tag', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">搜尋</div><input class="bt-inp" :value="assetJournalImportForm.search" @input="$emit('update-asset-journal-import-field', { key: 'search', value: $event.target.value })"></div>
      </div>
      <div class="asset-action-row">
        <button class="sync-btn" type="button" @click="$emit('preview-asset-journal-import')">預覽</button>
        <button class="run-btn" type="button" @click="$emit('import-asset-journal')">正式匯入</button>
      </div>
      <div class="asset-subsection">
        <div class="asset-card-title">預覽結果</div>
        <div v-if="assetJournalImportPreview?.items?.length" class="asset-list">
          <div v-for="item in assetJournalImportPreview.items" :key="item.entry_id" class="asset-list-item static">
            <div>
              <strong>{{ item.ticker || `#${item.entry_id}` }}</strong>
              <div class="bt-trade-sub">{{ formatDateTime(item.entry_time) }} → {{ formatDateTime(item.exit_time) }}</div>
            </div>
            <div class="asset-list-metrics">
              <span :class="item.importable ? 'up' : 'neutral'">{{ item.importable ? "可匯入" : item.reason || "略過" }}</span>
              <small>{{ item.payloads?.length || 0 }} legs</small>
            </div>
          </div>
        </div>
        <div v-else class="bt-history-empty">先建立預覽。</div>
      </div>
    </section>

    <template v-if="!isMaintenanceMode">
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
    </template>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  currentTicker: { type: String, required: true },
  assetLoading: { type: Boolean, required: true },
  panelMode: { type: String, default: "full" },
  assetPerformanceRange: { type: String, default: "1y" },
  assetBaseCurrency: { type: String, default: "TWD" },
  assetSummary: { type: Object, default: () => ({}) },
  assetAccounts: { type: Array, default: () => [] },
  assetAccountsSummary: { type: Array, default: () => [] },
  assetHoldings: { type: Array, default: () => [] },
  assetWarnings: { type: Array, default: () => [] },
  assetQuoteGaps: { type: Array, default: () => [] },
  assetReconciliation: { type: Object, default: () => ({ items: [], summary: {} }) },
  assetPriceOverrides: { type: Array, default: () => [] },
  assetFxRates: { type: Array, default: () => [] },
  assetAdjustments: { type: Array, default: () => [] },
  assetPerformanceSummary: { type: Object, default: () => ({}) },
  assetPerformanceSeries: { type: Array, default: () => [] },
  assetMonthlyHeatmap: { type: Array, default: () => [] },
  assetRealizedVsUnrealized: { type: Array, default: () => [] },
  assetAlerts: { type: Array, default: () => [] },
  assetTradeImportResult: { type: Object, default: null },
  assetCashImportResult: { type: Object, default: null },
  assetJournalImportPreview: { type: Object, default: null },
  assetLastRecompute: { type: Object, default: null },
  assetAccountAllocation: { type: Array, default: () => [] },
  assetMarketAllocation: { type: Array, default: () => [] },
  assetContributors: { type: Object, default: () => ({ top_gainers: [], top_losers: [] }) },
  assetCashEntries: { type: Array, default: () => [] },
  assetTradeEntries: { type: Array, default: () => [] },
  assetReconciliationEntries: { type: Array, default: () => [] },
  assetAccountForm: { type: Object, required: true },
  assetCashForm: { type: Object, required: true },
  assetTradeForm: { type: Object, required: true },
  assetReconciliationForm: { type: Object, required: true },
  assetPriceOverrideForm: { type: Object, required: true },
  assetFxRateForm: { type: Object, required: true },
  assetAdjustmentForm: { type: Object, required: true },
  assetTradeImportForm: { type: Object, required: true },
  assetCashImportForm: { type: Object, required: true },
  assetJournalImportForm: { type: Object, required: true },
});

const emit = defineEmits([
  "reload-asset-data",
  "recompute-asset-tracking",
  "set-asset-performance-range",
  "edit-asset-account",
  "update-asset-account-field",
  "update-asset-cash-field",
  "update-asset-trade-field",
  "update-asset-reconciliation-field",
  "update-asset-price-override-field",
  "update-asset-fx-rate-field",
  "update-asset-adjustment-field",
  "update-asset-trade-import-field",
  "update-asset-cash-import-field",
  "update-asset-journal-import-field",
  "save-asset-account",
  "save-asset-cash-entry",
  "save-asset-trade-entry",
  "save-asset-reconciliation",
  "save-asset-price-override",
  "save-asset-fx-rate",
  "save-asset-adjustment",
  "import-asset-trades-csv",
  "import-asset-cash-csv",
  "preview-asset-journal-import",
  "import-asset-journal",
  "reset-asset-account-form",
  "reset-asset-cash-form",
  "reset-asset-trade-form",
  "reset-asset-reconciliation-form",
  "reset-asset-price-override-form",
  "reset-asset-fx-rate-form",
  "reset-asset-adjustment-form",
  "reset-asset-import-forms",
  "reset-asset-journal-import-form",
  "edit-asset-cash-entry",
  "edit-asset-trade-entry",
  "edit-asset-price-override",
  "edit-asset-fx-rate",
  "edit-asset-adjustment",
  "delete-asset-account",
  "delete-asset-cash-entry",
  "delete-asset-trade-entry",
  "delete-asset-reconciliation",
  "delete-asset-price-override",
  "delete-asset-fx-rate",
  "delete-asset-adjustment",
]);

const performanceRangeOptions = [
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "180d", label: "180D" },
  { value: "1y", label: "1Y" },
  { value: "ytd", label: "YTD" },
  { value: "all", label: "ALL" },
];

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

const reconciliationSummary = computed(() => props.assetReconciliation?.summary || {});
const reconciliationItems = computed(() => props.assetReconciliation?.items || []);
const reconciliationGapItems = computed(() => reconciliationItems.value.filter((item) => item?.has_gap));
const isMaintenanceMode = computed(() => props.panelMode === "maintenance");
const settlementAccountOptions = computed(() => (
  (props.assetAccounts || []).filter((account) => String(account?.id) !== String(props.assetAccountForm?.id || ""))
));
const selectedTradeAccount = computed(() => (
  (props.assetAccounts || []).find((account) => String(account?.id) === String(props.assetTradeForm?.account_id || ""))
));
const tradeSettlementHint = computed(() => {
  const account = selectedTradeAccount.value;
  if (!account?.auto_sync_trade_settlement || !account?.settlement_account_id) return "";
  const settlementAccount = (props.assetAccounts || []).find(
    (item) => String(item?.id) === String(account?.settlement_account_id),
  );
  const settlementLabel = settlementAccount?.name || `帳戶 #${account.settlement_account_id}`;
  return `此券商帳戶已綁定 ${settlementLabel}，儲存交易時會自動建立對應的轉入 / 轉出交割資金。`;
});

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

function reconciliationEntryLabel(entry) {
  const parts = [];
  if (entry?.cash_actual != null) parts.push(`Cash ${formatCurrency(entry.cash_actual)}`);
  if (entry?.market_value_actual != null) parts.push(`MV ${formatCurrency(entry.market_value_actual)}`);
  return parts.join(" | ") || "Snapshot";
}

function adjustmentLabel(item) {
  if (item?.event_type === "split") return `x${formatNumber(item.split_ratio, 4)}`;
  if (item?.event_type === "symbol_change") return `→ ${item.target_ticker || "new"}`;
  return [
    item?.quantity_delta != null && item?.quantity_delta !== "" ? `Qty ${formatNumber(item.quantity_delta, 4)}` : null,
    item?.cost_basis_delta != null && item?.cost_basis_delta !== "" ? `Cost ${formatSignedCurrency(item.cost_basis_delta, props.assetBaseCurrency)}` : null,
  ].filter(Boolean).join(" · ") || "Manual";
}

function importSummaryLabel(result) {
  const summary = result?.summary || {};
  if (summary.created_count != null) return `成功匯入 ${summary.created_count} / ${summary.row_count || summary.created_count} 筆`;
  return `預覽 ${summary.row_count || 0} 筆`;
}

function heatmapTone(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "neutral";
  if (numeric >= 5) return "strong-up";
  if (numeric > 0) return "up";
  if (numeric <= -5) return "strong-dn";
  if (numeric < 0) return "dn";
  return "neutral";
}

function holdingWeight(holding) {
  const total = Number(props.assetSummary.total_asset_value_base || 0);
  const marketValue = Number(holding?.market_value_base || 0);
  if (!total || !marketValue) return "—";
  return `${((marketValue / total) * 100).toFixed(2)}%`;
}
</script>

<style>
.asset-shell {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.asset-toolbar,
.asset-card-head,
.asset-action-row,
.asset-list-item,
.asset-mini-block,
.asset-toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.asset-toolbar-copy,
.asset-toolbar-meta {
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
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 209, 102, 0.22);
  border-radius: 12px;
  background: rgba(255, 209, 102, 0.08);
  color: #ffe1a0;
  font-size: 11px;
  line-height: 1.6;
}

.asset-warning-card.info {
  border-color: rgba(0, 212, 255, 0.2);
  background: rgba(0, 212, 255, 0.08);
  color: #9cefff;
}

.asset-range-row,
.asset-summary-grid,
.asset-form-grid,
.asset-analytics-grid,
.asset-performance-grid,
.asset-journal-grid {
  display: grid;
  gap: 12px;
}

.asset-range-row {
  grid-template-columns: repeat(6, minmax(0, auto));
  justify-content: start;
}

.asset-range-btn {
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text2);
  cursor: pointer;
  font-size: 11px;
}

.asset-range-btn.active {
  border-color: rgba(0, 217, 163, 0.24);
  background: rgba(0, 217, 163, 0.12);
  color: #c6fff0;
}

.asset-summary-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.asset-form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.asset-form-grid-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.asset-analytics-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.asset-performance-grid {
  grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
}

.asset-journal-grid {
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

.asset-inline-btn.danger {
  background: rgba(255, 77, 106, 0.12);
  color: #ffb3c2;
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

.asset-badge.manual {
  background: rgba(0, 212, 255, 0.12);
  color: #9cefff;
}

.asset-curve-card {
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  background: rgba(8, 14, 24, 0.6);
  padding: 14px;
}

.asset-curve-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.asset-side-analytics {
  display: grid;
  gap: 10px;
}

.asset-sparkline-shell {
  margin-top: 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(0, 217, 163, 0.06), rgba(0, 212, 255, 0.02));
}

.asset-sparkline {
  width: 100%;
  height: 140px;
  display: block;
}

.asset-sparkline-line {
  fill: none;
  stroke: #00d9a3;
  stroke-width: 2.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.asset-heatmap-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
  gap: 8px;
}

.asset-heatmap-cell {
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.02);
}

.asset-heatmap-cell strong,
.asset-heatmap-cell span {
  display: block;
}

.asset-heatmap-cell strong {
  font-size: 11px;
}

.asset-heatmap-cell span {
  margin-top: 4px;
  font-size: 10px;
  color: var(--text2);
}

.asset-heatmap-cell.up {
  background: rgba(0, 217, 163, 0.12);
}

.asset-heatmap-cell.strong-up {
  background: rgba(0, 217, 163, 0.22);
}

.asset-heatmap-cell.dn {
  background: rgba(255, 77, 106, 0.1);
}

.asset-heatmap-cell.strong-dn {
  background: rgba(255, 77, 106, 0.2);
}

.asset-import-textarea {
  min-height: 150px;
}

.asset-result-box {
  margin-top: 10px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
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
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .asset-trade-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .asset-form-grid-3,
  .asset-journal-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1120px) {
  .asset-form-grid,
  .asset-form-grid-3,
  .asset-analytics-grid,
  .asset-performance-grid,
  .asset-journal-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .asset-summary-grid,
  .asset-trade-grid,
  .asset-range-row {
    grid-template-columns: 1fr;
  }

  .asset-toolbar,
  .asset-toolbar-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .asset-curve-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
