<template>
  <div class="institutional-section">
    <div class="institutional-section-head">
      <div>
        <div class="ind-group-title">TAIFEX 結構化查詢面板</div>
        <div class="institutional-section-note">
          直接查結構化表，可切 section、日期條件、商品與法人，再用圖表看時間序列。
        </div>
      </div>
      <div class="institutional-toolbar-actions institutional-structured-actions">
        <button class="tool-btn" :disabled="loading" @click="$emit('reset')">
          套用主查詢
        </button>
        <button class="tool-btn active" :disabled="loading" @click="$emit('refresh')">
          {{ loading ? "查詢中..." : "查詢資料" }}
        </button>
      </div>
    </div>

    <div class="institutional-card institutional-structured-panel">
      <div class="institutional-kpi-strip institutional-structured-summary">
        <div class="inst-kpi">
          <div class="inst-kpi-label">區段</div>
          <div class="inst-kpi-value">{{ activeSectionLabel }}</div>
          <div class="inst-kpi-change">{{ data?.count ?? 0 }} 筆</div>
        </div>
        <div class="inst-kpi">
          <div class="inst-kpi-label">日期條件</div>
          <div class="inst-kpi-value">{{ dateSummaryLabel }}</div>
          <div class="inst-kpi-change">{{ uniqueDateCount }} 個交易日</div>
        </div>
        <div class="inst-kpi">
          <div class="inst-kpi-label">圖表欄位</div>
          <div class="inst-kpi-value">{{ activeMetricLabel }}</div>
          <div class="inst-kpi-change">分組：{{ activeGroupLabel }}</div>
        </div>
        <div class="inst-kpi">
          <div class="inst-kpi-label">同步模式</div>
          <div class="inst-kpi-value">{{ query?.autoSync ? "跟隨主面板" : "獨立查詢" }}</div>
          <div class="inst-kpi-change">{{ syncHintLabel }}</div>
        </div>
      </div>

      <div class="institutional-structured-controls">
        <label class="institutional-structured-field">
          <span>Section</span>
          <select
            class="workspace-select"
            :value="query?.section || 'futures'"
            @change="emitQueryPatch({ section: $event.target.value })"
          >
            <option v-for="option in SECTION_OPTIONS" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="institutional-structured-field">
          <span>日期模式</span>
          <select
            class="workspace-select"
            :value="query?.dateMode || 'range'"
            @change="emitQueryPatch({ dateMode: $event.target.value })"
          >
            <option value="range">區間</option>
            <option value="date">單日</option>
          </select>
        </label>

        <label v-if="isExactDateMode" class="institutional-structured-field">
          <span>查詢日</span>
          <input
            class="workspace-select institutional-date-input"
            type="date"
            :value="query?.exactDate || selectedDate"
            @change="emitQueryPatch({ exactDate: $event.target.value })"
          >
        </label>

        <template v-else>
          <label class="institutional-structured-field">
            <span>起始日</span>
            <input
              class="workspace-select institutional-date-input"
              type="date"
              :value="query?.startDate || ''"
              @change="emitQueryPatch({ startDate: $event.target.value })"
            >
          </label>
          <label class="institutional-structured-field">
            <span>結束日</span>
            <input
              class="workspace-select institutional-date-input"
              type="date"
              :value="query?.endDate || selectedDate"
              @change="emitQueryPatch({ endDate: $event.target.value })"
            >
          </label>
        </template>

        <label v-if="supportsCommodity" class="institutional-structured-field">
          <span>商品</span>
          <input
            class="compare-input"
            type="text"
            :placeholder="commodityPlaceholder"
            :value="query?.commodity || ''"
            @input="emitQueryPatch({ commodity: $event.target.value })"
          >
        </label>

        <label class="institutional-structured-field">
          <span>法人</span>
          <input
            class="compare-input"
            type="text"
            placeholder="外資 / 投信 / 自營商"
            :value="query?.institution || ''"
            @input="emitQueryPatch({ institution: $event.target.value })"
          >
        </label>

        <label v-if="supportsOptionSide" class="institutional-structured-field">
          <span>權別</span>
          <select
            class="workspace-select"
            :value="query?.optionSide || ''"
            @change="emitQueryPatch({ optionSide: $event.target.value })"
          >
            <option value="">全部</option>
            <option value="買權">買權</option>
            <option value="賣權">賣權</option>
          </select>
        </label>

        <label class="institutional-structured-field">
          <span>筆數上限</span>
          <input
            class="workspace-select"
            type="number"
            min="1"
            max="1000"
            :value="query?.limit || 200"
            @change="emitQueryPatch({ limit: Number($event.target.value) || 200 })"
          >
        </label>

        <label class="institutional-structured-field">
          <span>圖表欄位</span>
          <select
            class="workspace-select"
            :value="activeMetric"
            @change="selectedMetric = $event.target.value"
          >
            <option v-for="option in metricOptions" :key="option.key" :value="option.key">
              {{ option.label }}
            </option>
          </select>
        </label>

        <label class="institutional-structured-field">
          <span>圖表分組</span>
          <select
            class="workspace-select"
            :value="activeGroupKey"
            @change="selectedGroupBy = $event.target.value"
          >
            <option v-for="option in groupOptions" :key="option.key" :value="option.key">
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>

      <div class="institutional-structured-note">
        {{ controlsHint }}
      </div>

      <div v-if="error" class="institutional-inline-error institutional-structured-inline">{{ error }}</div>
      <div v-else-if="loading" class="institutional-inline-loading institutional-structured-inline">
        正在查詢 TAIFEX 結構化資料...
      </div>

      <InstitutionalTrendChart
        v-if="hasChartMetric"
        title="結構化時間序列"
        :subtitle="chartSubtitle"
        :points="chartPoints"
        :series="chartSeries"
        :value-format="activeMetricFormat"
      />
      <div v-else class="institutional-empty institutional-empty-compact">
        這個 section 目前沒有可直接畫成數值時間序列的欄位。
      </div>

      <div class="institutional-section-head institutional-structured-table-head">
        <div>
          <div class="ind-group-title">查詢結果</div>
          <div class="institutional-section-note">
            目前顯示 {{ displayRows.length }} / {{ data?.count ?? 0 }} 筆，圖表以 resolved_date 聚合。
          </div>
        </div>
      </div>

      <div class="institutional-table-wrap">
        <table class="institutional-table institutional-structured-table">
          <thead>
            <tr>
              <th v-for="column in tableColumns" :key="column.key" :class="column.align === 'left' ? 'is-left' : ''">
                {{ column.label }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in displayRows" :key="buildRowKey(row, index)">
              <td
                v-for="column in tableColumns"
                :key="`${buildRowKey(row, index)}-${column.key}`"
                :class="[column.align === 'left' ? 'is-left' : '', toneClass(row[column.key], column)]"
              >
                {{ formatCellValue(row[column.key], column) }}
              </td>
            </tr>
            <tr v-if="!displayRows.length">
              <td :colspan="tableColumns.length || 1">
                <div class="institutional-empty institutional-empty-compact">
                  目前查詢條件還沒有回傳資料。
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import InstitutionalTrendChart from "../InstitutionalTrendChart.vue";
import { fmtTwMoney } from "../../utils/formatters";

const SECTION_OPTIONS = [
  { value: "meta", label: "Meta" },
  { value: "overview", label: "Overview" },
  { value: "futures", label: "Futures" },
  { value: "options", label: "Options" },
  { value: "call_puts", label: "Call / Put" },
  { value: "cash_summary", label: "Cash Summary" },
];

const SECTION_LABELS = Object.fromEntries(SECTION_OPTIONS.map((item) => [item.value, item.label]));
const SECTION_COLUMN_MAP = {
  meta: [
    { key: "resolved_date", label: "資料日", align: "left", type: "date" },
    { key: "query_date", label: "查詢日", align: "left", type: "date" },
    { key: "previous_date", label: "對比日", align: "left", type: "date" },
    { key: "default_futures_commodity", label: "預設期貨", align: "left", type: "text" },
    { key: "default_options_commodity", label: "預設選擇權", align: "left", type: "text" },
    { key: "cash_summary_source", label: "現貨來源", align: "left", type: "text" },
    { key: "cash_summary_warning", label: "備註", align: "left", type: "text" },
  ],
  overview: [
    { key: "resolved_date", label: "資料日", align: "left", type: "date" },
    { key: "institution", label: "法人", align: "left", type: "text" },
    { key: "trade_net_futures_volume", label: "期貨淨口數", align: "right", type: "number", signed: true },
    { key: "trade_net_options_volume", label: "選擇權淨口數", align: "right", type: "number", signed: true },
    { key: "trade_net_futures_amount", label: "期貨淨金額", align: "right", type: "amount", signed: true },
    { key: "trade_net_options_amount", label: "選擇權淨金額", align: "right", type: "amount", signed: true },
  ],
  futures: [
    { key: "resolved_date", label: "資料日", align: "left", type: "date" },
    { key: "commodity", label: "商品", align: "left", type: "text" },
    { key: "institution", label: "法人", align: "left", type: "text" },
    { key: "trade_net_volume", label: "交易淨口數", align: "right", type: "number", signed: true },
    { key: "oi_net_volume", label: "未平倉淨口數", align: "right", type: "number", signed: true },
    { key: "trade_net_amount", label: "交易淨金額", align: "right", type: "amount", signed: true },
    { key: "oi_net_amount", label: "未平倉淨金額", align: "right", type: "amount", signed: true },
    { key: "oi_net_volume_change", label: "未平倉變化", align: "right", type: "number", signed: true },
  ],
  options: [
    { key: "resolved_date", label: "資料日", align: "left", type: "date" },
    { key: "commodity", label: "商品", align: "left", type: "text" },
    { key: "institution", label: "法人", align: "left", type: "text" },
    { key: "trade_net_volume", label: "交易淨口數", align: "right", type: "number", signed: true },
    { key: "oi_net_volume", label: "未平倉淨口數", align: "right", type: "number", signed: true },
    { key: "trade_net_amount", label: "交易淨金額", align: "right", type: "amount", signed: true },
    { key: "oi_net_amount", label: "未平倉淨金額", align: "right", type: "amount", signed: true },
    { key: "oi_net_volume_change", label: "未平倉變化", align: "right", type: "number", signed: true },
  ],
  call_puts: [
    { key: "resolved_date", label: "資料日", align: "left", type: "date" },
    { key: "commodity", label: "商品", align: "left", type: "text" },
    { key: "option_side", label: "權別", align: "left", type: "text" },
    { key: "institution", label: "法人", align: "left", type: "text" },
    { key: "trade_net_volume", label: "交易買賣差", align: "right", type: "number", signed: true },
    { key: "oi_net_volume", label: "未平倉買賣差", align: "right", type: "number", signed: true },
    { key: "trade_net_amount", label: "交易淨金額", align: "right", type: "amount", signed: true },
    { key: "oi_net_amount", label: "未平倉淨金額", align: "right", type: "amount", signed: true },
    { key: "oi_net_volume_change", label: "未平倉變化", align: "right", type: "number", signed: true },
  ],
  cash_summary: [
    { key: "resolved_date", label: "資料日", align: "left", type: "date" },
    { key: "institution", label: "法人", align: "left", type: "text" },
    { key: "buy_amount", label: "買進金額", align: "right", type: "amount" },
    { key: "sell_amount", label: "賣出金額", align: "right", type: "amount" },
    { key: "net_amount", label: "買賣超金額", align: "right", type: "amount", signed: true },
    { key: "net_amount_change", label: "買賣超變化", align: "right", type: "amount", signed: true },
  ],
};

const METRIC_LABELS = {
  trade_long_futures_volume: "期貨多方口數",
  trade_long_options_volume: "選擇權多方口數",
  trade_short_futures_volume: "期貨空方口數",
  trade_short_options_volume: "選擇權空方口數",
  trade_net_futures_volume: "期貨淨口數",
  trade_net_options_volume: "選擇權淨口數",
  trade_net_futures_amount: "期貨淨金額",
  trade_net_options_amount: "選擇權淨金額",
  trade_net_futures_volume_change: "期貨淨口數變化",
  trade_net_options_volume_change: "選擇權淨口數變化",
  trade_net_volume: "交易淨口數",
  trade_net_amount: "交易淨金額",
  oi_net_volume: "未平倉淨口數",
  oi_net_amount: "未平倉淨金額",
  trade_net_volume_change: "交易淨口數變化",
  trade_net_amount_change: "交易淨金額變化",
  oi_net_volume_change: "未平倉淨口數變化",
  oi_net_amount_change: "未平倉淨金額變化",
  buy_amount: "買進金額",
  sell_amount: "賣出金額",
  net_amount: "買賣超金額",
  net_amount_change: "買賣超變化",
};

const METRIC_PRIORITY = {
  overview: ["trade_net_futures_volume", "trade_net_options_volume", "trade_net_futures_amount"],
  futures: ["oi_net_volume", "trade_net_volume", "oi_net_amount"],
  options: ["oi_net_volume", "trade_net_volume", "oi_net_amount"],
  call_puts: ["oi_net_volume", "trade_net_volume", "oi_net_amount"],
  cash_summary: ["net_amount", "net_amount_change", "buy_amount"],
};

const GROUP_COLOR_PALETTE = ["#00d9a3", "#ffd166", "#3b8bff", "#9b6dff", "#ff8c42", "#ff4d6a"];
const FILTERABLE_COMMODITY_SECTIONS = new Set(["futures", "options", "call_puts"]);
const FILTERABLE_OPTION_SIDE_SECTIONS = new Set(["call_puts"]);
const NUMERIC_IGNORE_FIELDS = new Set(["rank"]);

const props = defineProps({
  query: { type: Object, default: () => ({}) },
  data: { type: Object, default: () => ({ section: "futures", count: 0, filters: {}, items: [] }) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: "" },
  selectedDate: { type: String, default: "" },
  selectedFuturesCommodity: { type: String, default: "" },
  selectedOptionsCommodity: { type: String, default: "" },
});

const emit = defineEmits(["update-query", "refresh", "reset"]);

const selectedMetric = ref("");
const selectedGroupBy = ref("");

const sectionValue = computed(() => String(props.query?.section || props.data?.section || "futures"));
const activeSectionLabel = computed(() => SECTION_LABELS[sectionValue.value] || sectionValue.value);
const items = computed(() => (Array.isArray(props.data?.items) ? props.data.items : []));
const supportsCommodity = computed(() => FILTERABLE_COMMODITY_SECTIONS.has(sectionValue.value));
const supportsOptionSide = computed(() => FILTERABLE_OPTION_SIDE_SECTIONS.has(sectionValue.value));
const isExactDateMode = computed(() => String(props.query?.dateMode || "range") === "date");
const uniqueDateCount = computed(() => new Set(items.value.map((row) => row?.resolved_date).filter(Boolean)).size);

const metricOptions = computed(() => {
  const fieldMap = new Map();
  for (const row of items.value) {
    for (const [key, value] of Object.entries(row || {})) {
      if (NUMERIC_IGNORE_FIELDS.has(key)) continue;
      if (!Number.isFinite(Number(value))) continue;
      fieldMap.set(key, {
        key,
        label: METRIC_LABELS[key] || humanizeMetricKey(key),
        format: key.includes("amount") ? "amount" : "number",
      });
    }
  }

  const options = [...fieldMap.values()];
  const priority = METRIC_PRIORITY[sectionValue.value] || [];
  options.sort((left, right) => {
    const leftPriority = priority.indexOf(left.key);
    const rightPriority = priority.indexOf(right.key);
    if (leftPriority !== -1 || rightPriority !== -1) {
      if (leftPriority === -1) return 1;
      if (rightPriority === -1) return -1;
      return leftPriority - rightPriority;
    }
    return left.label.localeCompare(right.label);
  });
  return options;
});

const activeMetric = computed(() => {
  if (metricOptions.value.some((item) => item.key === selectedMetric.value)) return selectedMetric.value;
  return metricOptions.value[0]?.key || "";
});
const activeMetricLabel = computed(() => metricOptions.value.find((item) => item.key === activeMetric.value)?.label || "無");
const activeMetricFormat = computed(() => metricOptions.value.find((item) => item.key === activeMetric.value)?.format || "number");
const hasChartMetric = computed(() => Boolean(activeMetric.value));

const groupOptions = computed(() => {
  const options = [{ key: "all", label: "合計" }];
  if (items.value.some((row) => row?.institution)) options.push({ key: "institution", label: "法人" });
  if (items.value.some((row) => row?.commodity)) options.push({ key: "commodity", label: "商品" });
  if (items.value.some((row) => row?.option_side)) options.push({ key: "option_side", label: "權別" });
  return options;
});

const activeGroupKey = computed(() => {
  if (groupOptions.value.some((item) => item.key === selectedGroupBy.value)) return selectedGroupBy.value;
  if (props.query?.institution && groupOptions.value.some((item) => item.key === "commodity")) return "commodity";
  if (props.query?.commodity && groupOptions.value.some((item) => item.key === "institution")) return "institution";
  if (groupOptions.value.some((item) => item.key === "institution")) return "institution";
  return "all";
});
const activeGroupLabel = computed(() => groupOptions.value.find((item) => item.key === activeGroupKey.value)?.label || "合計");

const chartPoints = computed(() => {
  if (!activeMetric.value) return [];
  const groupedByDate = new Map();
  for (const row of items.value) {
    const date = row?.resolved_date || row?.query_date || row?.previous_date;
    const metricValue = Number(row?.[activeMetric.value]);
    if (!date || !Number.isFinite(metricValue)) continue;
    const seriesKey = resolveSeriesKey(row, activeGroupKey.value);
    const point = groupedByDate.get(date) || { date };
    point[seriesKey] = Number(point[seriesKey] || 0) + metricValue;
    groupedByDate.set(date, point);
  }
  return [...groupedByDate.values()].sort((left, right) => String(left.date).localeCompare(String(right.date)));
});

const chartSeries = computed(() => {
  const scoreByKey = new Map();
  for (const point of chartPoints.value) {
    for (const [key, value] of Object.entries(point)) {
      if (key === "date" || !Number.isFinite(Number(value))) continue;
      const score = Math.max(Math.abs(Number(value)), Number(scoreByKey.get(key) || 0));
      scoreByKey.set(key, score);
    }
  }
  return [...scoreByKey.entries()]
    .sort((left, right) => right[1] - left[1])
    .slice(0, 6)
    .map(([key], index) => ({
      key,
      label: key,
      color: GROUP_COLOR_PALETTE[index % GROUP_COLOR_PALETTE.length],
    }));
});

const chartSubtitle = computed(() => {
  if (!hasChartMetric.value) return "";
  const parts = [`欄位：${activeMetricLabel.value}`, `分組：${activeGroupLabel.value}`];
  if (props.query?.commodity) parts.push(`商品：${props.query.commodity}`);
  if (props.query?.institution) parts.push(`法人：${props.query.institution}`);
  if (props.query?.optionSide) parts.push(`權別：${props.query.optionSide}`);
  return parts.join(" / ");
});

const tableColumns = computed(() => SECTION_COLUMN_MAP[sectionValue.value] || SECTION_COLUMN_MAP.futures);
const displayRows = computed(() => items.value.slice(0, 300));

const dateSummaryLabel = computed(() => {
  if (isExactDateMode.value) return props.query?.exactDate || props.selectedDate || "未設定";
  const start = props.query?.startDate || "未設定";
  const end = props.query?.endDate || props.selectedDate || "未設定";
  return `${start} → ${end}`;
});

const commodityPlaceholder = computed(() => {
  if (sectionValue.value === "futures") return props.selectedFuturesCommodity || "例如：臺股期貨";
  return props.selectedOptionsCommodity || "例如：臺指選擇權";
});

const syncHintLabel = computed(() => (
  props.query?.autoSync
    ? "切換主面板日期或商品時會一起更新"
    : "手動調整後會維持自己的查詢條件"
));

const controlsHint = computed(() => {
  if (props.query?.autoSync) {
    return "目前面板會跟隨上方的主查詢日與主商品。若你手動改條件，它就會切成獨立查詢。";
  }
  return "你現在看的已經是獨立查詢條件；按「套用主查詢」就能回到跟隨主面板。";
});

function emitQueryPatch(patch) {
  emit("update-query", patch);
}

function humanizeMetricKey(key) {
  return String(key || "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function resolveSeriesKey(row, groupKey) {
  if (groupKey === "institution" && row?.institution) return row.institution;
  if (groupKey === "commodity" && row?.commodity) return row.commodity;
  if (groupKey === "option_side" && row?.option_side) return row.option_side;
  return "合計";
}

function buildRowKey(row, index) {
  return [
    row?.resolved_date || row?.query_date || "row",
    row?.commodity || "all",
    row?.option_side || "all",
    row?.institution || "all",
    index,
  ].join("-");
}

function toneClass(value, column) {
  if (!column?.signed) return "";
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "";
  return numeric > 0 ? "up" : "dn";
}

function formatCellValue(value, column) {
  if (value == null || value === "") return "—";
  if (column?.type === "date") return String(value);
  if (column?.type === "text") return String(value);
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  if (column?.type === "amount") {
    return fmtTwMoney(numeric, { signed: Boolean(column?.signed), empty: "0" });
  }
  if (column?.signed) {
    return `${numeric >= 0 ? "+" : "-"}${Math.abs(Math.round(numeric)).toLocaleString()}`;
  }
  return Math.round(numeric).toLocaleString();
}
</script>
