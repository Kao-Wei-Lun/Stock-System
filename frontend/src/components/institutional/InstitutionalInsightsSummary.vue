<template>
  <div>
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
            <div class="inst-kpi-change">{{ basisMetrics.basisPct >= 0 ? "+" : "" }}{{ Number(basisMetrics.basisPct || 0).toFixed(2) }}%</div>
          </div>
          <div class="inst-kpi">
            <div class="inst-kpi-label">散戶對手 Basis</div>
            <div class="inst-kpi-value" :class="basisMetrics.retailBasis >= 0 ? 'up' : 'dn'">{{ formatPriceSigned(basisMetrics.retailBasis) }}</div>
            <div class="inst-kpi-change">{{ basisMetrics.bandWidth ? `成本帶寬 ${fmtPrice(basisMetrics.bandWidth)}` : "—" }}</div>
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
  </div>
</template>

<script setup>
import { fmtPrice } from "../../utils/formatters";

defineProps({
  historyDaysLabel: { type: String, required: true },
  anomalyAlerts: { type: Array, default: () => [] },
  narrativePoints: { type: Array, default: () => [] },
  basisMetrics: { type: Object, default: null },
  basisNarrative: { type: Array, default: () => [] },
  buildInstitutionalAlertShortcut: { type: Function, required: true },
  buildBasisAlertShortcut: { type: Function, required: true },
  formatPriceSigned: { type: Function, required: true },
});

defineEmits(["create-alert"]);
</script>
