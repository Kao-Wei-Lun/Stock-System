<template>
<div class="rp-content">
      <div class="bt-section-title">交易日誌</div>
      <div class="bt-row">
        <div class="bt-label">範圍</div>
        <select class="bt-sel" :value="journalFilterScope" @change="$emit('update-journal-filter', { key: 'scope', value: $event.target.value })">
          <option value="ticker">目前標的</option>
          <option value="all">全部紀錄</option>
        </select>
      </div>
      <div class="bt-row"><div class="bt-label">市場</div><input class="bt-inp" :value="journalFilters.market" @input="$emit('update-journal-filter', { key: 'market', value: $event.target.value })" placeholder="US / TW / HK"></div>
      <div class="bt-row"><div class="bt-label">策略篩選</div><input class="bt-inp" :value="journalFilters.strategy_code" @input="$emit('update-journal-filter', { key: 'strategy_code', value: $event.target.value })" placeholder="breakout"></div>
      <div class="bt-row"><div class="bt-label">標籤篩選</div><input class="bt-inp" :value="journalFilters.tag" @input="$emit('update-journal-filter', { key: 'tag', value: $event.target.value })" placeholder="swing"></div>
      <div class="bt-row"><div class="bt-label">關鍵字</div><input class="bt-inp" :value="journalFilters.search" @input="$emit('update-journal-filter', { key: 'search', value: $event.target.value })" placeholder="review / note"></div>

      <div class="journal-card">
        <div class="bt-section-title">篩選模板</div>
        <div class="journal-preset-save">
          <input
            v-model.trim="journalPresetName"
            class="bt-inp"
            placeholder="儲存目前篩選"
            data-testid="journal-preset-name"
            @keydown.enter.prevent="saveJournalPreset"
          />
          <input
            v-model.trim="journalPresetDescription"
            class="bt-inp"
            placeholder="模板說明"
            data-testid="journal-preset-description"
            @keydown.enter.prevent="saveJournalPreset"
          />
          <button
            type="button"
            class="sync-btn"
            data-testid="journal-preset-save"
            @click="saveJournalPreset"
          >
            {{ editingJournalPresetId ? "更新" : "儲存" }}
          </button>
          <button
            v-if="editingJournalPresetId"
            type="button"
            class="sync-btn"
            data-testid="journal-preset-cancel"
            @click="resetJournalPresetEditor"
          >
            取消
          </button>
        </div>
        <div v-if="journalFilterPresets.length" class="journal-preset-grid">
          <button
            v-for="preset in journalFilterPresets"
            :key="preset.id"
            type="button"
            :class="['preset-chip', 'journal-preset-chip', { 'journal-preset-active': isJournalPresetActive(preset) }]"
            :data-testid="`journal-preset-${preset.id}`"
            @click="$emit('load-journal-filter-preset', preset)"
          >
            <span>{{ preset.name }}</span>
            <small>{{ preset.description || "自訂模板" }}</small>
            <small>
              {{ preset.scope === "all" ? "全部紀錄" : "目前標的" }}
              · 已用 {{ Number(preset.use_count || 0) }}
              <template v-if="preset.last_used_at"> · {{ formatDateTime(preset.last_used_at) }}</template>
            </small>
            <span class="journal-preset-actions">
              <strong
                class="journal-preset-edit"
                :data-testid="`journal-preset-edit-${preset.id}`"
                @click.stop="startEditingJournalPreset(preset)"
              >
                編
              </strong>
              <strong
                class="journal-preset-delete"
                :data-testid="`journal-preset-delete-${preset.id}`"
                @click.stop="$emit('delete-journal-filter-preset', preset.id)"
              >
                ×
              </strong>
            </span>
          </button>
        </div>
        <div v-else class="bt-history-empty">尚無篩選模板</div>
      </div>

      <div v-if="journalPresetResultSummary" class="journal-card journal-preset-result-card" data-testid="journal-preset-result-summary">
        <div class="bt-section-title">套用結果</div>
        <div class="bt-trade-row">
          <div>
            <div>{{ journalPresetResultSummary.name }}</div>
            <div class="bt-trade-sub">{{ journalPresetResultSummary.description }}</div>
          </div>
          <div class="bt-trade-sub">{{ journalPresetResultSummary.scopeLabel }}</div>
        </div>
        <div class="bt-metric">
          <span>命中筆數</span>
          <span>{{ journalPresetResultSummary.totalEntries }}</span>
        </div>
        <div class="bt-metric">
          <span>目前顯示</span>
          <span>{{ journalPresetResultSummary.visibleEntries }}</span>
        </div>
        <div class="bt-metric">
          <span>已平倉 / 未平倉</span>
          <span>{{ journalPresetResultSummary.closedEntries }} / {{ journalPresetResultSummary.openEntries }}</span>
        </div>
        <div class="bt-metric">
          <span>勝率</span>
          <span :class="journalPresetResultSummary.winRate >= 50 ? 'up' : 'dn'">{{ journalPresetResultSummary.winRate.toFixed(1) }}%</span>
        </div>
        <div class="bt-metric">
          <span>淨損益</span>
          <span :class="journalPresetResultSummary.netPnl >= 0 ? 'up' : 'dn'">
            {{ journalPresetResultSummary.netPnl >= 0 ? "+" : "" }}${{ Math.round(journalPresetResultSummary.netPnl).toLocaleString() }}
          </span>
        </div>
        <div class="bt-metric">
          <span>平均報酬</span>
          <span :class="journalPresetResultSummary.avgReturnPct >= 0 ? 'up' : 'dn'">{{ journalPresetResultSummary.avgReturnPct.toFixed(2) }}%</span>
        </div>
        <button
          v-if="journalPresetLatestEntry"
          type="button"
          class="journal-preset-latest-hit"
          data-testid="journal-preset-latest-entry"
          @click="$emit('select-journal-entry', journalPresetLatestEntry.id)"
        >
          <div>
            <div>最近命中</div>
            <div class="bt-trade-sub">
              {{ journalPresetLatestEntry.ticker }} · {{ journalPresetLatestEntry.direction }} · {{ journalPresetLatestEntry.strategy_code || "manual" }}
            </div>
            <div class="bt-trade-sub">{{ formatDateTime(journalPresetLatestEntry.entry_time) }}</div>
          </div>
          <div :class="Number(journalPresetLatestEntry.result?.pnl || 0) >= 0 ? 'up' : 'dn'">
            {{ Number(journalPresetLatestEntry.result?.pnl || 0) >= 0 ? "+" : "" }}${{ Math.round(Number(journalPresetLatestEntry.result?.pnl || 0)).toLocaleString() }}
          </div>
        </button>
        <button
          v-if="journalResultToggleVisible"
          type="button"
          class="journal-preset-expand-btn"
          data-testid="journal-preset-toggle-results"
          @click="toggleJournalResultRows"
        >
          {{ journalResultToggleLabel }}
        </button>
        <div v-if="journalResultWatchlistItems.length || journalResultAlertPayload" class="journal-result-actions">
          <button
            v-if="journalResultWatchGroupPayload"
            type="button"
            class="journal-result-action"
            data-testid="journal-preset-create-watch-group"
            @click="$emit('create-watch-group', journalResultWatchGroupPayload)"
          >
            建立專屬觀察群組 ({{ journalResultWatchlistItems.length }})
          </button>
          <button
            v-if="journalResultWatchlistItems.length"
            type="button"
            class="journal-result-action"
            data-testid="journal-preset-add-watchlist"
            @click="$emit('add-watchlist', journalResultWatchlistItems)"
          >
            加入目前顯示到自選 ({{ journalResultWatchlistItems.length }})
          </button>
          <button
            v-if="journalResultAlertPayload"
            type="button"
            class="journal-result-action"
            data-testid="journal-preset-open-alert"
            @click="$emit('open-alert-modal', journalResultAlertPayload)"
          >
            為最近命中設警報
          </button>
        </div>
        <div v-if="journalPresetResultSummary.totalEntries === 0" class="journal-empty-state">
          <div class="bt-trade-sub">目前條件沒有命中任何交易紀錄，可以先放寬一個篩選條件再看。</div>
          <div v-if="journalPresetEmptySuggestions.length" class="journal-empty-actions">
            <button
              v-for="suggestion in journalPresetEmptySuggestions"
              :key="suggestion.id"
              type="button"
              class="journal-empty-action"
              :data-testid="`journal-empty-${suggestion.id}`"
              @click="applyJournalEmptySuggestion(suggestion)"
            >
              {{ suggestion.label }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="activeJournalFilters.length" class="journal-filter-summary">
        <div class="bt-section-title">目前篩選</div>
        <div class="journal-filter-chip-list">
          <button
            v-for="item in activeJournalFilters"
            :key="item.key"
            type="button"
            class="journal-filter-chip"
            :data-testid="`journal-filter-${item.key}`"
            @click="$emit('update-journal-filter', { key: item.key, value: item.clearValue })"
          >
            <span>{{ item.label }}：{{ item.valueLabel }}</span>
            <span>×</span>
          </button>
          <button
            type="button"
            class="journal-filter-reset"
            data-testid="journal-filter-reset"
            @click="$emit('apply-journal-filter-preset', resetJournalFilterPreset)"
          >
            清除全部篩選
          </button>
        </div>
      </div>

      <div class="journal-card">
        <div class="bt-section-title">{{ journalForm.id ? "編輯紀錄" : "新增紀錄" }}</div>
        <div class="bt-row"><div class="bt-label">Ticker</div><input class="bt-inp" :value="journalForm.ticker" @input="$emit('update-journal-field', { key: 'ticker', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">市場</div><input class="bt-inp" :value="journalForm.market" @input="$emit('update-journal-field', { key: 'market', value: $event.target.value })"></div>
        <div class="bt-row">
          <div class="bt-label">方向</div>
          <select class="bt-sel" :value="journalForm.direction" @change="$emit('update-journal-field', { key: 'direction', value: $event.target.value })">
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </div>
        <div class="bt-row"><div class="bt-label">策略碼</div><input class="bt-inp" :value="journalForm.strategy_code" @input="$emit('update-journal-field', { key: 'strategy_code', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">進場時間</div><input class="bt-inp" type="datetime-local" :value="journalForm.entry_time" @input="$emit('update-journal-field', { key: 'entry_time', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">進場價格</div><input class="bt-inp" type="number" :value="journalForm.entry_price" @input="$emit('update-journal-field', { key: 'entry_price', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">出場時間</div><input class="bt-inp" type="datetime-local" :value="journalForm.exit_time" @input="$emit('update-journal-field', { key: 'exit_time', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">出場價格</div><input class="bt-inp" type="number" :value="journalForm.exit_price" @input="$emit('update-journal-field', { key: 'exit_price', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">部位</div><input class="bt-inp" type="number" :value="journalForm.size" @input="$emit('update-journal-field', { key: 'size', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">停損</div><input class="bt-inp" type="number" :value="journalForm.stop_loss" @input="$emit('update-journal-field', { key: 'stop_loss', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">停利</div><input class="bt-inp" type="number" :value="journalForm.take_profit" @input="$emit('update-journal-field', { key: 'take_profit', value: $event.target.value })"></div>
        <div class="bt-row"><div class="bt-label">標籤</div><input class="bt-inp" :value="journalForm.tags_text" @input="$emit('update-journal-field', { key: 'tags_text', value: $event.target.value })" placeholder="breakout, earnings"></div>
        <div class="bt-row"><div class="bt-label">情緒</div><input class="bt-inp" :value="journalForm.emotion_tag" @input="$emit('update-journal-field', { key: 'emotion_tag', value: $event.target.value })" placeholder="calm"></div>
        <div class="journal-text-row">
          <div class="bt-label">進場理由</div>
          <textarea class="journal-textarea" :value="journalForm.entry_reason" @input="$emit('update-journal-field', { key: 'entry_reason', value: $event.target.value })"></textarea>
        </div>
        <div class="journal-text-row">
          <div class="bt-label">出場理由</div>
          <textarea class="journal-textarea" :value="journalForm.exit_reason" @input="$emit('update-journal-field', { key: 'exit_reason', value: $event.target.value })"></textarea>
        </div>
        <div class="journal-text-row">
          <div class="bt-label">檢討</div>
          <textarea class="journal-textarea" :value="journalForm.review_notes" @input="$emit('update-journal-field', { key: 'review_notes', value: $event.target.value })"></textarea>
        </div>

        <div class="bt-row"><div class="bt-label">附件路徑</div><input class="bt-inp" :value="journalForm.attachment_path" @input="$emit('update-journal-field', { key: 'attachment_path', value: $event.target.value })" placeholder="C:/screenshots/trade.png"></div>
        <div class="bt-row"><div class="bt-label">附件類型</div><input class="bt-inp" :value="journalForm.attachment_type" @input="$emit('update-journal-field', { key: 'attachment_type', value: $event.target.value })" placeholder="image/png"></div>
        <button class="add-btn" style="margin-top:0" @click="$emit('add-journal-attachment')">＋ 加入附件</button>
        <div v-if="journalForm.attachments?.length" class="journal-attachment-list">
          <div v-for="(attachment, index) in journalForm.attachments" :key="`${attachment.file_path}-${index}`" class="bt-trade-row">
            <div>
              <div>{{ attachment.file_path }}</div>
              <div class="bt-trade-sub">{{ attachment.file_type || "metadata only" }}</div>
            </div>
            <button class="journal-inline-btn" @click="$emit('remove-journal-attachment', index)">移除</button>
          </div>
        </div>

        <div class="journal-action-row">
          <button class="run-btn" :disabled="journalLoading" @click="$emit('save-journal-entry')">{{ journalLoading ? "儲存中..." : (journalForm.id ? "更新交易紀錄" : "建立交易紀錄") }}</button>
          <button class="sync-btn" type="button" @click="$emit('reset-journal-form')">清空表單</button>
          <button v-if="journalForm.id" class="sync-btn" type="button" @click="$emit('delete-journal-entry', journalForm.id)">刪除紀錄</button>
        </div>
      </div>

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
import { computed, watch } from "vue";

const props = defineProps({
  journalForm: { type: Object, required: true },
  journalEntries: { type: Array, default: () => [] },
  journalStats: { type: Object, default: null },
  journalLoading: { type: Boolean, required: true },
  journalFilterPresets: { type: Array, default: () => [] },
  journalFilterScope: { type: String, required: true },
  journalFilters: { type: Object, required: true },
  formatDateTime: { type: Function, required: true },
});

const emit = defineEmits([
  "update-journal-field",
  "update-journal-filter",
  "apply-journal-filter-preset",
  "save-journal-filter-preset",
  "load-journal-filter-preset",
  "delete-journal-filter-preset",
  "save-journal-entry",
  "delete-journal-entry",
  "select-journal-entry",
  "reset-journal-form",
  "add-journal-attachment",
  "remove-journal-attachment",
  "create-watch-group",
  "add-watchlist",
  "open-alert-modal",
]);

const showAllJournalEntries = defineModel("showAllJournalEntries", { type: Boolean, default: false });
const editingJournalPresetId = defineModel("editingJournalPresetId", { default: null });
const journalPresetName = defineModel("journalPresetName", { type: String, default: "" });
const journalPresetDescription = defineModel("journalPresetDescription", { type: String, default: "" });

function buildJournalTagPreset(tag) {
  return {
    tag,
    search: "",
  };
}

function buildJournalStrategyPreset(strategyCode) {
  return {
    strategy_code: strategyCode,
    search: "",
  };
}

function getJournalEntryPlainTags(entry) {
  return (entry?.tags || [])
    .map((tag) => String(tag || "").trim())
    .filter((tag) => tag && !tag.startsWith("來源:") && !tag.startsWith("市場:"));
}

function findJournalEntryPrefixedTag(entry, prefix) {
  return (entry?.tags || [])
    .map((tag) => String(tag || "").trim())
    .find((tag) => tag.startsWith(prefix)) || "";
}

function buildJournalQuickSaveDraft(name, partialPreset, description) {
  const filters = {
    market: props.journalFilters?.market || "",
    strategy_code: props.journalFilters?.strategy_code || "",
    tag: props.journalFilters?.tag || "",
    search: props.journalFilters?.search || "",
  };
  const source = partialPreset && typeof partialPreset === "object" ? partialPreset : {};
  const mergedFilters = source.filters && typeof source.filters === "object"
    ? { ...filters, ...source.filters }
    : { ...filters, ...source };
  return {
    name,
    description,
    scope: Object.prototype.hasOwnProperty.call(source, "scope")
      ? (source.scope === "all" ? "all" : "ticker")
      : (props.journalFilterScope === "all" ? "all" : "ticker"),
    filters: {
      market: mergedFilters.market || "",
      strategy_code: mergedFilters.strategy_code || "",
      tag: mergedFilters.tag || "",
      search: mergedFilters.search || "",
    },
  };
}

function getJournalEntryQuickFilters(entry) {
  const quickFilters = [];
  const strategyCode = String(entry?.strategy_code || "").trim();
  const sourceTag = findJournalEntryPrefixedTag(entry, "來源:");
  const marketPostureTag = findJournalEntryPrefixedTag(entry, "市場:");

  if (sourceTag) {
    const label = `來源：${sourceTag.slice(3)}`;
    quickFilters.push({
      kind: "source",
      value: sourceTag.slice(3),
      label,
      preset: buildJournalTagPreset(sourceTag),
      saveDraft: buildJournalQuickSaveDraft(label, buildJournalTagPreset(sourceTag), "由歷史紀錄快速建立"),
    });
  }

  if (marketPostureTag) {
    const label = `市場：${marketPostureTag.slice(3)}`;
    quickFilters.push({
      kind: "posture",
      value: marketPostureTag.slice(3),
      label,
      preset: buildJournalTagPreset(marketPostureTag),
      saveDraft: buildJournalQuickSaveDraft(label, buildJournalTagPreset(marketPostureTag), "由歷史紀錄快速建立"),
    });
  }

  if (strategyCode) {
    const label = `策略：${strategyCode}`;
    quickFilters.push({
      kind: "strategy",
      value: strategyCode,
      label,
      preset: buildJournalStrategyPreset(strategyCode),
      saveDraft: buildJournalQuickSaveDraft(label, buildJournalStrategyPreset(strategyCode), "由歷史紀錄快速建立"),
    });
  }

  return quickFilters;
}

function normalizeJournalFilterSnapshot(source) {
  const filters = source?.filters && typeof source.filters === "object"
    ? source.filters
    : source || {};
  return {
    scope: source?.scope === "all" ? "all" : "ticker",
    filters: {
      market: String(filters.market || "").trim(),
      strategy_code: String(filters.strategy_code || "").trim(),
      tag: String(filters.tag || "").trim(),
      search: String(filters.search || "").trim(),
    },
  };
}

function isSameJournalFilterSnapshot(left, right) {
  if (!left || !right) return false;
  if (left.scope !== right.scope) return false;
  return ["market", "strategy_code", "tag", "search"].every(
    (key) => String(left.filters?.[key] || "") === String(right.filters?.[key] || ""),
  );
}

function saveJournalPreset() {
  const name = String(journalPresetName.value || "").trim();
  if (!name) return;
  emit("save-journal-filter-preset", {
    id: editingJournalPresetId.value,
    name,
    description: String(journalPresetDescription.value || "").trim(),
    scope: props.journalFilterScope === "all" ? "all" : "ticker",
    filters: {
      market: props.journalFilters?.market || "",
      strategy_code: props.journalFilters?.strategy_code || "",
      tag: props.journalFilters?.tag || "",
      search: props.journalFilters?.search || "",
    },
  });
  resetJournalPresetEditor();
}

function startEditingJournalPreset(preset) {
  editingJournalPresetId.value = preset?.id ?? null;
  journalPresetName.value = preset?.name || "";
  journalPresetDescription.value = preset?.description || "";
}

function resetJournalPresetEditor() {
  editingJournalPresetId.value = null;
  journalPresetName.value = "";
  journalPresetDescription.value = "";
}

const journalLoadedEntryCount = computed(() => (
  Array.isArray(props.journalEntries) ? props.journalEntries.length : 0
));

const journalEntryRows = computed(() => {
  const entries = Array.isArray(props.journalEntries) ? props.journalEntries : [];
  return showAllJournalEntries.value ? entries : entries.slice(0, 12);
});

const topSourceBreakdown = computed(() => (props.journalStats?.source_breakdown || []).slice(0, 3));
const topStrategyBreakdown = computed(() => (props.journalStats?.strategy_breakdown || []).slice(0, 3));
const topMarketPostureBreakdown = computed(() => (props.journalStats?.market_posture_breakdown || []).slice(0, 3));
const topTagBreakdown = computed(() => (
  (props.journalStats?.tag_breakdown || [])
    .filter((item) => !String(item.key || "").startsWith("來源:") && !String(item.key || "").startsWith("市場:"))
    .slice(0, 4)
));

const resetJournalFilterPreset = {
  scope: "ticker",
  market: "",
  strategy_code: "",
  tag: "",
  search: "",
};

const currentJournalFilterSnapshot = computed(() => normalizeJournalFilterSnapshot({
  scope: props.journalFilterScope,
  filters: props.journalFilters,
}));

watch(currentJournalFilterSnapshot, () => {
  showAllJournalEntries.value = false;
}, { deep: true });

const activeJournalPreset = computed(() => (
  (props.journalFilterPresets || []).find((preset) =>
    isSameJournalFilterSnapshot(normalizeJournalFilterSnapshot(preset), currentJournalFilterSnapshot.value))
  || null
));

const activeJournalFilters = computed(() => {
  const chips = [];
  if (props.journalFilterScope === "all") {
    chips.push({
      key: "scope",
      label: "範圍",
      valueLabel: "全部紀錄",
      clearValue: "ticker",
    });
  }

  const filterLabels = {
    market: "市場",
    strategy_code: "策略",
    tag: "標籤",
    search: "關鍵字",
  };

  Object.entries(filterLabels).forEach(([key, label]) => {
    const value = String(props.journalFilters?.[key] || "").trim();
    if (!value) return;
    chips.push({
      key,
      label,
      valueLabel: value,
      clearValue: "",
    });
  });

  return chips;
});

function isJournalPresetActive(preset) {
  if (!preset || !activeJournalPreset.value) return false;
  return String(preset.id) === String(activeJournalPreset.value.id);
}

const journalPresetResultSummary = computed(() => {
  if (!props.journalStats || (!activeJournalPreset.value && !activeJournalFilters.value.length)) {
    return null;
  }
  return {
    name: activeJournalPreset.value?.name || "自訂篩選",
    description: activeJournalPreset.value?.description || "目前條件命中摘要",
    scopeLabel: currentJournalFilterSnapshot.value.scope === "all" ? "全部紀錄" : "目前標的",
    totalEntries: Number(props.journalStats.total_entries || 0),
    visibleEntries: Number(journalEntryRows.value.length || 0),
    closedEntries: Number(props.journalStats.closed_entries || 0),
    openEntries: Number(props.journalStats.open_entries || 0),
    winRate: Number(props.journalStats.win_rate || 0),
    netPnl: Number(props.journalStats.net_pnl || 0),
    avgReturnPct: Number(props.journalStats.avg_return_pct || 0),
  };
});

const journalPresetLatestEntry = computed(() => {
  if (!journalPresetResultSummary.value || journalPresetResultSummary.value.totalEntries === 0) {
    return null;
  }
  const entries = Array.isArray(props.journalEntries) ? props.journalEntries : [];
  if (!entries.length) return null;
  return entries.reduce((latest, entry) => {
    if (!latest) return entry;
    const latestTime = Date.parse(latest?.entry_time || "") || 0;
    const currentTime = Date.parse(entry?.entry_time || "") || 0;
    return currentTime >= latestTime ? entry : latest;
  }, null);
});

const journalResultToggleVisible = computed(() => (
  Boolean(journalPresetResultSummary.value)
  && Number(journalPresetResultSummary.value?.totalEntries || 0) > 0
  && journalLoadedEntryCount.value > 12
));

const journalResultToggleLabel = computed(() => (
  showAllJournalEntries.value
    ? "收合至前 12 筆"
    : `查看全部命中 (${journalLoadedEntryCount.value})`
));

function toggleJournalResultRows() {
  showAllJournalEntries.value = !showAllJournalEntries.value;
}

const journalResultContextTags = computed(() => {
  const tags = [
    "日誌復盤",
    String(activeJournalPreset.value?.name || "").trim(),
    String(props.journalFilters?.tag || "").trim(),
    String(props.journalFilters?.strategy_code || "").trim()
      ? `策略:${String(props.journalFilters?.strategy_code || "").trim()}`
      : "",
  ]
    .map((item) => String(item || "").trim())
    .filter(Boolean);
  return Array.from(new Set(tags)).slice(0, 6);
});

const journalResultWatchlistItems = computed(() => {
  const seen = new Set();
  return journalEntryRows.value.reduce((items, entry) => {
    const ticker = String(entry?.ticker || "").trim();
    if (!ticker || seen.has(ticker)) return items;
    seen.add(ticker);
    items.push({
      ticker,
      tags: journalResultContextTags.value,
    });
    return items;
  }, []);
});

const journalResultWatchGroupPayload = computed(() => {
  if (!journalResultWatchlistItems.value.length) return null;
  const presetName = String(journalPresetResultSummary.value?.name || "").trim();
  const strategy = String(props.journalFilters?.strategy_code || "").trim();
  const tag = String(props.journalFilters?.tag || "").trim();
  const baseName = presetName || strategy || tag || "日誌";
  const groupName = baseName.includes("命中池") ? baseName : `${baseName} 命中池`;
  return {
    name: groupName,
    items: journalResultWatchlistItems.value,
  };
});

const journalResultAlertPayload = computed(() => {
  if (!journalPresetLatestEntry.value) return null;
  return {
    ticker: journalPresetLatestEntry.value.ticker,
    type: "price",
    condition: "大於",
    value: "",
    context_source: "journal_result",
    context_tags: journalResultContextTags.value,
    snapshot_price: journalPresetLatestEntry.value.entry_price ?? null,
    snapshot_timestamp: journalPresetLatestEntry.value.entry_time || "",
    prefill_hint: `${journalPresetResultSummary.value?.name || "自訂篩選"} 最近命中`,
  };
});

const journalPresetEmptySuggestions = computed(() => {
  if (!journalPresetResultSummary.value || journalPresetResultSummary.value.totalEntries !== 0) {
    return [];
  }

  const suggestions = [];
  if (props.journalFilterScope !== "all") {
    suggestions.push({
      id: "scope-all",
      label: "改看全部紀錄",
      type: "update",
      key: "scope",
      value: "all",
    });
  }
  if (String(props.journalFilters?.search || "").trim()) {
    suggestions.push({
      id: "clear-search",
      label: "清除關鍵字",
      type: "update",
      key: "search",
      value: "",
    });
  }
  if (String(props.journalFilters?.tag || "").trim()) {
    suggestions.push({
      id: "clear-tag",
      label: "清除標籤",
      type: "update",
      key: "tag",
      value: "",
    });
  }
  if (String(props.journalFilters?.strategy_code || "").trim()) {
    suggestions.push({
      id: "clear-strategy",
      label: "清除策略",
      type: "update",
      key: "strategy_code",
      value: "",
    });
  }
  if (String(props.journalFilters?.market || "").trim()) {
    suggestions.push({
      id: "clear-market",
      label: "清除市場",
      type: "update",
      key: "market",
      value: "",
    });
  }
  if (activeJournalFilters.value.length) {
    suggestions.push({
      id: "reset-all",
      label: "清除全部篩選",
      type: "preset",
      value: resetJournalFilterPreset,
    });
  }
  return suggestions;
});

function applyJournalEmptySuggestion(suggestion) {
  if (!suggestion) return;
  if (suggestion.type === "preset") {
    emit("apply-journal-filter-preset", suggestion.value);
    return;
  }
  emit("update-journal-filter", { key: suggestion.key, value: suggestion.value });
}
</script>
<style scoped>
.journal-analytics-card {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.journal-analytics-row-wrap {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.journal-analytics-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex: 1;
  width: 100%;
  padding: 8px 0;
  border: 0;
  background: transparent;
  text-align: left;
  font-size: 11px;
  cursor: pointer;
}

.journal-analytics-save {
  flex-shrink: 0;
  align-self: center;
  border: 0;
  border-radius: 999px;
  padding: 6px 9px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
  font-size: 10px;
  line-height: 1.2;
  cursor: pointer;
}

.journal-analytics-row-wrap + .journal-analytics-row-wrap {
  border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.journal-filter-summary {
  margin-top: 10px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(123, 231, 255, 0.05);
  border: 1px solid rgba(123, 231, 255, 0.12);
}

.journal-preset-save {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 8px;
  margin-top: 8px;
}

.journal-preset-save .bt-inp {
  min-width: 0;
}

.journal-preset-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.journal-preset-chip {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-width: 180px;
  padding-right: 52px;
}

.journal-preset-chip small {
  color: var(--text3);
  font-size: 10px;
  line-height: 1.4;
  text-align: left;
}

.journal-preset-active {
  border-color: rgba(123, 231, 255, 0.38);
  box-shadow: 0 0 0 1px rgba(123, 231, 255, 0.12) inset;
}

.journal-preset-actions {
  position: absolute;
  top: 6px;
  right: 8px;
  display: flex;
  gap: 8px;
}

.journal-preset-edit,
.journal-preset-delete {
  font-size: 12px;
  color: var(--text3);
}

.journal-filter-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.journal-filter-chip,
.journal-filter-reset {
  border: 0;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 10px;
  line-height: 1.4;
  cursor: pointer;
}

.journal-filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(123, 231, 255, 0.14);
  color: #c9f6ff;
}

.journal-filter-reset {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
}

.journal-preset-result-card {
  margin-top: 12px;
}

.journal-preset-latest-hit {
  width: 100%;
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(123, 231, 255, 0.14);
  border-radius: 10px;
  background: rgba(8, 26, 36, 0.82);
  color: var(--text1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  text-align: left;
  cursor: pointer;
}

.journal-preset-expand-btn {
  width: 100%;
  margin-top: 8px;
  border: 0;
  border-radius: 999px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
  font-size: 10px;
  line-height: 1.4;
  cursor: pointer;
}

.journal-result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.journal-result-action {
  flex: 1 1 180px;
  border: 0;
  border-radius: 999px;
  padding: 8px 12px;
  background: rgba(123, 231, 255, 0.12);
  color: #c9f6ff;
  font-size: 10px;
  line-height: 1.4;
  cursor: pointer;
}

.journal-empty-state {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.journal-empty-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.journal-empty-action {
  border: 0;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
  font-size: 10px;
  line-height: 1.4;
  cursor: pointer;
}

.journal-entry-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.journal-entry-quick-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.journal-entry-quick-filter-group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.journal-entry-meta-chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(123, 231, 255, 0.2);
  background: rgba(8, 26, 36, 0.9);
  color: var(--text2);
  font-size: 10px;
  line-height: 1.4;
  cursor: pointer;
}

.journal-entry-meta-save {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--text3);
  font-size: 10px;
  line-height: 1.4;
  cursor: pointer;
}

.journal-entry-tag {
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(255, 209, 102, 0.12);
  color: #ffe1a0;
  font-size: 10px;
  line-height: 1.4;
  cursor: pointer;
}
</style>
