<template>
  <div>
    <div v-if="journalStats" class="journal-card">
      <div class="bt-section-title">統計摘要</div>
      <div class="bt-metric"><span>總筆數</span><span>{{ journalStats.total_entries }}</span></div>
      <div class="bt-metric"><span>已平倉</span><span>{{ journalStats.closed_entries }}</span></div>
      <div class="bt-metric"><span>未平倉</span><span>{{ journalStats.open_entries }}</span></div>
      <div class="bt-metric"><span>勝率</span><span :class="journalStats.win_rate >= 50 ? 'up' : 'dn'">{{ Number(journalStats.win_rate || 0).toFixed(1) }}%</span></div>
      <div class="bt-metric"><span>淨損益</span><span :class="Number(journalStats.net_pnl || 0) >= 0 ? 'up' : 'dn'">${{ Math.round(Number(journalStats.net_pnl || 0)).toLocaleString() }}</span></div>
      <div class="bt-metric"><span>平均報酬</span><span :class="Number(journalStats.avg_return_pct || 0) >= 0 ? 'up' : 'dn'">{{ Number(journalStats.avg_return_pct || 0).toFixed(2) }}%</span></div>

      <div v-if="journalStats.source_breakdown?.length" class="journal-analytics-card">
        <div class="bt-section-title">來源拆解</div>
        <div
          v-for="item in topSourceBreakdown"
          :key="`source-${item.key}`"
          class="journal-analytics-row-wrap"
        >
          <button
            type="button"
            class="journal-analytics-row"
            :data-testid="`journal-source-${item.key}`"
            @click="$emit('apply-journal-filter-preset', buildJournalTagPreset(`來源:${item.key}`))"
          >
            <div>
              <div>{{ item.key }}</div>
              <div class="bt-trade-sub">{{ item.closed_count }} 筆平倉 · 勝率 {{ Number(item.win_rate || 0).toFixed(1) }}%</div>
            </div>
            <div :class="Number(item.net_pnl || 0) >= 0 ? 'up' : 'dn'">
              {{ Number(item.net_pnl || 0) >= 0 ? "+" : "" }}${{ Math.round(Number(item.net_pnl || 0)).toLocaleString() }}
            </div>
          </button>
          <button
            type="button"
            class="journal-analytics-save"
            :data-testid="`journal-source-save-${item.key}`"
            @click="$emit('save-journal-filter-preset', buildJournalQuickSaveDraft(`來源：${item.key}`, buildJournalTagPreset(`來源:${item.key}`), '由來源拆解快速建立'))"
          >
            存
          </button>
        </div>
      </div>

      <div v-if="journalStats.strategy_breakdown?.length" class="journal-analytics-card">
        <div class="bt-section-title">策略拆解</div>
        <div
          v-for="item in topStrategyBreakdown"
          :key="`strategy-${item.key}`"
          class="journal-analytics-row-wrap"
        >
          <button
            type="button"
            class="journal-analytics-row"
            :data-testid="`journal-strategy-${item.key}`"
            @click="$emit('apply-journal-filter-preset', buildJournalStrategyPreset(item.key))"
          >
            <div>
              <div>{{ item.key }}</div>
              <div class="bt-trade-sub">{{ item.count }} 筆 · 勝率 {{ Number(item.win_rate || 0).toFixed(1) }}%</div>
            </div>
            <div :class="Number(item.net_pnl || 0) >= 0 ? 'up' : 'dn'">
              {{ Number(item.net_pnl || 0) >= 0 ? "+" : "" }}${{ Math.round(Number(item.net_pnl || 0)).toLocaleString() }}
            </div>
          </button>
          <button
            type="button"
            class="journal-analytics-save"
            :data-testid="`journal-strategy-save-${item.key}`"
            @click="$emit('save-journal-filter-preset', buildJournalQuickSaveDraft(`策略：${item.key}`, buildJournalStrategyPreset(item.key), '由策略拆解快速建立'))"
          >
            存
          </button>
        </div>
      </div>

      <div v-if="journalStats.market_posture_breakdown?.length" class="journal-analytics-card">
        <div class="bt-section-title">市場情境</div>
        <div
          v-for="item in topMarketPostureBreakdown"
          :key="`posture-${item.key}`"
          class="journal-analytics-row-wrap"
        >
          <button
            type="button"
            class="journal-analytics-row"
            :data-testid="`journal-posture-${item.key}`"
            @click="$emit('apply-journal-filter-preset', buildJournalTagPreset(`市場:${item.key}`))"
          >
            <div>
              <div>{{ item.key }}</div>
              <div class="bt-trade-sub">{{ item.count }} 筆 · 平均報酬 {{ Number(item.avg_return_pct || 0).toFixed(2) }}%</div>
            </div>
            <div :class="Number(item.net_pnl || 0) >= 0 ? 'up' : 'dn'">
              {{ Number(item.net_pnl || 0) >= 0 ? "+" : "" }}${{ Math.round(Number(item.net_pnl || 0)).toLocaleString() }}
            </div>
          </button>
          <button
            type="button"
            class="journal-analytics-save"
            :data-testid="`journal-posture-save-${item.key}`"
            @click="$emit('save-journal-filter-preset', buildJournalQuickSaveDraft(`市場：${item.key}`, buildJournalTagPreset(`市場:${item.key}`), '由市場情境快速建立'))"
          >
            存
          </button>
        </div>
      </div>

      <div v-if="journalStats.tag_breakdown?.length" class="journal-analytics-card">
        <div class="bt-section-title">高頻標籤</div>
        <div
          v-for="item in topTagBreakdown"
          :key="`tag-${item.key}`"
          class="journal-analytics-row-wrap"
        >
          <button
            type="button"
            class="journal-analytics-row"
            :data-testid="`journal-tag-${item.key}`"
            @click="$emit('apply-journal-filter-preset', buildJournalTagPreset(item.key))"
          >
            <div>
              <div>{{ item.key }}</div>
              <div class="bt-trade-sub">{{ item.count }} 筆 · 勝率 {{ Number(item.win_rate || 0).toFixed(1) }}%</div>
            </div>
            <div :class="Number(item.net_pnl || 0) >= 0 ? 'up' : 'dn'">
              {{ Number(item.net_pnl || 0) >= 0 ? "+" : "" }}${{ Math.round(Number(item.net_pnl || 0)).toLocaleString() }}
            </div>
          </button>
          <button
            type="button"
            class="journal-analytics-save"
            :data-testid="`journal-tag-save-${item.key}`"
            @click="$emit('save-journal-filter-preset', buildJournalQuickSaveDraft(`標籤：${item.key}`, buildJournalTagPreset(item.key), '由高頻標籤快速建立'))"
          >
            存
          </button>
        </div>
      </div>
    </div>

    <div class="journal-card">
      <div class="bt-section-title">歷史紀錄</div>
      <div v-if="journalEntries.length">
        <button
          v-for="entry in journalEntryRows"
          :key="entry.id"
          type="button"
          class="bt-history-row"
          :data-testid="`journal-history-entry-${entry.id}`"
          @click="$emit('select-journal-entry', entry.id)"
        >
          <span>
            <div>{{ entry.ticker }} · {{ entry.direction }} · {{ entry.strategy_code || "manual" }}</div>
            <div class="bt-trade-sub">{{ entry.entry_time }}</div>
            <div v-if="getJournalEntryQuickFilters(entry).length" class="journal-entry-quick-filters">
              <span
                v-for="chip in getJournalEntryQuickFilters(entry)"
                :key="`${entry.id}-${chip.kind}-${chip.value}`"
                class="journal-entry-quick-filter-group"
              >
                <span
                  class="journal-entry-meta-chip"
                  :data-testid="`journal-entry-${chip.kind}-${entry.id}-${chip.value}`"
                  @click.stop="$emit('apply-journal-filter-preset', chip.preset)"
                >
                  {{ chip.label }}
                </span>
                <span
                  class="journal-entry-meta-save"
                  :data-testid="`journal-entry-save-${chip.kind}-${entry.id}-${chip.value}`"
                  @click.stop="$emit('save-journal-filter-preset', chip.saveDraft)"
                >
                  存
                </span>
              </span>
            </div>
            <div v-if="getJournalEntryPlainTags(entry).length" class="journal-entry-tags">
              <span
                v-for="tag in getJournalEntryPlainTags(entry).slice(0, 4)"
                :key="`${entry.id}-${tag}`"
                class="journal-entry-tag"
                :data-testid="`journal-entry-tag-${entry.id}-${tag}`"
                @click.stop="$emit('apply-journal-filter-preset', buildJournalTagPreset(tag))"
              >
                {{ tag }}
              </span>
            </div>
            <div v-else-if="!getJournalEntryQuickFilters(entry).length" class="bt-trade-sub">無標籤</div>
          </span>
          <span :class="Number(entry.result?.pnl || 0) >= 0 ? 'up' : 'dn'">
            {{ Number(entry.result?.pnl || 0) >= 0 ? "+" : "" }}${{ Math.round(Number(entry.result?.pnl || 0)).toLocaleString() }}
          </span>
        </button>
      </div>
      <div v-else class="bt-history-empty">尚無交易日誌</div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  journalStats: { type: Object, default: null },
  journalEntries: { type: Array, default: () => [] },
  journalEntryRows: { type: Array, default: () => [] },
  topSourceBreakdown: { type: Array, default: () => [] },
  topStrategyBreakdown: { type: Array, default: () => [] },
  topMarketPostureBreakdown: { type: Array, default: () => [] },
  topTagBreakdown: { type: Array, default: () => [] },
  buildJournalTagPreset: { type: Function, required: true },
  buildJournalStrategyPreset: { type: Function, required: true },
  buildJournalQuickSaveDraft: { type: Function, required: true },
  getJournalEntryQuickFilters: { type: Function, required: true },
  getJournalEntryPlainTags: { type: Function, required: true },
});

defineEmits([
  "apply-journal-filter-preset",
  "save-journal-filter-preset",
  "select-journal-entry",
]);
</script>
