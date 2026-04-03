<template>
  <div class="right-panel">
    <div class="rp-tabs">
      <div class="rtab" :class="{ active: rightTab === 'indicators' }" @click="$emit('set-right-tab', 'indicators')">指標</div>
      <div class="rtab" :class="{ active: rightTab === 'alerts' }" @click="$emit('set-right-tab', 'alerts')">警報</div>
      <div class="rtab" :class="{ active: rightTab === 'backtest' }" @click="$emit('set-right-tab', 'backtest')">回測</div>
      <div class="rtab" :class="{ active: rightTab === 'journal' }" @click="$emit('set-right-tab', 'journal')">日誌</div>
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
        <div class="ind-group-title">趨勢疊加</div>
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
        <div class="ind-group-title">副圖面板</div>
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
        <div class="tech-summary">
          <div v-for="(item, idx) in indicatorSnapshot.techSummaryItems || []" :key="idx">
            <span :class="item.cls">{{ item.text }}</span>
          </div>
          <div v-if="indicatorSnapshot.techSummaryVerdict" style="margin-top:8px">
            <span :class="indicatorSnapshot.techSummaryVerdict.cls">{{ indicatorSnapshot.techSummaryVerdict.text }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-show="rightTab === 'alerts'" class="rp-content">
      <div class="alert-summary-card">
        <div class="alert-summary-title">警報中心</div>
        <div class="alert-summary-subtitle">狀態、觸發紀錄與通知均來自本地資料庫</div>
      </div>
      <div v-if="alerts.length" class="alert-list">
        <div
          v-for="(alert, index) in alerts"
          :key="alert.id || `${alert.ticker}-${index}`"
          class="alert-card"
          :class="{ triggered: alert.triggered }"
        >
          <div class="alert-head">
            <div>
              <div class="alert-tk">{{ formatAlertTarget(alert) }}</div>
              <div class="alert-cond">{{ formatAlertSummary(alert) }}</div>
            </div>
            <div class="alert-badge" :class="alert.triggered ? 'triggered' : (alert.active ? 'active' : 'paused')">
              {{ formatAlertStatus(alert) }}
            </div>
          </div>

          <div class="alert-meta-grid">
            <div class="alert-meta-item">
              <span>類型</span>
              <span>{{ formatAlertType(alert) }}</span>
            </div>
            <div class="alert-meta-item">
              <span>最近評估</span>
              <span>{{ formatDateTime(alert.last_evaluated_at) }}</span>
            </div>
            <div class="alert-meta-item">
              <span>最近觸發</span>
              <span>{{ formatDateTime(alert.triggered_at) }}</span>
            </div>
            <div class="alert-meta-item">
              <span>儲存位置</span>
              <span>MySQL / alerts</span>
            </div>
          </div>

          <div v-if="getAlertContextSource(alert) || getAlertContextGroupName(alert) || getAlertContextTags(alert).length" class="alert-context-card">
            <div class="alert-context-head">
              <span>{{ getAlertContextSource(alert) || "研究上下文" }}</span>
              <span v-if="getAlertSnapshotLabel(alert)">{{ getAlertSnapshotLabel(alert) }}</span>
            </div>
            <div v-if="getAlertContextGroupName(alert) || getAlertContextTags(alert).length" class="alert-context-tags">
              <span
                v-if="getAlertContextGroupName(alert)"
                :key="`${alert.id}-context-group`"
                class="alert-context-tag"
              >
                {{ `群組：${getAlertContextGroupName(alert)}` }}
              </span>
              <span
                v-for="tag in getAlertContextTags(alert)"
                :key="`${alert.id}-${tag}`"
                class="alert-context-tag"
              >
                {{ tag }}
              </span>
            </div>
          </div>

          <div class="alert-actions">
            <button
              v-if="getAlertContextGroupName(alert)"
              class="alert-action-btn log"
              @click="$emit('open-watch-group', { groupName: getAlertContextGroupName(alert), ticker: alert.ticker || null })"
            >
              回到群組
            </button>
            <button class="alert-action-btn pause" @click="$emit('toggle-alert-active', alert.id)">
              {{ alert.active ? "暫停" : "恢復" }}
            </button>
            <button class="alert-action-btn log" @click="$emit('toggle-alert-log', alert.id)">
              {{ isAlertLogOpen(alert) ? "收合紀錄" : "觸發紀錄" }}
            </button>
            <button class="alert-action-btn delete" @click="$emit('delete-alert', alert.id)">刪除</button>
          </div>

          <div v-if="isAlertLogOpen(alert)" class="alert-log-card">
            <div class="alert-log-title">alert_trigger_logs</div>
            <div v-if="isAlertLogLoading(alert)" class="alert-log-empty">載入中...</div>
            <div v-else-if="getAlertLogs(alert).length" class="alert-log-list">
              <div
                v-for="log in getAlertLogs(alert)"
                :key="log.id"
                class="alert-log-row"
              >
                <div class="alert-log-row-top">
                  <span>{{ formatDateTime(log.created_at) }}</span>
                  <span>{{ formatLogSource(log) }}</span>
                </div>
                <div class="alert-log-row-bottom">
                  <span>觸發值 {{ formatAlertMetricValue(alert, log.trigger_value) }}</span>
                  <span>門檻 {{ formatAlertMetricValue(alert, log.threshold_value) }}</span>
                </div>
                <div v-if="formatLogMacroContext(log)" class="alert-log-row-bottom">
                  <span>{{ formatLogMacroContext(log) }}</span>
                </div>
                <div v-if="formatLogContextSummary(log)" class="alert-log-row-bottom">
                  <span>{{ formatLogContextSummary(log) }}</span>
                </div>
              </div>
            </div>
            <div v-else class="alert-log-empty">尚無觸發紀錄</div>
          </div>
        </div>
      </div>
      <div v-else style="color:var(--text3);font-size:11px;text-align:center;padding:16px">尚無警報</div>
      <button class="add-btn" @click="$emit('open-alert-modal')">＋ 新增警報</button>
    </div>

    <div v-show="rightTab === 'backtest'" class="rp-content">
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
      <div class="bt-row"><div class="bt-label">手續費</div><input class="bt-inp" type="number" :value="backtestForm.fee" step="0.01" @input="$emit('update-backtest-field', { key: 'fee', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <div class="bt-row"><div class="bt-label">滑價</div><input class="bt-inp" type="number" :value="backtestForm.slippage" step="0.01" @input="$emit('update-backtest-field', { key: 'slippage', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <div class="bt-row"><div class="bt-label">停損</div><input class="bt-inp" type="number" :value="backtestForm.sl" step="0.5" @input="$emit('update-backtest-field', { key: 'sl', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <div class="bt-row"><div class="bt-label">停利</div><input class="bt-inp" type="number" :value="backtestForm.tp" step="0.5" @input="$emit('update-backtest-field', { key: 'tp', value: $event.target.value })"><span style="font-size:10px;color:var(--text3)">%</span></div>
      <button class="run-btn" :disabled="backtestLoading" @click="$emit('run-backtest')">{{ backtestLoading ? "回測中..." : "▶ 執行回測" }}</button>

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

      <div class="bt-history-card">
        <div class="bt-section-title">歷史回測</div>
        <div v-if="backtestHistory.length">
          <button
            v-for="item in backtestHistoryRows"
            :key="item.id"
            type="button"
            class="bt-history-row"
            @click="$emit('load-backtest', item.id)"
          >
            <span>
              <div>{{ item.strategy }}</div>
              <div class="bt-trade-sub">{{ item.start }} ~ {{ item.end }}</div>
            </span>
            <span :class="item.totalReturn >= 0 ? 'up' : 'dn'">{{ item.totalReturn >= 0 ? "+" : "" }}{{ item.totalReturn.toFixed(2) }}%</span>
          </button>
        </div>
        <div v-else class="bt-history-empty">尚無回測紀錄</div>
      </div>
    </div>

    <div v-show="rightTab === 'journal'" class="rp-content">
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

    <div v-show="rightTab === 'db'" class="rp-content">
      <div class="ind-group">
        <div class="ind-group-title">資料庫狀態</div>
        <div v-if="dbStats">
          <div class="db-stat-row"><span>總 K 線筆數</span><span style="color:var(--green)">{{ dbStats.total_rows?.toLocaleString() }}</span></div>
          <div class="db-stat-row"><span>股票數量</span><span>{{ dbStats.total_tickers }}</span></div>
          <div v-for="item in dbStats.top_tickers || []" :key="item.ticker" class="db-stat-row">
            <span>
              <div>{{ item.ticker }}</div>
              <div v-if="item.name && item.name !== item.ticker" class="db-stat-name">{{ item.name }}</div>
            </span>
            <span>{{ item.rows }} 筆</span>
          </div>
        </div>
        <div v-else-if="dbStatsLoading" style="color:var(--text2);font-size:11px">載入中...</div>
        <div v-else style="color:var(--red);font-size:11px">{{ dbStatsError || "尚未載入資料庫統計" }}</div>
      </div>
      <button class="sync-btn" :disabled="syncingAll" @click="$emit('sync-all')">{{ syncingAll ? "↻ 同步中..." : "↻ 同步股票與大盤最新資料" }}</button>
      <div style="margin-top:10px;font-size:10px;color:var(--text3);line-height:1.8">
        資料庫：<span style="color:var(--text2)">MySQL / quantvision</span><br>
        資料來源：<span style="color:var(--text2)">Yahoo Finance</span><br>
        更新頻率：<span style="color:var(--text2)">定時輪詢 + 每日自動更新</span><br>
        同步範圍：<span style="color:var(--text2)">自選股群組與全球大盤群組</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  rightTab: { type: String, required: true },
  indicatorSnapshot: { type: Object, required: true },
  activeInd: { type: Object, required: true },
  activePanels: { type: Object, required: true },
  indicatorSettings: { type: Object, required: true },
  alerts: { type: Array, required: true },
  alertTriggerLogs: { type: Object, default: () => ({}) },
  alertLogLoading: { type: Object, default: () => ({}) },
  expandedAlertLogId: { type: [Number, String], default: null },
  backtestForm: { type: Object, required: true },
  backtestResult: { type: Object, default: null },
  backtestHistory: { type: Array, default: () => [] },
  backtestLoading: { type: Boolean, required: true },
  journalForm: { type: Object, required: true },
  journalEntries: { type: Array, default: () => [] },
  journalStats: { type: Object, default: null },
  journalLoading: { type: Boolean, required: true },
  journalFilterPresets: { type: Array, default: () => [] },
  journalFilterScope: { type: String, required: true },
  journalFilters: { type: Object, required: true },
  dbStats: { type: Object, default: null },
  dbStatsLoading: { type: Boolean, required: true },
  dbStatsError: { type: String, default: "" },
  syncingAll: { type: Boolean, required: true },
});

const emit = defineEmits([
  "set-right-tab",
  "toggle-indicator",
  "toggle-panel",
  "update-indicator-setting",
  "apply-indicator-preset",
  "open-alert-modal",
  "open-watch-group",
  "toggle-alert-active",
  "toggle-alert-log",
  "delete-alert",
  "update-backtest-field",
  "run-backtest",
  "load-backtest",
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
  "sync-all",
]);

function buildSparklinePath(points) {
  if (!Array.isArray(points) || points.length < 2) return "";
  const values = points.map((item) => Number(item?.equity ?? 0)).filter((value) => Number.isFinite(value));
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = 240;
  const height = 90;
  const xStep = width / Math.max(values.length - 1, 1);
  return values.map((value, index) => {
    const x = Number((index * xStep).toFixed(2));
    const ratio = max === min ? 0.5 : (value - min) / (max - min);
    const y = Number((height - (ratio * (height - 12)) - 6).toFixed(2));
    return `${index === 0 ? "M" : "L"}${x} ${y}`;
  }).join(" ");
}

function formatPct(value) {
  if (value == null || value === "") return "—";
  return `${(Number(value) * 100).toFixed(2)}%`;
}

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

const journalPresetName = ref("");
const journalPresetDescription = ref("");
const editingJournalPresetId = ref(null);
const showAllJournalEntries = ref(false);

function saveJournalPreset() {
  if (!journalPresetName.value) return;
  emit("save-journal-filter-preset", {
    id: editingJournalPresetId.value,
    name: journalPresetName.value,
    description: journalPresetDescription.value,
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

const ALERT_TYPE_LABELS = {
  price: "價格",
  pct: "漲跌幅",
  rsi: "RSI",
  macd: "MACD",
  volume: "量比",
  market_risk: "市場風險",
};

const ALERT_CONDITION_LABELS = {
  gt: "大於",
  lt: "小於",
  eq: "等於",
  "大於": "大於",
  "小於": "小於",
  "等於": "等於",
  cross_up: "黃金交叉",
  cross_down: "死亡交叉",
  "上穿": "黃金交叉",
  "下穿": "死亡交叉",
  "黃金交叉": "黃金交叉",
  "死亡交叉": "死亡交叉",
  high: "進入高風險",
  medium_or_high: "進入中風險以上",
  risk_off: "進入 risk-off",
  offensive: "進入偏進攻",
};

const MARKET_RISK_VALUE_LABELS = {
  high: "高風險",
  medium: "中風險",
  low: "低風險",
  medium_or_high: "中風險以上",
  risk_off: "risk-off",
  risk_on: "risk-on",
  offensive: "偏進攻",
  balanced: "平衡觀察",
  selective: "選擇性出手",
  defensive: "防守控倉",
};

function formatDateTime(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("zh-TW", { hour12: false });
}

function formatAlertType(alert) {
  return ALERT_TYPE_LABELS[String(alert?.type || "").toLowerCase()] || alert?.type || "警報";
}

function formatAlertTarget(alert) {
  if (String(alert?.type || "").toLowerCase() === "market_risk") return "市場";
  if (String(alert?.ticker || "").toUpperCase() === "MARKET") return "市場";
  return alert?.ticker || "—";
}

function formatAlertMetricValue(alert, value) {
  if (value == null || value === "") return "—";
  const normalizedType = String(alert?.type || "").toLowerCase();
  if (normalizedType === "market_risk") {
    return MARKET_RISK_VALUE_LABELS[String(value)] || String(value);
  }
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return String(value);
  if (normalizedType === "pct") {
    return `${numericValue.toFixed(2)}%`;
  }
  if (normalizedType === "volume") {
    return `${numericValue.toFixed(2)}x`;
  }
  return numericValue.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function formatAlertSummary(alert) {
  const condition = ALERT_CONDITION_LABELS[alert?.condition || alert?.cond] || alert?.condition || alert?.cond || "—";
  const valueLabel = formatAlertMetricValue(alert, alert?.value);
  return valueLabel === "—"
    ? `${formatAlertType(alert)} · ${condition}`
    : `${formatAlertType(alert)} · ${condition} ${valueLabel}`;
}

function formatAlertStatus(alert) {
  if (alert?.triggered) return "已觸發";
  return alert?.active ? "監控中" : "已暫停";
}

function getAlertLogs(alert) {
  const cacheKey = String(alert?.id ?? "");
  return props.alertTriggerLogs?.[cacheKey] || [];
}

function isAlertLogOpen(alert) {
  return String(props.expandedAlertLogId ?? "") === String(alert?.id ?? "");
}

function isAlertLogLoading(alert) {
  return Boolean(props.alertLogLoading?.[String(alert?.id ?? "")]);
}

function formatLogSource(log) {
  return log?.payload?.quote?.source || "local_db";
}

function formatLogMacroContext(log) {
  const summary = log?.payload?.macro_summary || log?.payload?.quote?.macro_summary;
  if (!summary) return "";
  const riskLabel = MARKET_RISK_VALUE_LABELS[String(summary.overall_risk)] || summary.overall_risk;
  const postureLabel = MARKET_RISK_VALUE_LABELS[String(summary.trade_posture)] || summary.trade_posture;
  return `市場 ${riskLabel} / ${postureLabel}`;
}

function getAlertContextSource(alert) {
  const source = String(alert?.condition_payload?.context_source || "").toLowerCase();
  if (source === "watchlist") return "來源：觀察池";
  if (source === "watchlist_group") return "來源：觀察群組";
  if (!source) return "";
  return `來源：${source}`;
}

function getAlertContextGroupName(alert) {
  return String(alert?.condition_payload?.context_group_name || "").trim();
}

function getAlertContextTags(alert) {
  return Array.isArray(alert?.condition_payload?.context_tags)
    ? alert.condition_payload.context_tags.filter(Boolean).slice(0, 4)
    : [];
}

function formatLogContextSummary(log) {
  const source = String(log?.payload?.context_source || "").toLowerCase();
  const parts = [];
  if (source === "watchlist_group") parts.push("來源：觀察群組");
  else if (source === "watchlist") parts.push("來源：觀察池");
  else if (source) parts.push(`來源：${source}`);
  if (log?.payload?.context_group_name) parts.push(`群組：${log.payload.context_group_name}`);
  return parts.join(" / ");
}

function getAlertSnapshotLabel(alert) {
  const snapshotPrice = alert?.condition_payload?.snapshot_price;
  if (snapshotPrice == null || snapshotPrice === "") return "";
  return `快照 ${formatAlertMetricValue({ type: "price" }, snapshotPrice)}`;
}

const overlayRows = computed(() => [
  { key: "cycleMa", label: "周 / 月 / 季 / 年線", value: "MA 5 / 20 / 60 / 240", color: "#7be7ff", hint: "清指標模式下仍會保留的核心均線組" },
  { key: "ma20", label: `MA ${props.indicatorSettings.ma20Period}`, value: props.indicatorSnapshot.ma20, color: "#3b8bff" },
  { key: "ma50", label: `MA ${props.indicatorSettings.ma50Period}`, value: props.indicatorSnapshot.ma50, color: "#f5a623" },
  { key: "ma200", label: `MA ${props.indicatorSettings.ma200Period}`, value: props.indicatorSnapshot.ma200, color: "#9b6dff" },
  { key: "ema12", label: `EMA ${props.indicatorSettings.emaPeriod}`, value: props.indicatorSnapshot.ema12, color: "#00d4ff" },
  { key: "bb", label: `布林通道 (${props.indicatorSettings.bbPeriod}, ${props.indicatorSettings.bbMultiplier})`, value: props.indicatorSnapshot.bb, color: "#ffd166" },
  { key: "psar", label: `Parabolic SAR (${props.indicatorSettings.psarStep}, ${props.indicatorSettings.psarMax})`, value: props.indicatorSnapshot.psar, color: "#ff6b6b", hint: "拋物線停損反轉" },
  { key: "keltner", label: `Keltner (${props.indicatorSettings.kcPeriod}, ${props.indicatorSettings.kcMultiplier})`, value: props.indicatorSnapshot.keltner, color: "#7be7ff", hint: "EMA + ATR 通道" },
  { key: "donchian", label: `Donchian (${props.indicatorSettings.donchianPeriod})`, value: props.indicatorSnapshot.donchian, color: "#9b6dff", hint: "區間突破通道" },
  { key: "vwap", label: "VWAP", value: "ON", color: "#ff8c42", hint: "盤中量價基準線" },
  { key: "ichimoku", label: `Ichimoku (${props.indicatorSettings.ichimokuConversion}, ${props.indicatorSettings.ichimokuBase}, ${props.indicatorSettings.ichimokuSpanB})`, value: props.indicatorSnapshot.ichimoku, color: "#8dc1ff", hint: `位移 ${props.indicatorSettings.ichimokuDisplacement}` },
  { key: "supertrend", label: `SuperTrend (${props.indicatorSettings.supertrendPeriod}, ${props.indicatorSettings.supertrendMultiplier})`, value: props.indicatorSnapshot.supertrend, color: "#7be7ff", hint: "多空切換支撐線" },
]);

const panelRows = computed(() => [
  { key: "rsi", label: `RSI(${props.indicatorSettings.rsiPeriod})`, hint: "70 超買 / 30 超賣", value: props.indicatorSnapshot.rsi, valueClass: props.indicatorSnapshot.rsiClass },
  { key: "aroon", label: `Aroon(${props.indicatorSettings.aroonPeriod})`, hint: "Up / Down 趨勢強度", value: props.indicatorSnapshot.aroon, valueClass: "" },
  { key: "trix", label: `TRIX(${props.indicatorSettings.trixPeriod},${props.indicatorSettings.trixSignal})`, hint: props.indicatorSnapshot.trixSignal, value: props.indicatorSnapshot.trix, valueClass: "" },
  { key: "williamsr", label: `Williams %R(${props.indicatorSettings.williamsrPeriod})`, hint: "-20 超買 / -80 超賣", value: props.indicatorSnapshot.williamsr, valueClass: "" },
  { key: "mfi", label: `MFI(${props.indicatorSettings.mfiPeriod})`, hint: "量價資金流", value: props.indicatorSnapshot.mfi, valueClass: "" },
  { key: "roc", label: `ROC(${props.indicatorSettings.rocPeriod})`, hint: "價格動能百分比", value: props.indicatorSnapshot.roc, valueClass: "" },
  { key: "bbPercent", label: `Bollinger %B(${props.indicatorSettings.bbPeriod})`, hint: "0 下軌 / 100 上軌", value: props.indicatorSnapshot.bbPercent, valueClass: "" },
  { key: "bbWidth", label: `Bollinger Width(${props.indicatorSettings.bbPeriod})`, hint: "通道寬度 / 壓縮偵測", value: props.indicatorSnapshot.bbWidth, valueClass: "" },
  { key: "macd", label: `MACD(${props.indicatorSettings.macdFast},${props.indicatorSettings.macdSlow},${props.indicatorSettings.macdSignal})`, hint: props.indicatorSnapshot.macdSignal, value: props.indicatorSnapshot.macd, valueClass: "" },
  { key: "stoch", label: `KD Stoch(${props.indicatorSettings.stochK},${props.indicatorSettings.stochD})`, hint: "擺盪強弱", value: props.indicatorSnapshot.stoch, valueClass: "" },
  { key: "atr", label: `ATR(${props.indicatorSettings.atrPeriod})`, hint: "波動幅度 / 停損參考", value: props.indicatorSnapshot.atr, valueClass: "" },
  { key: "cci", label: `CCI(${props.indicatorSettings.cciPeriod})`, hint: "±100 強弱區間", value: props.indicatorSnapshot.cci, valueClass: "" },
  { key: "obv", label: "OBV", hint: "量能趨勢累積", value: props.indicatorSnapshot.obv, valueClass: "" },
  { key: "adx", label: `ADX(${props.indicatorSettings.adxPeriod})`, hint: props.indicatorSnapshot.adxSignal, value: props.indicatorSnapshot.adx, valueClass: "" },
  { key: "cmf", label: `CMF(${props.indicatorSettings.cmfPeriod})`, hint: "Chaikin 資金流", value: props.indicatorSnapshot.cmf, valueClass: "" },
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
      { key: "psarStep", label: "PSAR Step", step: 0.005, min: 0.005, max: 0.2, range: "0.005-0.2" },
      { key: "psarMax", label: "PSAR Max", step: 0.01, min: 0.02, max: 1, range: "0.02-1" },
      { key: "kcPeriod", label: "Keltner 週期", step: 1, min: 2, max: 300, range: "2-300" },
      { key: "kcMultiplier", label: "Keltner 倍數", step: 0.1, min: 0.5, max: 6, range: "0.5-6" },
      { key: "donchianPeriod", label: "Donchian 週期", step: 1, min: 2, max: 300, range: "2-300" },
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
      { key: "aroonPeriod", label: "Aroon", step: 1, min: 2, max: 150, range: "2-150" },
      { key: "trixPeriod", label: "TRIX", step: 1, min: 2, max: 120, range: "2-120" },
      { key: "trixSignal", label: "TRIX 訊號", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "williamsrPeriod", label: "Williams %R", step: 1, min: 2, max: 100, range: "2-100" },
      { key: "mfiPeriod", label: "MFI", step: 1, min: 2, max: 100, range: "2-100" },
      { key: "rocPeriod", label: "ROC", step: 1, min: 1, max: 120, range: "1-120" },
      { key: "macdFast", label: "MACD 快線", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "macdSlow", label: "MACD 慢線", step: 1, min: 3, max: 120, range: "3-120" },
      { key: "macdSignal", label: "MACD 訊號", step: 1, min: 2, max: 60, range: "2-60" },
      { key: "stochK", label: "KD K", step: 1, min: 3, max: 100, range: "3-100" },
      { key: "stochD", label: "KD D", step: 1, min: 2, max: 20, range: "2-20" },
      { key: "atrPeriod", label: "ATR", step: 1, min: 2, max: 120, range: "2-120" },
      { key: "cciPeriod", label: "CCI", step: 1, min: 3, max: 120, range: "3-120" },
      { key: "adxPeriod", label: "ADX", step: 1, min: 2, max: 120, range: "2-120" },
      { key: "cmfPeriod", label: "CMF", step: 1, min: 2, max: 120, range: "2-120" },
    ],
  },
]);

const backtestEquityPath = computed(() => buildSparklinePath(props.backtestResult?.equity_curve || []));
const backtestTradeRows = computed(() => (props.backtestResult?.trades || []).slice(-5).reverse());
const backtestHistoryRows = computed(() => (props.backtestHistory || []).slice(0, 8));
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
.alert-summary-card {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(123, 231, 255, 0.18);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 26, 36, 0.96), rgba(5, 16, 24, 0.96));
}

.alert-summary-title {
  font-family: "Syne", sans-serif;
  font-size: 13px;
  font-weight: 700;
  color: var(--text1);
}

.alert-summary-subtitle {
  margin-top: 4px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--text3);
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.alert-card {
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(8, 14, 22, 0.92);
}

.alert-card.triggered {
  border-color: rgba(245, 166, 35, 0.34);
  box-shadow: 0 0 0 1px rgba(245, 166, 35, 0.12) inset;
}

.alert-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.alert-tk {
  font-family: "Syne", sans-serif;
  font-size: 14px;
  font-weight: 700;
}

.alert-cond {
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text2);
}

.alert-badge {
  flex-shrink: 0;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
}

.alert-badge.active {
  background: rgba(0, 217, 163, 0.12);
  color: var(--green);
}

.alert-badge.paused {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text2);
}

.alert-badge.triggered {
  background: rgba(245, 166, 35, 0.14);
  color: var(--yellow);
}

.alert-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.alert-meta-item {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  font-size: 10px;
  line-height: 1.5;
  color: var(--text3);
}

.alert-meta-item span:last-child {
  display: block;
  margin-top: 2px;
  color: var(--text1);
}

.alert-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.alert-action-btn {
  flex: 1;
  min-width: 0;
  padding: 7px 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text1);
  font-size: 11px;
  cursor: pointer;
}

.alert-action-btn.pause {
  border-color: rgba(123, 231, 255, 0.24);
}

.alert-action-btn.log {
  border-color: rgba(255, 209, 102, 0.24);
}

.alert-action-btn.delete {
  border-color: rgba(255, 77, 106, 0.24);
  color: #ff7d91;
}

.alert-log-card {
  margin-top: 10px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(3, 10, 16, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.alert-log-title {
  font-size: 10px;
  letter-spacing: 0.04em;
  color: var(--text3);
}

.alert-log-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.alert-log-row {
  padding: 8px 9px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
}

.alert-log-row-top,
.alert-log-row-bottom {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 10px;
  line-height: 1.5;
}

.alert-log-row-top {
  color: var(--text2);
}

.alert-log-row-bottom {
  margin-top: 4px;
  color: var(--text3);
}

.alert-log-empty {
  margin-top: 8px;
  font-size: 10px;
  color: var(--text3);
}

.alert-context-card {
  margin-top: 10px;
  padding: 9px 10px;
  border-radius: 10px;
  background: rgba(123, 231, 255, 0.05);
  border: 1px solid rgba(123, 231, 255, 0.12);
}

.alert-context-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 10px;
  line-height: 1.5;
  color: var(--text2);
}

.alert-context-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.alert-context-tag {
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(123, 231, 255, 0.12);
  color: #bfefff;
  font-size: 10px;
  line-height: 1.4;
}

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
