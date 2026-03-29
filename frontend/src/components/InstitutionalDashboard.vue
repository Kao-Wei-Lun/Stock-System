<template>
  <div class="institutional-shell">
    <div class="institutional-toolbar">
      <div>
        <div class="institutional-title">TAIFEX 三大法人籌碼</div>
        <div class="institutional-subtitle">
          期貨、選擇權、買賣權分計與現貨參考一次整合
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
        <button class="tool-btn active" :disabled="loading" @click="$emit('refresh')">
          {{ loading ? "載入中..." : "重新整理" }}
        </button>
      </div>
    </div>

    <div class="chart-meta institutional-meta">
      <div class="meta-chip">查詢日 {{ selectedDate || "—" }}</div>
      <div class="meta-chip">實際資料日 {{ data?.resolved_date || "—" }}</div>
      <div class="meta-chip">對比日 {{ data?.previous_date || "—" }}</div>
      <div class="meta-chip is-hint">資料來源：台灣期貨交易所三大法人依日期查詢、證交所現貨法人買賣超摘要</div>
    </div>

    <div v-if="loading" class="institutional-loading">
      <div class="spinner"></div>
      <p>正在載入期權法人資料...</p>
    </div>
    <div v-else-if="error" class="institutional-error">{{ error }}</div>
    <template v-else-if="data">
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
          <div class="ind-group-title">現貨法人買賣超</div>
          <div class="institutional-rows compact">
            <div v-for="row in data.cash_summary || []" :key="row.institution" class="inst-row">
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
                <strong>外資台指期淨未平倉</strong>
                <div class="inst-row-sub">{{ foreignTxf?.commodity || "—" }}</div>
              </div>
              <div class="inst-row-metrics">
                <span :class="Number(foreignTxf?.oi_net_volume) >= 0 ? 'up' : 'dn'">{{ formatSigned(foreignTxf?.oi_net_volume) }}</span>
                <span :class="Number(foreignTxf?.oi_net_volume_change) >= 0 ? 'up' : 'dn'">Δ {{ formatSigned(foreignTxf?.oi_net_volume_change) }}</span>
              </div>
            </div>
            <div class="inst-row wide">
              <div>
                <strong>台指選擇權 Put/Call OI 差額</strong>
                <div class="inst-row-sub">外資買賣權未平倉淨額比較</div>
              </div>
              <div class="inst-row-metrics">
                <span :class="txoPutCallBalance >= 0 ? 'up' : 'dn'">{{ formatSigned(txoPutCallBalance) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="institutional-filters">
        <select class="workspace-select" v-model="institutionFilter">
          <option value="">全部法人</option>
          <option v-for="name in institutionOptions" :key="name" :value="name">{{ name }}</option>
        </select>
        <input v-model.trim="keyword" class="compare-input" placeholder="搜尋商品名稱，例如 臺股期貨 / 臺指選擇權">
      </div>

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

import { fmtPrice } from "../utils/formatters";

const props = defineProps({
  data: { type: Object, default: null },
  loading: { type: Boolean, required: true },
  error: { type: String, default: "" },
  selectedDate: { type: String, required: true },
});

defineEmits(["set-date", "shift-date", "refresh"]);

const institutionFilter = ref("");
const keyword = ref("");

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

const foreignTxf = computed(() =>
  (props.data?.futures || []).find((row) => row.commodity === "臺股期貨" && row.institution === "外資") || null,
);

const txoPutCallBalance = computed(() => {
  const targetRows = (props.data?.call_puts || []).filter(
    (row) => row.commodity === "臺指選擇權" && row.institution === "外資",
  );
  const callRow = targetRows.find((row) => row.option_side === "買權");
  const putRow = targetRows.find((row) => row.option_side === "賣權");
  return Number(callRow?.oi_net_volume || 0) - Number(putRow?.oi_net_volume || 0);
});
</script>
