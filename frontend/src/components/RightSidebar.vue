<template>
  <div class="right-panel">
    <div class="rp-tabs">
      <div class="rtab" :class="{ active: rightTab === 'indicators' }" @click="$emit('set-right-tab', 'indicators')">指標</div>
      <div class="rtab" :class="{ active: rightTab === 'alerts' }" @click="$emit('set-right-tab', 'alerts')">警報</div>
      <div class="rtab" :class="{ active: rightTab === 'backtest' }" @click="$emit('set-right-tab', 'backtest')">回測</div>
      <div class="rtab" :class="{ active: rightTab === 'db' }" @click="$emit('set-right-tab', 'db')">資料庫</div>
    </div>

    <div v-show="rightTab === 'indicators'" class="rp-content">
      <div class="ind-group">
        <div class="ind-group-title">指標模板</div>
        <div class="preset-grid">
          <button class="preset-chip" @click="$emit('apply-indicator-preset', 'trend')">趨勢模板</button>
          <button class="preset-chip" @click="$emit('apply-indicator-preset', 'swing')">擺盪模板</button>
          <button class="preset-chip" @click="$emit('apply-indicator-preset', 'volume')">量價模板</button>
          <button class="preset-chip" @click="$emit('apply-indicator-preset', 'clean')">清爽模板</button>
        </div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">趨勢 (疊加主圖)</div>
        <div class="ind-row"><div class="ind-name">MA 20</div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val" style="color:#3b8bff">{{ indicatorSnapshot.ma20 }}</div><div class="ind-toggle" :class="{ on: activeInd.ma20 }" @click="$emit('toggle-indicator','ma20')"></div></div></div>
        <div class="ind-row"><div class="ind-name">MA 50</div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val" style="color:#f5a623">{{ indicatorSnapshot.ma50 }}</div><div class="ind-toggle" :class="{ on: activeInd.ma50 }" @click="$emit('toggle-indicator','ma50')"></div></div></div>
        <div class="ind-row"><div class="ind-name">MA 200</div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val" style="color:#9b6dff">{{ indicatorSnapshot.ma200 }}</div><div class="ind-toggle" :class="{ on: activeInd.ma200 }" @click="$emit('toggle-indicator','ma200')"></div></div></div>
        <div class="ind-row"><div class="ind-name">EMA 12</div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val" style="color:#00d4ff">{{ indicatorSnapshot.ema12 }}</div><div class="ind-toggle" :class="{ on: activeInd.ema12 }" @click="$emit('toggle-indicator','ema12')"></div></div></div>
        <div class="ind-row"><div class="ind-name">布林通道</div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val" style="color:#ffd166">{{ indicatorSnapshot.bb }}</div><div class="ind-toggle" :class="{ on: activeInd.bb }" @click="$emit('toggle-indicator','bb')"></div></div></div>
        <div class="ind-row"><div class="ind-name">VWAP</div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val" style="color:#ff8c42">ON</div><div class="ind-toggle" :class="{ on: activeInd.vwap }" @click="$emit('toggle-indicator','vwap')"></div></div></div>
        <div class="ind-row"><div><div class="ind-name">Ichimoku 雲圖</div><div style="font-size:9px;color:var(--text3)">Tenkan / Kijun / Cloud</div></div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val" style="color:#8dc1ff">{{ indicatorSnapshot.ichimoku }}</div><div class="ind-toggle" :class="{ on: activeInd.ichimoku }" @click="$emit('toggle-indicator','ichimoku')"></div></div></div>
        <div class="ind-row"><div><div class="ind-name">SuperTrend(10,3)</div><div style="font-size:9px;color:var(--text3)">多空切換支撐線</div></div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val" style="color:#7be7ff">{{ indicatorSnapshot.supertrend }}</div><div class="ind-toggle" :class="{ on: activeInd.supertrend }" @click="$emit('toggle-indicator','supertrend')"></div></div></div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">震盪 (副圖)</div>
        <div class="ind-row"><div><div class="ind-name">RSI(14)</div><div style="font-size:9px;color:var(--text3)">70超買 / 30超賣</div></div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val" :class="indicatorSnapshot.rsiClass">{{ indicatorSnapshot.rsi }}</div><div class="ind-toggle" :class="{ on: activePanels.rsi }" @click="$emit('toggle-panel','rsi')"></div></div></div>
        <div class="ind-row"><div><div class="ind-name">MACD(12,26,9)</div><div style="font-size:9px;color:var(--text3)">{{ indicatorSnapshot.macdSignal }}</div></div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val">{{ indicatorSnapshot.macd }}</div><div class="ind-toggle" :class="{ on: activePanels.macd }" @click="$emit('toggle-panel','macd')"></div></div></div>
        <div class="ind-row"><div><div class="ind-name">KD Stoch(14,3)</div></div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val">{{ indicatorSnapshot.stoch }}</div><div class="ind-toggle" :class="{ on: activePanels.stoch }" @click="$emit('toggle-panel','stoch')"></div></div></div>
        <div class="ind-row"><div><div class="ind-name">ATR(14)</div><div style="font-size:9px;color:var(--text3)">波動幅度 / 停損參考</div></div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val">{{ indicatorSnapshot.atr }}</div><div class="ind-toggle" :class="{ on: activePanels.atr }" @click="$emit('toggle-panel','atr')"></div></div></div>
        <div class="ind-row"><div><div class="ind-name">CCI(20)</div><div style="font-size:9px;color:var(--text3)">±100 強弱區間</div></div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val">{{ indicatorSnapshot.cci }}</div><div class="ind-toggle" :class="{ on: activePanels.cci }" @click="$emit('toggle-panel','cci')"></div></div></div>
        <div class="ind-row"><div><div class="ind-name">OBV</div><div style="font-size:9px;color:var(--text3)">量能趨勢累積</div></div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val">{{ indicatorSnapshot.obv }}</div><div class="ind-toggle" :class="{ on: activePanels.obv }" @click="$emit('toggle-panel','obv')"></div></div></div>
        <div class="ind-row"><div><div class="ind-name">ADX(14)</div><div style="font-size:9px;color:var(--text3)">{{ indicatorSnapshot.adxSignal }}</div></div><div style="display:flex;align-items:center;gap:8px"><div class="ind-val">{{ indicatorSnapshot.adx }}</div><div class="ind-toggle" :class="{ on: activePanels.adx }" @click="$emit('toggle-panel','adx')"></div></div></div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">技術面總結</div>
        <div style="font-size:11px;color:var(--text2);line-height:1.8" v-html="indicatorSnapshot.techSummaryHtml"></div>
      </div>
    </div>

    <div v-show="rightTab === 'alerts'" class="rp-content">
      <div v-if="alerts.length">
        <div v-for="(alert, index) in alerts" :key="`${alert.ticker}-${index}`" class="alert-card" :class="{ triggered: alert.triggered }">
          <div class="alert-tk">{{ alert.ticker }}</div>
          <div class="alert-cond">{{ alert.type }} {{ alert.cond }} {{ alert.value }}</div>
          <div class="alert-badge" :class="alert.triggered ? 'triggered' : 'active'">{{ alert.triggered ? "已觸發" : "監控中" }}</div>
        </div>
      </div>
      <div v-else style="color:var(--text3);font-size:11px;text-align:center;padding:16px">尚無警報</div>
      <button class="add-btn" @click="$emit('open-alert-modal')">＋ 新增警報</button>
    </div>

    <div v-show="rightTab === 'backtest'" class="rp-content">
      <div class="bt-row"><div class="bt-label">策略</div><select class="bt-sel" :value="backtestForm.strategy" @change="$emit('update-backtest-field', { key: 'strategy', value: $event.target.value })"><option>MA 黃金/死亡交叉</option><option>RSI 超買超賣</option><option>MACD 交叉</option><option>布林通道突破</option><option>KD 交叉</option></select></div>
      <div class="bt-row"><div class="bt-label">開始日期</div><input class="bt-inp" type="date" :value="backtestForm.start" @input="$emit('update-backtest-field', { key: 'start', value: $event.target.value })"></div>
      <div class="bt-row"><div class="bt-label">結束日期</div><input class="bt-inp" type="date" :value="backtestForm.end" @input="$emit('update-backtest-field', { key: 'end', value: $event.target.value })"></div>
      <div class="bt-row"><div class="bt-label">初始資金</div><input class="bt-inp" type="number" :value="backtestForm.capital" @input="$emit('update-backtest-field', { key: 'capital', value: $event.target.value })"></div>
      <div class="bt-row"><div class="bt-label">手續費</div><input class="bt-inp" type="number" :value="backtestForm.fee" step="0.01" @input="$emit('update-backtest-field', { key: 'fee', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <div class="bt-row"><div class="bt-label">停損</div><input class="bt-inp" type="number" :value="backtestForm.sl" step="0.5" @input="$emit('update-backtest-field', { key: 'sl', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <div class="bt-row"><div class="bt-label">停利</div><input class="bt-inp" type="number" :value="backtestForm.tp" step="0.5" @input="$emit('update-backtest-field', { key: 'tp', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <button class="run-btn" @click="$emit('run-backtest')">▶ 執行回測</button>

      <div v-if="backtestResult" style="margin-top:12px">
        <div style="font-family:'Syne',sans-serif;font-size:13px;font-weight:700;margin-bottom:10px">{{ backtestResult.strategy }}</div>
        <div class="bt-metric"><span>期間</span><span>{{ backtestResult.start }} ~ {{ backtestResult.end }}</span></div>
        <div class="bt-metric"><span>初始資金</span><span>${{ Number(backtestResult.capital).toLocaleString() }}</span></div>
        <div class="bt-metric"><span>最終資金</span><span :class="backtestResult.totalReturn >= 0 ? 'up' : 'dn'">${{ Math.round(backtestResult.finalEquity).toLocaleString() }}</span></div>
        <div class="bt-metric"><span>總報酬率</span><span :class="backtestResult.totalReturn >= 0 ? 'up' : 'dn'">{{ backtestResult.totalReturn >= 0 ? "+" : "" }}{{ backtestResult.totalReturn.toFixed(2) }}%</span></div>
        <div class="bt-metric"><span>交易次數</span><span>{{ backtestResult.sellTrades }}</span></div>
        <div class="bt-metric"><span>勝率</span><span :class="backtestResult.winRate >= 50 ? 'up' : 'dn'">{{ backtestResult.winRate.toFixed(1) }}%</span></div>
        <div class="bt-metric"><span>最大回撤</span><span class="dn">-{{ backtestResult.maxDrawdown.toFixed(2) }}%</span></div>
        <div class="bt-metric"><span>夏普比率</span><span :class="backtestResult.sharpe >= 1 ? 'up' : ''">{{ backtestResult.sharpe.toFixed(2) }}</span></div>
        <div style="margin-top:8px;padding:6px;background:rgba(245,166,35,.05);border:1px solid rgba(245,166,35,.2);border-radius:4px;font-size:10px;color:var(--text3)">基於 {{ backtestResult.bars }} 根 K 線真實歷史資料 · 回測結果僅供參考</div>
      </div>
    </div>

    <div v-show="rightTab === 'db'" class="rp-content">
      <div class="ind-group">
        <div class="ind-group-title">資料庫狀態</div>
        <div v-if="dbStats">
          <div class="db-stat-row"><span>總 K 線筆數</span><span style="color:var(--green)">{{ dbStats.total_rows?.toLocaleString() }}</span></div>
          <div class="db-stat-row"><span>股票數量</span><span>{{ dbStats.total_tickers }}</span></div>
          <div v-for="item in dbStats.top_tickers || []" :key="item.ticker" class="db-stat-row"><span>{{ item.ticker }}</span><span>{{ item.rows }} 筆</span></div>
        </div>
        <div v-else style="color:var(--red);font-size:11px">{{ dbStatsError || "載入中..." }}</div>
      </div>
      <button class="sync-btn" :disabled="syncingAll" @click="$emit('sync-all')">{{ syncingAll ? "↻ 同步中..." : "↻ 同步所有股票最新資料" }}</button>
      <div style="margin-top:10px;font-size:10px;color:var(--text3);line-height:1.8">
        資料庫：<span style="color:var(--text2)">MySQL / quantvision</span><br>
        資料來源：<span style="color:var(--text2)">Yahoo Finance</span><br>
        更新頻率：<span style="color:var(--text2)">每 15 秒輪詢</span><br>
        歷史資料：<span style="color:var(--text2)">最多 2 年</span>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  rightTab: { type: String, required: true },
  indicatorSnapshot: { type: Object, required: true },
  activeInd: { type: Object, required: true },
  activePanels: { type: Object, required: true },
  alerts: { type: Array, required: true },
  backtestForm: { type: Object, required: true },
  backtestResult: { type: Object, default: null },
  dbStats: { type: Object, default: null },
  dbStatsError: { type: String, default: "" },
  syncingAll: { type: Boolean, required: true },
});

defineEmits([
  "set-right-tab",
  "toggle-indicator",
  "toggle-panel",
  "apply-indicator-preset",
  "open-alert-modal",
  "update-backtest-field",
  "run-backtest",
  "sync-all",
]);
</script>
