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
        <div v-for="row in overlayRows" :key="row.key" class="ind-row">
          <div>
            <div class="ind-name">{{ row.label }}</div>
            <div v-if="row.hint" class="ind-hint">{{ row.hint }}</div>
          </div>
          <div class="ind-row-actions">
            <div class="ind-val" :style="{ color: row.color }">{{ row.value }}</div>
            <div class="ind-toggle" :class="{ on: activeInd[row.key] }" @click="$emit('toggle-indicator', row.key)"></div>
          </div>
        </div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">震盪 (副圖)</div>
        <div v-for="row in panelRows" :key="row.key" class="ind-row">
          <div>
            <div class="ind-name">{{ row.label }}</div>
            <div v-if="row.hint" class="ind-hint">{{ row.hint }}</div>
          </div>
          <div class="ind-row-actions">
            <div class="ind-val" :class="row.valueClass">{{ row.value }}</div>
            <div class="ind-toggle" :class="{ on: activePanels[row.key] }" @click="$emit('toggle-panel', row.key)"></div>
          </div>
        </div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">指標參數</div>
        <div v-for="section in settingSections" :key="section.title" class="setting-section">
          <div class="setting-section-title">{{ section.title }}</div>
          <div class="setting-grid">
            <label v-for="setting in section.items" :key="setting.key" class="setting-row">
              <span class="setting-label">{{ setting.label }}</span>
              <input
                class="setting-input"
                type="number"
                :step="setting.step"
                :min="setting.min"
                :max="setting.max"
                :value="indicatorSettings[setting.key]"
                @input="$emit('update-indicator-setting', { key: setting.key, value: $event.target.value })"
              />
              <span class="setting-range">{{ setting.range }}</span>
            </label>
          </div>
        </div>
      </div>

      <div class="ind-group">
        <div class="ind-group-title">技術面總結</div>
        <div class="tech-summary" v-html="indicatorSnapshot.techSummaryHtml"></div>
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
import { computed } from "vue";

const props = defineProps({
  rightTab: { type: String, required: true },
  indicatorSnapshot: { type: Object, required: true },
  activeInd: { type: Object, required: true },
  activePanels: { type: Object, required: true },
  indicatorSettings: { type: Object, required: true },
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
  "update-indicator-setting",
  "apply-indicator-preset",
  "open-alert-modal",
  "update-backtest-field",
  "run-backtest",
  "sync-all",
]);

const overlayRows = computed(() => [
  { key: "ma20", label: `MA ${props.indicatorSettings.ma20Period}`, value: props.indicatorSnapshot.ma20, color: "#3b8bff" },
  { key: "ma50", label: `MA ${props.indicatorSettings.ma50Period}`, value: props.indicatorSnapshot.ma50, color: "#f5a623" },
  { key: "ma200", label: `MA ${props.indicatorSettings.ma200Period}`, value: props.indicatorSnapshot.ma200, color: "#9b6dff" },
  { key: "ema12", label: `EMA ${props.indicatorSettings.emaPeriod}`, value: props.indicatorSnapshot.ema12, color: "#00d4ff" },
  {
    key: "bb",
    label: `布林通道 (${props.indicatorSettings.bbPeriod}, ${props.indicatorSettings.bbMultiplier})`,
    value: props.indicatorSnapshot.bb,
    color: "#ffd166",
  },
  { key: "vwap", label: "VWAP", value: "ON", color: "#ff8c42", hint: "盤中量價基準線" },
  {
    key: "ichimoku",
    label: `Ichimoku (${props.indicatorSettings.ichimokuConversion}, ${props.indicatorSettings.ichimokuBase}, ${props.indicatorSettings.ichimokuSpanB})`,
    value: props.indicatorSnapshot.ichimoku,
    color: "#8dc1ff",
    hint: `位移 ${props.indicatorSettings.ichimokuDisplacement}`,
  },
  {
    key: "supertrend",
    label: `SuperTrend (${props.indicatorSettings.supertrendPeriod}, ${props.indicatorSettings.supertrendMultiplier})`,
    value: props.indicatorSnapshot.supertrend,
    color: "#7be7ff",
    hint: "多空切換支撐線",
  },
]);

const panelRows = computed(() => [
  {
    key: "rsi",
    label: `RSI(${props.indicatorSettings.rsiPeriod})`,
    hint: "70 超買 / 30 超賣",
    value: props.indicatorSnapshot.rsi,
    valueClass: props.indicatorSnapshot.rsiClass,
  },
  {
    key: "macd",
    label: `MACD(${props.indicatorSettings.macdFast},${props.indicatorSettings.macdSlow},${props.indicatorSettings.macdSignal})`,
    hint: props.indicatorSnapshot.macdSignal,
    value: props.indicatorSnapshot.macd,
    valueClass: "",
  },
  {
    key: "stoch",
    label: `KD Stoch(${props.indicatorSettings.stochK},${props.indicatorSettings.stochD})`,
    hint: "擺盪強弱",
    value: props.indicatorSnapshot.stoch,
    valueClass: "",
  },
  {
    key: "atr",
    label: `ATR(${props.indicatorSettings.atrPeriod})`,
    hint: "波動幅度 / 停損參考",
    value: props.indicatorSnapshot.atr,
    valueClass: "",
  },
  {
    key: "cci",
    label: `CCI(${props.indicatorSettings.cciPeriod})`,
    hint: "±100 強弱區間",
    value: props.indicatorSnapshot.cci,
    valueClass: "",
  },
  {
    key: "obv",
    label: "OBV",
    hint: "量能趨勢累積",
    value: props.indicatorSnapshot.obv,
    valueClass: "",
  },
  {
    key: "adx",
    label: `ADX(${props.indicatorSettings.adxPeriod})`,
    hint: props.indicatorSnapshot.adxSignal,
    value: props.indicatorSnapshot.adx,
    valueClass: "",
  },
]);

const settingSections = computed(() => [
  {
    title: "主圖參數",
    items: [
      { key: "ma20Period", label: "MA 快線", step: 1, min: 2, max: 400, range: "2-400" },
      { key: "ma50Period", label: "MA 中線", step: 1, min: 2, max: 600, range: "2-600" },
      { key: "ma200Period", label: "MA 長線", step: 1, min: 2, max: 1200, range: "2-1200" },
      { key: "emaPeriod", label: "EMA", step: 1, min: 2, max: 400, range: "2-400" },
      { key: "bbPeriod", label: "BB 週期", step: 1, min: 5, max: 300, range: "5-300" },
      { key: "bbMultiplier", label: "BB 倍數", step: 0.1, min: 0.5, max: 6, range: "0.5-6" },
      { key: "volumeMaPeriod", label: "量均線", step: 1, min: 2, max: 200, range: "2-200" },
      { key: "ichimokuConversion", label: "轉換線", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "ichimokuBase", label: "基準線", step: 1, min: 3, max: 120, range: "3-120" },
      { key: "ichimokuSpanB", label: "先行 B", step: 1, min: 4, max: 240, range: "4-240" },
      { key: "ichimokuDisplacement", label: "雲圖位移", step: 1, min: 1, max: 120, range: "1-120" },
      { key: "supertrendPeriod", label: "SuperTrend 週期", step: 1, min: 2, max: 120, range: "2-120" },
      { key: "supertrendMultiplier", label: "SuperTrend 倍數", step: 0.1, min: 0.5, max: 10, range: "0.5-10" },
    ],
  },
  {
    title: "副圖參數",
    items: [
      { key: "rsiPeriod", label: "RSI", step: 1, min: 2, max: 100, range: "2-100" },
      { key: "macdFast", label: "MACD 快線", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "macdSlow", label: "MACD 慢線", step: 1, min: 3, max: 120, range: "3-120" },
      { key: "macdSignal", label: "MACD 訊號", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "stochK", label: "KD K", step: 1, min: 3, max: 100, range: "3-100" },
      { key: "stochD", label: "KD D", step: 1, min: 2, max: 20, range: "2-20" },
      { key: "atrPeriod", label: "ATR", step: 1, min: 2, max: 120, range: "2-120" },
      { key: "cciPeriod", label: "CCI", step: 1, min: 3, max: 120, range: "3-120" },
      { key: "adxPeriod", label: "ADX", step: 1, min: 2, max: 120, range: "2-120" },
    ],
  },
]);
</script>
