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
      <div v-if="data.cash_summary_warning" class="institutional-inline-error">
        {{ data.cash_summary_warning }}
      </div>

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
          <div class="institutional-ranking-grid">
            <div class="institutional-card">
              <div class="institutional-section-head">
                <div>
                  <div class="ind-group-title">法人籌碼異常值警報</div>
                  <div class="institutional-section-note">用近 {{ historyDaysLabel }} 的基準偵測極端口數、資金流與期現貨偏離</div>
                </div>
                <button
                  v-if="anomalyAlerts.length"
                  type="button"
                  class="tool-btn institutional-action-btn"
                  @click="$emit('create-alert', buildInstitutionalAlertShortcut(anomalyAlerts[0]))"
                >
                  設異常警報
                </button>
              </div>
              <div v-if="anomalyAlerts.length" class="institutional-rows compact">
                <div v-for="alert in anomalyAlerts" :key="alert.title" class="inst-row wide">
                  <div>
                    <strong>{{ alert.title }}</strong>
                    <div class="inst-row-sub">{{ alert.detail }}</div>
                  </div>
                  <div class="inst-row-metrics">
                    <span :class="alert.directionClass">{{ alert.value }}</span>
                    <span class="institutional-alert-badge" :class="alert.severityClass">{{ alert.levelLabel }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="institutional-empty institutional-empty-compact">近 {{ historyDaysLabel }} 暫未偵測到顯著異常值</div>
            </div>

            <div class="institutional-card">
              <div class="institutional-section-head">
                <div class="ind-group-title">自動產出法人觀點摘要</div>
                <div class="institutional-section-note">綜合法人未平倉、現貨、選擇權與 Basis 變化自動整理重點</div>
              </div>
              <ul class="institutional-summary-list">
                <li v-for="point in narrativePoints" :key="point">{{ point }}</li>
              </ul>
            </div>
          </div>
        </div>

        <div class="institutional-section">
          <div class="institutional-section-head">
            <div>
              <div class="ind-group-title">法人期現貨偏離 / Basis 分析</div>
              <div class="institutional-section-note">比較法人合成成本、散戶對手成本與現貨參考價的偏離程度</div>
            </div>
            <button
              v-if="basisMetrics"
              type="button"
              class="tool-btn institutional-action-btn"
              @click="$emit('create-alert', buildBasisAlertShortcut())"
            >
              設 Basis 警報
            </button>
          </div>
          <template v-if="basisMetrics">
            <div class="institutional-kpi-strip">
              <div class="inst-kpi">
                <div class="inst-kpi-label">現貨參考</div>
                <div class="inst-kpi-value">{{ basisMetrics.spotLabel }}</div>
                <div class="inst-kpi-change">{{ fmtPrice(basisMetrics.spotPrice) }}</div>
              </div>
              <div class="inst-kpi">
                <div class="inst-kpi-label">法人 Basis</div>
                <div class="inst-kpi-value" :class="basisMetrics.basis >= 0 ? 'up' : 'dn'">{{ formatPriceSigned(basisMetrics.basis) }}</div>
                <div class="inst-kpi-change">{{ basisMetrics.basisPct >= 0 ? '+' : '' }}{{ Number(basisMetrics.basisPct || 0).toFixed(2) }}%</div>
              </div>
              <div class="inst-kpi">
                <div class="inst-kpi-label">散戶對手 Basis</div>
                <div class="inst-kpi-value" :class="basisMetrics.retailBasis >= 0 ? 'up' : 'dn'">{{ formatPriceSigned(basisMetrics.retailBasis) }}</div>
                <div class="inst-kpi-change">{{ basisMetrics.bandWidth ? `成本帶寬 ${fmtPrice(basisMetrics.bandWidth)}` : '—' }}</div>
              </div>
              <div class="inst-kpi">
                <div class="inst-kpi-label">成本帶位置</div>
                <div class="inst-kpi-value">{{ basisMetrics.spotPosition }}</div>
                <div class="inst-kpi-change">{{ fmtPrice(basisMetrics.bandLow) }} → {{ fmtPrice(basisMetrics.bandHigh) }}</div>
              </div>
            </div>
            <div class="institutional-card">
              <ul class="institutional-summary-list">
                <li v-for="point in basisNarrative" :key="point">{{ point }}</li>
              </ul>
            </div>
          </template>
          <div v-else class="institutional-card">
            <div class="institutional-empty institutional-empty-compact">目前所選期貨商品沒有可對照的現貨參考價，暫時無法產生 Basis 分析。</div>
          </div>
        </div>

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
  "create-alert",
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

const SPOT_REFERENCE_BY_COMMODITY = {
  "臺股期貨": "^TWII",
  "小型臺指期貨": "^TWII",
  "微型臺指期貨": "^TWII",
  "臺灣永續期貨": "^TWII",
  "臺灣生技期貨": "^TWII",
  "櫃買指數期貨": "^TWOII",
};

function mean(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function stddev(values, avg) {
  if (!values.length) return 0;
  const variance = values.reduce((sum, value) => sum + ((value - avg) ** 2), 0) / values.length;
  return Math.sqrt(variance);
}

function formatPriceSigned(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${numeric >= 0 ? "+" : "-"}${fmtPrice(Math.abs(numeric))}`;
}

function formatCashSigned(value) {
  const numeric = Number(value || 0);
  if (!numeric) return "0";
  const absValue = Math.abs(numeric);
  if (absValue >= 1000) {
    return `${numeric >= 0 ? "+" : "-"}${(absValue / 100).toFixed(1)}億`;
  }
  return `${numeric >= 0 ? "+" : "-"}${absValue.toFixed(1)}百萬`;
}

function analyzeHistorySeries(points, key = "合計") {
  const normalized = (points || [])
    .map((point) => ({
      date: point?.date,
      value: Number(point?.[key]),
    }))
    .filter((point) => Number.isFinite(point.value));

  if (normalized.length < 4) return null;

  const latest = normalized.at(-1);
  const previousValues = normalized.slice(0, -1).map((point) => point.value);
  const avg = mean(previousValues);
  const deviation = stddev(previousValues, avg);
  const zScore = deviation > 0 ? (latest.value - avg) / deviation : 0;
  const relativeShift = Math.abs(latest.value - avg) / Math.max(Math.abs(avg), 1);

  return {
    latest: latest.value,
    date: latest.date,
    average: avg,
    previous: normalized.at(-2)?.value ?? avg,
    zScore,
    score: Math.max(Math.abs(zScore), relativeShift * 1.8),
  };
}

function createSeriesAlert(title, stats, formatter, detailPrefix) {
  if (!stats || stats.score < 1.8) return null;
  const isHigh = stats.score >= 2.7;
  return {
    title,
    detail: `${detailPrefix} 最新 ${formatter(stats.latest)}，近窗均值 ${formatter(stats.average)}`,
    value: formatter(stats.latest),
    directionClass: stats.latest >= stats.average ? "up" : "dn",
    severityClass: isHigh ? "high" : "medium",
    levelLabel: isHigh ? "高異常" : "留意",
    score: stats.score,
  };
}

const totalCashNet = computed(() =>
  aggregatedCashSummary.value.reduce((sum, row) => sum + Number(row?.net_amount || 0), 0),
);

const selectedSpotReference = computed(() => {
  const mappedTicker = SPOT_REFERENCE_BY_COMMODITY[props.selectedFuturesCommodity];
  if (!mappedTicker) return null;
  return (props.data?.spot_reference || []).find((item) => item.ticker === mappedTicker) || null;
});

const alertTicker = computed(() => (
  selectedSpotReference.value?.ticker
  || (props.data?.spot_reference || []).find((item) => item?.ticker)?.ticker
  || ""
));

function roundBasisThreshold(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "";
  const absValue = Math.abs(numeric);
  const stepped = Math.ceil((absValue + 0.15) * 10) / 10;
  return numeric >= 0 ? stepped.toFixed(1) : (-stepped).toFixed(1);
}

const basisMetrics = computed(() => {
  const spot = selectedSpotReference.value;
  const spotPrice = spot?.price == null ? Number.NaN : Number(spot.price);
  const institutionPrice = futuresCostEstimate.value?.institution_estimate?.price == null
    ? Number.NaN
    : Number(futuresCostEstimate.value.institution_estimate.price);
  const retailPrice = futuresCostEstimate.value?.retail_estimate?.price == null
    ? Number.NaN
    : Number(futuresCostEstimate.value.retail_estimate.price);
  const bandLow = futuresCostEstimate.value?.band_low == null ? Number.NaN : Number(futuresCostEstimate.value.band_low);
  const bandHigh = futuresCostEstimate.value?.band_high == null ? Number.NaN : Number(futuresCostEstimate.value.band_high);

  if (!Number.isFinite(spotPrice) || !Number.isFinite(institutionPrice)) return null;

  const basis = institutionPrice - spotPrice;
  const retailBasis = Number.isFinite(retailPrice) ? retailPrice - spotPrice : null;
  const bandWidth = Number.isFinite(bandLow) && Number.isFinite(bandHigh) ? bandHigh - bandLow : null;
  const spotPosition = Number.isFinite(bandLow) && Number.isFinite(bandHigh)
    ? (spotPrice < bandLow ? "現貨低於成本帶" : spotPrice > bandHigh ? "現貨高於成本帶" : "現貨落在成本帶內")
    : "以法人成本為主";

  return {
    spotLabel: spot?.label || spot?.ticker || "現貨",
    spotPrice,
    bandLow: Number.isFinite(bandLow) ? bandLow : null,
    bandHigh: Number.isFinite(bandHigh) ? bandHigh : null,
    bandWidth,
    institutionPrice,
    retailPrice: Number.isFinite(retailPrice) ? retailPrice : null,
    basis,
    basisPct: spotPrice ? (basis / spotPrice) * 100 : null,
    retailBasis,
    spotPosition,
  };
});

const anomalyAlerts = computed(() => {
  const alerts = [
    createSeriesAlert(
      "期貨未平倉淨口數異常",
      analyzeHistorySeries(props.insights?.history?.futures_oi, "合計"),
      formatSigned,
      `${props.selectedFuturesCommodity} / 三大法人`,
    ),
    createSeriesAlert(
      "期貨當日交易淨口數異常",
      analyzeHistorySeries(props.insights?.history?.futures_trade, "合計"),
      formatSigned,
      `${props.selectedFuturesCommodity} / 交易口數`,
    ),
    createSeriesAlert(
      "外資選擇權偏向擴大",
      analyzeHistorySeries(props.insights?.history?.call_put_balance, "外資"),
      formatSigned,
      `${props.selectedOptionsCommodity} / 外資 Call-Put`,
    ),
    createSeriesAlert(
      "現貨三大法人買賣超異常",
      analyzeHistorySeries(props.insights?.history?.cash_net, "合計"),
      formatCashSigned,
      "TWSE 現貨 / 三大法人",
    ),
  ].filter(Boolean);

  if (basisMetrics.value && Math.abs(Number(basisMetrics.value.basisPct || 0)) >= 1.2) {
    const absPct = Math.abs(Number(basisMetrics.value.basisPct || 0));
    alerts.push({
      title: "期現貨偏離擴大",
      detail: `${basisMetrics.value.spotLabel} 與法人合成成本偏離 ${formatPriceSigned(basisMetrics.value.basis)}`,
      value: `${basisMetrics.value.basis >= 0 ? "+" : ""}${Number(basisMetrics.value.basisPct || 0).toFixed(2)}%`,
      directionClass: basisMetrics.value.basis >= 0 ? "up" : "dn",
      severityClass: absPct >= 2 ? "high" : "medium",
      levelLabel: absPct >= 2 ? "高異常" : "留意",
      score: absPct,
    });
  }

  return alerts
    .sort((left, right) => Number(right.score || 0) - Number(left.score || 0))
    .slice(0, 6);
});

const basisNarrative = computed(() => {
  if (!basisMetrics.value) return [];
  const points = [];
  points.push(
    `${basisMetrics.value.spotLabel} 現貨為 ${fmtPrice(basisMetrics.value.spotPrice)}，法人合成成本為 ${fmtPrice(basisMetrics.value.institutionPrice)}，目前 Basis 為 ${formatPriceSigned(basisMetrics.value.basis)}。`,
  );
  if (basisMetrics.value.retailPrice != null) {
    points.push(
      `散戶 / 非三大法人對手成本推估約在 ${fmtPrice(basisMetrics.value.retailPrice)}，對照現貨偏離 ${formatPriceSigned(basisMetrics.value.retailBasis)}。`,
    );
  }
  if (basisMetrics.value.bandLow != null && basisMetrics.value.bandHigh != null) {
    points.push(
      `主力成本帶區間落在 ${fmtPrice(basisMetrics.value.bandLow)} 到 ${fmtPrice(basisMetrics.value.bandHigh)}，目前判定為「${basisMetrics.value.spotPosition}」。`,
    );
  }
  return points;
});

function buildInstitutionalAlertShortcut(alert = anomalyAlerts.value[0]) {
  const targetLabel = props.selectedFuturesCommodity || "法人籌碼";
  return {
    ticker: alertTicker.value || "MARKET",
    type: "institutional",
    condition: alert?.severityClass === "high" ? "high" : "medium_or_high",
    value: "",
    futures_commodity: props.selectedFuturesCommodity || "",
    options_commodity: props.selectedOptionsCommodity || "",
    target_label: targetLabel,
    prefill_hint: alert
      ? `法人異常警報會追蹤「${alert.title}」是否再次進入${alert.severityClass === "high" ? "高異常" : "中度以上異常"}。`
      : `${targetLabel} 法人異常警報會追蹤近窗籌碼是否再次放大。`,
    context_tags: ["法人異常", targetLabel, alert?.levelLabel].filter(Boolean),
  };
}

function buildBasisAlertShortcut() {
  if (!basisMetrics.value) return null;
  const basisPct = Number(basisMetrics.value.basisPct || 0);
  return {
    ticker: alertTicker.value || "MARKET",
    type: "basis",
    condition: basisPct >= 0 ? "大於" : "小於",
    value: roundBasisThreshold(basisPct),
    metric: "basis_pct",
    futures_commodity: props.selectedFuturesCommodity || "",
    target_label: `${props.selectedFuturesCommodity || "Basis"} / ${basisMetrics.value.spotLabel}`,
    prefill_hint: `${basisMetrics.value.spotLabel} 與法人合成成本目前偏離 ${basisPct >= 0 ? "+" : ""}${basisPct.toFixed(2)}%，可直接調整成你想追蹤的 Basis 門檻。`,
    context_tags: ["Basis", props.selectedFuturesCommodity || "", basisMetrics.value.spotLabel].filter(Boolean),
  };
}

const narrativePoints = computed(() => {
  const points = [];
  const institutionSide = futuresCostEstimate.value?.institution_estimate?.side || "中性";
  const institutionNetVolume = Number(futuresCostEstimate.value?.institution_estimate?.net_volume || 0);
  const cashBias = totalCashNet.value;

  points.push(
    `${props.selectedFuturesCommodity || "期貨"} 目前三大法人未平倉偏向${institutionSide}方，合成淨口數 ${formatSigned(institutionNetVolume)}。`,
  );

  if (cashBias) {
    points.push(
      `現貨三大法人合計${cashBias >= 0 ? "買超" : "賣超"} ${formatCashSigned(cashBias)}，與期貨方向${Math.sign(cashBias) === Math.sign(institutionNetVolume) ? "一致" : "出現分歧"}。`,
    );
  }

  if (foreignCallPutBalance.value) {
    points.push(
      `外資在 ${props.selectedOptionsCommodity || "選擇權"} 的 Call / Put 未平倉差為 ${formatSigned(foreignCallPutBalance.value)}，顯示其偏向${foreignCallPutBalance.value >= 0 ? "偏多" : "偏空"}配置。`,
    );
  }

  if (basisMetrics.value) {
    points.push(
      `期現貨 Basis 目前為 ${formatPriceSigned(basisMetrics.value.basis)}，${basisMetrics.value.basis >= 0 ? "期貨成本高於現貨" : "期貨成本低於現貨"}，位置判讀為 ${basisMetrics.value.spotPosition}。`,
    );
  }

  if (anomalyAlerts.value.length) {
    points.push(`異常監測目前最需要留意的是「${anomalyAlerts.value[0].title}」：${anomalyAlerts.value[0].detail}。`);
  }

  return points.filter(Boolean).slice(0, 5);
});
</script>
