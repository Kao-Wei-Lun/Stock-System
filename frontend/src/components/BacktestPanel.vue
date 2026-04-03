<template>
<div class="rp-content">
      <div class="bt-row">
        <div class="bt-label">策略</div>
        <select class="bt-sel" :value="backtestForm.strategy" @change="$emit('update-backtest-field', { key: 'strategy', value: $event.target.value })">
          <option>MA 黃金/死亡交叉</option>
          <option>RSI 超買超賣</option>
          <option>MACD 交叉</option>
          <option>布林通道突破</option>
          <option>KD 交叉</option>
        </select>
      </div>
      <div class="bt-row"><div class="bt-label">開始日期</div><input class="bt-inp" type="date" :value="backtestForm.start" @input="$emit('update-backtest-field', { key: 'start', value: $event.target.value })"></div>
      <div class="bt-row"><div class="bt-label">結束日期</div><input class="bt-inp" type="date" :value="backtestForm.end" @input="$emit('update-backtest-field', { key: 'end', value: $event.target.value })"></div>
      <div class="bt-row"><div class="bt-label">初始資金</div><input class="bt-inp" type="number" :value="backtestForm.capital" @input="$emit('update-backtest-field', { key: 'capital', value: $event.target.value })"></div>
      <div class="bt-row">
        <div class="bt-label">倉位配置</div>
        <select class="bt-sel" :value="backtestForm.positionSizing || 'full_equity'" @change="$emit('update-backtest-field', { key: 'positionSizing', value: $event.target.value })">
          <option value="full_equity">100% 資金</option>
          <option value="half_equity">50% 資金</option>
          <option value="quarter_equity">25% 資金</option>
        </select>
      </div>
      <div class="bt-row"><div class="bt-label">手續費</div><input class="bt-inp" type="number" :value="backtestForm.fee" step="0.01" @input="$emit('update-backtest-field', { key: 'fee', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <div class="bt-row"><div class="bt-label">滑價</div><input class="bt-inp" type="number" :value="backtestForm.slippage" step="0.01" @input="$emit('update-backtest-field', { key: 'slippage', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <div class="bt-row"><div class="bt-label">停損</div><input class="bt-inp" type="number" :value="backtestForm.sl" step="0.5" @input="$emit('update-backtest-field', { key: 'sl', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <div class="bt-row"><div class="bt-label">停利</div><input class="bt-inp" type="number" :value="backtestForm.tp" step="0.5" @input="$emit('update-backtest-field', { key: 'tp', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <button class="run-btn" :disabled="backtestLoading" @click="$emit('run-backtest')">{{ backtestLoading ? "回測中..." : "▶ 執行回測" }}</button>

      <div v-if="backtestResult" style="margin-top:12px">
        <div style="font-family:'Syne',sans-serif;font-size:13px;font-weight:700;margin-bottom:10px">{{ backtestResult.strategy }}</div>
        <div class="bt-metric"><span>期間</span><span>{{ backtestResult.start }} ~ {{ backtestResult.end }}</span></div>
        <div class="bt-metric"><span>初始資金</span><span>${{ Number(backtestResult.capital).toLocaleString() }}</span></div>
        <div class="bt-metric"><span>倉位配置</span><span>{{ formatPositionSizing(backtestResult.positionSizing) }}</span></div>
        <div class="bt-metric"><span>最終資金</span><span :class="backtestResult.totalReturn >= 0 ? 'up' : 'dn'">${{ Math.round(backtestResult.finalEquity).toLocaleString() }}</span></div>
        <div class="bt-metric"><span>總報酬率</span><span :class="backtestResult.totalReturn >= 0 ? 'up' : 'dn'">{{ backtestResult.totalReturn >= 0 ? "+" : "" }}{{ backtestResult.totalReturn.toFixed(2) }}%</span></div>
        <div class="bt-metric"><span>交易次數</span><span>{{ backtestResult.sellTrades }}</span></div>
        <div class="bt-metric"><span>勝率</span><span :class="backtestResult.winRate >= 50 ? 'up' : 'dn'">{{ backtestResult.winRate.toFixed(1) }}%</span></div>
        <div class="bt-metric"><span>最大回撤</span><span class="dn">-{{ backtestResult.maxDrawdown.toFixed(2) }}%</span></div>
        <div class="bt-metric"><span>夏普比率</span><span :class="backtestResult.sharpe >= 1 ? 'up' : ''">{{ backtestResult.sharpe.toFixed(2) }}</span></div>
        <div class="bt-metric"><span>滑價</span><span>{{ ((backtestResult.slippageRate || 0) * 100).toFixed(2) }}%</span></div>
        <div class="bt-metric"><span>停損 / 停利</span><span>{{ formatPct(backtestResult.stopLoss) }} / {{ formatPct(backtestResult.takeProfit) }}</span></div>
        <div v-if="backtestEquityPath" class="bt-equity-card">
          <div class="bt-section-title">權益曲線</div>
          <svg class="bt-equity-chart" viewBox="0 0 240 90" preserveAspectRatio="none" aria-label="backtest equity curve">
            <path class="bt-equity-grid" d="M0 15 H240 M0 45 H240 M0 75 H240"></path>
            <path :d="backtestEquityPath" class="bt-equity-line"></path>
          </svg>
        </div>
        <div v-if="backtestTradeRows.length" class="bt-trade-card">
          <div class="bt-section-title">交易明細</div>
          <div v-for="trade in backtestTradeRows" :key="trade.id || `${trade.entry_date}-${trade.exit_date}`" class="bt-trade-row">
            <div>
              <div>{{ trade.entry_date }} → {{ trade.exit_date }}</div>
              <div class="bt-trade-sub">{{ trade.exit_reason || "strategy_exit" }} · {{ Number(trade.quantity || 0).toLocaleString() }} 股</div>
            </div>
            <div :class="Number(trade.net_pnl) >= 0 ? 'up' : 'dn'">
              {{ Number(trade.net_pnl) >= 0 ? "+" : "" }}${{ Math.round(Number(trade.net_pnl || 0)).toLocaleString() }}
            </div>
          </div>
        </div>
        <div style="margin-top:8px;padding:6px;background:rgba(245,166,35,.05);border:1px solid rgba(245,166,35,.2);border-radius:4px;font-size:10px;color:var(--text3)">
          基於 {{ backtestResult.bars }} 根 K 線真實歷史資料 · 回測結果僅供參考
        </div>
      </div>

      <div v-if="backtestCompareRows.length" class="bt-compare-card" data-testid="backtest-compare-card">
        <div class="bt-compare-head">
          <div class="bt-section-title">歷史比較</div>
          <button type="button" class="bt-compare-clear" data-testid="backtest-compare-clear" @click="$emit('clear-backtest-compare')">清空比較</button>
        </div>
        <div class="bt-compare-grid">
          <div v-for="item in backtestCompareRows" :key="item.id" class="bt-compare-item" :data-testid="`backtest-compare-item-${item.id}`">
            <div class="bt-compare-item-head">
              <div>
                <div>{{ item.strategy }}</div>
                <div class="bt-trade-sub">{{ item.start }} ~ {{ item.end }}</div>
              </div>
              <button type="button" class="bt-compare-remove" :data-testid="`backtest-compare-remove-${item.id}`" @click="$emit('toggle-backtest-compare', item.id)">移除</button>
            </div>
            <div class="bt-compare-metric"><span>報酬率</span><span :class="item.totalReturn >= 0 ? 'up' : 'dn'">{{ item.totalReturn >= 0 ? "+" : "" }}{{ Number(item.totalReturn || 0).toFixed(2) }}%</span></div>
            <div class="bt-compare-metric"><span>最終資金</span><span>${{ Math.round(Number(item.finalEquity || 0)).toLocaleString() }}</span></div>
            <div class="bt-compare-metric"><span>最大回撤</span><span class="dn">-{{ Number(item.maxDrawdown || 0).toFixed(2) }}%</span></div>
            <div class="bt-compare-metric"><span>勝率</span><span>{{ Number(item.winRate || 0).toFixed(1) }}%</span></div>
            <div class="bt-compare-metric"><span>倉位</span><span>{{ formatPositionSizing(item.positionSizing) }}</span></div>
          </div>
        </div>
      </div>

      <div class="bt-history-card">
        <div class="bt-section-title">歷史回測</div>
        <div v-if="backtestHistory.length">
          <div
            v-for="item in backtestHistoryRows"
            :key="item.id"
            class="bt-history-row"
            :class="{ active: isBacktestRunCompared(item.id) }"
          >
            <span>
              <div>{{ item.strategy }}</div>
              <div class="bt-trade-sub">{{ item.start }} ~ {{ item.end }}</div>
            </span>
            <div class="bt-history-row-actions">
              <span :class="item.totalReturn >= 0 ? 'up' : 'dn'">{{ item.totalReturn >= 0 ? "+" : "" }}{{ item.totalReturn.toFixed(2) }}%</span>
              <button type="button" class="bt-history-action" :data-testid="`backtest-load-${item.id}`" @click="$emit('load-backtest', item.id)">載入</button>
              <button
                type="button"
                class="bt-history-action bt-history-compare"
                :class="{ active: isBacktestRunCompared(item.id) }"
                :data-testid="`backtest-compare-toggle-${item.id}`"
                @click="$emit('toggle-backtest-compare', item.id)"
              >
                {{ isBacktestRunCompared(item.id) ? "取消比較" : "比較" }}
              </button>
            </div>
          </div>
        </div>
        <div v-else class="bt-history-empty">尚無回測紀錄</div>
      </div>
    </div>
</template>
<script setup>
defineProps(["backtestForm", "backtestResult", "backtestLoading", "backtestHistory", "formatPct", "formatPositionSizing", "backtestEquityPath", "backtestTradeRows", "backtestHistoryRows", "backtestCompareRows", "isBacktestRunCompared"]);
defineEmits(["update-backtest-field", "run-backtest", "load-backtest", "toggle-backtest-compare", "clear-backtest-compare"]);
</script>
<style scoped>
.bt-compare-card {
  margin-top: 12px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(123, 231, 255, 0.16);
  background: rgba(6, 16, 24, 0.92);
}

.bt-compare-head,
.bt-compare-item-head,
.bt-history-row-actions,
.bt-compare-metric {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.bt-compare-grid {
  display: grid;
  gap: 10px;
  margin-top: 10px;
}

.bt-compare-item {
  padding: 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.bt-compare-metric {
  margin-top: 6px;
  font-size: 10px;
  line-height: 1.5;
  color: var(--text3);
}

.bt-compare-metric span:last-child {
  color: var(--text1);
}

.bt-compare-clear,
.bt-compare-remove,
.bt-history-action {
  border: 0;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 10px;
  line-height: 1.3;
  cursor: pointer;
}

.bt-compare-clear,
.bt-history-action {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
}

.bt-compare-remove {
  background: rgba(255, 77, 106, 0.12);
  color: #ff8da0;
}

.bt-history-row {
  align-items: center;
}

.bt-history-row.active {
  border-color: rgba(123, 231, 255, 0.24);
  box-shadow: 0 0 0 1px rgba(123, 231, 255, 0.08) inset;
}

.bt-history-row-actions {
  flex-wrap: wrap;
}

.bt-history-compare.active {
  background: rgba(123, 231, 255, 0.14);
  color: #c9f6ff;
}
</style>
