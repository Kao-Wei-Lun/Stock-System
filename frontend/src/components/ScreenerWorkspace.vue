<template>
  <div class="screen-shell">
    <section class="screen-filters">
      <div class="screen-head">
        <div>
          <div class="screen-title">選股器</div>
          <div class="screen-subtitle">結合技術面、事件、基本面與台股籌碼的工作區</div>
        </div>
        <button class="screen-btn primary" :disabled="loading" @click="$emit('run-screen')">
          {{ loading ? "篩選中..." : "執行篩選" }}
        </button>
      </div>

      <div class="filter-grid">
        <label class="filter-row">
          <span>市場</span>
          <select :value="filters.market" @change="$emit('update-filter', { key: 'market', value: $event.target.value })">
            <option value="ALL">全部</option>
            <option value="US">US</option>
            <option value="TW">TW</option>
            <option value="HK">HK</option>
            <option value="INDEX">INDEX</option>
          </select>
        </label>
        <label class="filter-row">
          <span>關鍵字</span>
          <input :value="filters.search" @input="$emit('update-filter', { key: 'search', value: $event.target.value })" placeholder="ticker / sector" />
        </label>
        <label class="filter-row">
          <span>產業</span>
          <input :value="filters.sector" @input="$emit('update-filter', { key: 'sector', value: $event.target.value })" placeholder="Semiconductor" />
        </label>
        <label class="filter-row">
          <span>最低價</span>
          <input type="number" :value="filters.min_price" @input="$emit('update-filter', { key: 'min_price', value: $event.target.value })" />
        </label>
        <label class="filter-row">
          <span>量比下限</span>
          <input type="number" step="0.1" :value="filters.min_volume_ratio" @input="$emit('update-filter', { key: 'min_volume_ratio', value: $event.target.value })" />
        </label>
        <label class="filter-row">
          <span>PE 上限</span>
          <input type="number" step="0.1" :value="filters.max_pe_ratio" @input="$emit('update-filter', { key: 'max_pe_ratio', value: $event.target.value })" />
        </label>
        <label class="filter-row">
          <span>殖利率下限</span>
          <input type="number" step="0.01" :value="filters.min_dividend_yield" @input="$emit('update-filter', { key: 'min_dividend_yield', value: $event.target.value })" />
        </label>
        <label class="filter-row">
          <span>接近 52W 高點</span>
          <input type="number" step="1" :value="filters.near_52w_high_pct" @input="$emit('update-filter', { key: 'near_52w_high_pct', value: $event.target.value })" />
        </label>
        <label class="filter-row">
          <span>事件天數</span>
          <input type="number" step="1" :value="filters.upcoming_event_days" @input="$emit('update-filter', { key: 'upcoming_event_days', value: $event.target.value })" />
        </label>
        <label class="filter-row">
          <span>台股籌碼</span>
          <select :value="filters.chip_bias" @change="$emit('update-filter', { key: 'chip_bias', value: $event.target.value })">
            <option value="any">不限</option>
            <option value="bullish">偏多</option>
            <option value="bearish">偏空</option>
          </select>
        </label>
        <label class="filter-row">
          <span>均線排列</span>
          <select :value="filters.ma_alignment" @change="$emit('update-filter', { key: 'ma_alignment', value: $event.target.value })">
            <option value="any">不限</option>
            <option value="bullish">多頭排列</option>
          </select>
        </label>
        <label class="filter-row">
          <span>排序</span>
          <select :value="filters.sort_by" @change="$emit('update-filter', { key: 'sort_by', value: $event.target.value })">
            <option value="score">綜合分數</option>
            <option value="change_pct">漲跌幅</option>
            <option value="volume_ratio">量比</option>
            <option value="event_date">事件日期</option>
          </select>
        </label>
      </div>
    </section>

    <section class="preset-panel">
      <div class="panel-head">
        <div class="panel-title">篩選模板</div>
        <div class="preset-save">
          <input v-model.trim="presetName" placeholder="儲存目前條件" />
          <button class="screen-btn" @click="savePreset">儲存</button>
        </div>
      </div>
      <div class="preset-list">
        <button
          v-for="preset in presets"
          :key="preset.id"
          type="button"
          class="preset-chip"
          @click="$emit('load-preset', preset)"
        >
          <span>{{ preset.name }}</span>
          <small>{{ preset.description || "自訂模板" }}</small>
          <strong v-if="!preset.builtin" class="preset-delete" @click.stop="$emit('delete-preset', preset.id)">×</strong>
        </button>
      </div>
    </section>

    <section class="result-panel">
      <div class="panel-head">
        <div class="panel-title">結果</div>
        <div class="panel-subtitle">
          {{ results.total || 0 }} 檔符合條件<span v-if="marketContext"> · {{ postureLabel }}</span>
        </div>
      </div>
      <div v-if="marketContext" class="market-context-banner" :class="bannerClass">
        <span class="market-context-pill">{{ riskLabel }}</span>
        <strong>{{ postureLabel }}</strong>
        <span>{{ marketContext.decision_hint }}</span>
      </div>
      <div v-if="results.items?.length" class="result-table-wrap">
        <table class="result-table">
          <thead>
            <tr>
              <th>標的</th>
              <th>市場</th>
              <th>價格</th>
              <th>漲跌幅</th>
              <th>量比</th>
              <th>分數</th>
              <th>事件</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in results.items" :key="item.ticker" :class="{ active: item.ticker === currentTicker }">
              <td>
                <div class="ticker-cell">
                  <strong>{{ item.ticker }}</strong>
                  <small>{{ item.name }}</small>
                </div>
              </td>
              <td>{{ item.market }}</td>
              <td>{{ formatNumber(item.close) }}</td>
              <td :class="Number(item.change_pct || 0) >= 0 ? 'up' : 'dn'">{{ formatSigned(item.change_pct) }}%</td>
              <td>{{ formatNumber(item.volume_ratio) }}</td>
              <td>
                <div class="score-cell">
                  <strong>{{ item.score }}</strong>
                  <small :class="scoreAdjustmentClass(item.macro_adjustment)">
                    {{ formatAdjustment(item.macro_adjustment) }} · Q{{ item.setup_quality ?? "—" }}
                  </small>
                </div>
              </td>
              <td>{{ item.next_event?.event_date || "—" }}</td>
              <td>
                <div class="action-row">
                  <button class="tiny-btn" @click="$emit('open-ticker', item.ticker)">開圖</button>
                  <button class="tiny-btn" @click="$emit('add-watchlist', item.ticker)">自選</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty-state">尚未執行篩選，或目前沒有符合條件的標的。</div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  filters: { type: Object, required: true },
  results: { type: Object, default: () => ({ items: [], total: 0 }) },
  presets: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  currentTicker: { type: String, default: "" },
});

const emit = defineEmits([
  "update-filter",
  "run-screen",
  "save-preset",
  "load-preset",
  "delete-preset",
  "open-ticker",
  "add-watchlist",
]);

const presetName = ref("");
const marketContext = computed(() => props.results?.market_context || null);
const bannerClass = computed(() => `is-${marketContext.value?.trade_posture || "standby"}`);
const postureLabel = computed(() => {
  if (marketContext.value?.trade_posture === "defensive") return "防守控倉";
  if (marketContext.value?.trade_posture === "selective") return "選擇性出手";
  if (marketContext.value?.trade_posture === "offensive") return "偏進攻";
  if (marketContext.value?.trade_posture === "balanced") return "平衡觀察";
  return "暫停判斷";
});
const riskLabel = computed(() => {
  if (marketContext.value?.overall_risk === "high") return "高風險";
  if (marketContext.value?.overall_risk === "medium") return "中風險";
  if (marketContext.value?.overall_risk === "low") return "低風險";
  return "未同步";
});

function formatNumber(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return numeric.toLocaleString("zh-TW", { maximumFractionDigits: 2 });
}

function formatSigned(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}`;
}

function formatAdjustment(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "±0";
  return `${numeric > 0 ? "+" : ""}${numeric}`;
}

function scoreAdjustmentClass(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric === 0) return "";
  return numeric > 0 ? "up" : "dn";
}

function savePreset() {
  if (!presetName.value) return;
  emit("save-preset", presetName.value);
  presetName.value = "";
}
</script>

<style scoped>
.screen-shell {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  background: linear-gradient(180deg, rgba(8, 12, 18, 0.98) 0%, rgba(12, 18, 28, 0.98) 100%);
}

.screen-filters,
.preset-panel,
.result-panel {
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(8, 14, 22, 0.9);
  padding: 16px;
}

.screen-head,
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.screen-title,
.panel-title {
  color: var(--text1);
  font-size: 18px;
  font-weight: 700;
}

.screen-subtitle,
.panel-subtitle {
  color: var(--text3);
  font-size: 12px;
  margin-top: 4px;
}

.screen-btn,
.tiny-btn,
.preset-save input,
.filter-row input,
.filter-row select {
  border-radius: 10px;
  font-size: 12px;
}

.screen-btn,
.tiny-btn {
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text2);
  cursor: pointer;
}

.screen-btn {
  padding: 9px 14px;
}

.screen-btn.primary {
  background: linear-gradient(135deg, rgba(0, 212, 255, 0.18), rgba(255, 140, 66, 0.18));
  color: var(--text1);
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.filter-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--text2);
  font-size: 12px;
}

.filter-row input,
.filter-row select,
.preset-save input {
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text1);
  padding: 10px 12px;
}

.preset-save {
  display: flex;
  gap: 8px;
}

.preset-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.preset-chip {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 180px;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  color: var(--text1);
  cursor: pointer;
  text-align: left;
}

.preset-chip small {
  color: var(--text3);
}

.preset-delete {
  position: absolute;
  top: 8px;
  right: 10px;
  color: var(--text3);
}

.result-table-wrap {
  overflow: auto;
}

.market-context-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text2);
  font-size: 12px;
}

.market-context-banner strong {
  color: var(--text1);
}

.market-context-pill {
  border-radius: 999px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.08);
}

.market-context-banner.is-defensive {
  background: rgba(255, 107, 107, 0.12);
}

.market-context-banner.is-defensive .market-context-pill {
  background: rgba(255, 107, 107, 0.2);
  color: #ffd0d0;
}

.market-context-banner.is-selective,
.market-context-banner.is-balanced {
  background: rgba(255, 209, 102, 0.12);
}

.market-context-banner.is-selective .market-context-pill,
.market-context-banner.is-balanced .market-context-pill {
  background: rgba(255, 209, 102, 0.2);
  color: #ffe2a6;
}

.market-context-banner.is-offensive {
  background: rgba(0, 217, 163, 0.12);
}

.market-context-banner.is-offensive .market-context-pill {
  background: rgba(0, 217, 163, 0.2);
  color: #bfffea;
}

.result-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.result-table th,
.result-table td {
  padding: 10px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  color: var(--text2);
}

.result-table th {
  text-align: left;
  color: var(--text3);
  font-weight: 600;
}

.result-table tr.active {
  background: rgba(0, 212, 255, 0.05);
}

.ticker-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ticker-cell strong {
  color: var(--text1);
}

.ticker-cell small {
  color: var(--text3);
}

.up {
  color: var(--green);
}

.dn {
  color: var(--red);
}

.action-row {
  display: flex;
  gap: 6px;
}

.score-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.score-cell strong {
  color: var(--text1);
}

.score-cell small {
  color: var(--text3);
}

.tiny-btn {
  padding: 6px 9px;
}

.empty-state {
  color: var(--text3);
  font-size: 12px;
  padding: 14px 0 4px;
}

@media (max-width: 820px) {
  .screen-shell {
    gap: 12px;
    padding: 12px;
  }

  .screen-filters,
  .preset-panel,
  .result-panel {
    padding: 12px;
  }

  .screen-head,
  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .screen-btn.primary {
    width: 100%;
  }

  .filter-grid {
    grid-template-columns: 1fr;
  }

  .preset-save {
    width: 100%;
    flex-direction: column;
  }

  .preset-save input,
  .preset-save .screen-btn {
    width: 100%;
  }

  .preset-list {
    flex-direction: column;
  }

  .preset-chip {
    min-width: 0;
    width: 100%;
  }
}
</style>
