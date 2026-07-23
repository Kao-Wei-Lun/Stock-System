<template>
  <div class="pt-dashboard">
    <!-- ─── Header ────────────────────────────────────────── -->
    <header class="pt-header">
      <div class="pt-header-left">
        <button class="pt-back-btn" @click="$router.push('/')">← 返回</button>
        <h1 class="pt-title">
          <span class="pt-title-icon">⚡</span>
          TMF 模擬交易
        </h1>
        <span class="pt-badge">模擬交易</span>
      </div>
      <div class="pt-header-right">
        <div class="pt-status-pill" :class="activeBotStatusClass">
          <span class="pt-status-dot"></span>
          {{ activeBotStatusLabel }}
        </div>
      </div>
    </header>

    <div class="pt-simulation-notice" role="note" data-testid="simulation-safety-notice">
      <strong>僅供模擬與策略驗證</strong>
      <span>本頁不會送出任何真實委託；帳戶、Bot 與回放結果皆為模擬資料。</span>
    </div>

    <!-- ─── Tab Bar ───────────────────────────────────────── -->
    <nav class="pt-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="pt-tab"
        :class="{ active: activeTab === tab.key }"
        :aria-current="activeTab === tab.key ? 'page' : undefined"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- ─── Account Setup Tab ─────────────────────────────── -->
    <PaperAccountSection v-if="activeTab === 'setup'">
      <div v-if="sectionLoading.accounts" class="pt-inline-state" data-testid="accounts-loading">帳戶資料載入中…</div>
      <div v-else-if="sectionErrors.accounts" class="pt-inline-state error" data-testid="accounts-error">
        <span>帳戶資料載入失敗：{{ sectionErrors.accounts }}</span>
        <button class="pt-btn pt-btn-sm" @click="loadAccounts">重試</button>
      </div>
      <div v-else-if="!accounts.length" class="pt-inline-state" data-testid="accounts-empty">
        尚未建立模擬帳戶，可先使用下方表單建立。
      </div>
      <div v-if="sectionLoading.margin" class="pt-inline-state" data-testid="margin-loading">
        保證金資料更新中…
      </div>
      <div
        v-else-if="sectionErrors.margin"
        class="pt-inline-state warning"
        role="status"
        data-testid="margin-error"
      >
        <span>保證金供應商暫時無法使用：{{ sectionErrors.margin }}。既有帳戶與歷史回放仍可使用。</span>
        <button class="pt-btn pt-btn-sm" @click="previewAccountMargin">重試</button>
      </div>
      <div v-else-if="!marginPreview" class="pt-inline-state" data-testid="margin-fallback">
        尚未向供應商更新；目前使用資料庫保存值或商品預設保證金。
      </div>
      <div class="pt-card">
        <h2 class="pt-card-title">帳戶設定</h2>
        <div class="pt-form-grid">
          <div class="pt-field">
            <label>帳戶名稱</label>
            <input v-model="accountForm.name" type="text" placeholder="TMF 模擬帳戶" />
          </div>
          <div class="pt-field">
            <label>初始權益 (TWD)</label>
            <input v-model.number="accountForm.starting_equity" type="number" />
          </div>
          <div class="pt-field">
            <label>原始保證金 / 口</label>
            <div class="pt-margin-auto-box">
              <div class="pt-margin-value">{{ formatCurrency(marginPreview?.initial_margin_per_contract ?? activeInitialMargin) }}</div>
              <div class="pt-margin-meta">{{ marginPreviewLabel }}</div>
            </div>
          </div>
          <div class="pt-field">
            <label>單日虧損上限 (%)</label>
            <input v-model.number="riskForm.daily_loss_limit_pct" type="number" step="0.01" />
          </div>
          <div class="pt-field">
            <label>最大回撤上限 (%)</label>
            <input v-model.number="riskForm.max_drawdown_pct" type="number" step="0.01" />
          </div>
          <div class="pt-field">
            <label>口數硬上限</label>
            <input v-model.number="riskForm.max_contracts_hard" type="number" />
          </div>
          <div class="pt-field">
            <label>保證金使用率上限</label>
            <input v-model.number="riskForm.max_margin_usage_pct" type="number" step="0.01" />
          </div>
          <div class="pt-field">
            <label>單筆風險比例</label>
            <input v-model.number="riskForm.risk_per_trade_pct" type="number" step="0.01" />
          </div>
          <div class="pt-field">
            <label>總部位風險比例</label>
            <input v-model.number="riskForm.total_position_risk_pct" type="number" step="0.01" />
          </div>
          <div class="pt-field">
            <label>壓力測試點數</label>
            <input v-model.number="riskForm.stress_points" type="number" />
          </div>
        </div>
        <div class="pt-card-actions">
          <button class="pt-btn pt-btn-primary" :disabled="creatingAccount" @click="createAccount">
            {{ creatingAccount ? '建立中...' : '建立帳戶' }}
          </button>
          <button class="pt-btn" :disabled="marginPreviewLoading" @click="previewAccountMargin">
            {{ marginPreviewLoading ? '\u67e5\u8a62\u4e2d...' : '\u9810\u67e5\u4fdd\u8b49\u91d1' }}
          </button>
        </div>
      </div>

      <!-- Account List -->
      <div v-if="accounts.length" class="pt-card">
        <h2 class="pt-card-title">已建帳戶</h2>
        <div class="pt-card-actions pt-card-actions-top">
          <button class="pt-btn pt-btn-sm" :disabled="refreshingAllMargins" @click="refreshAllMargins">
            {{ refreshAllMarginsLabel }}
          </button>
        </div>
        <div class="pt-table-wrap">
          <table class="pt-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>名稱</th>
                <th>商品</th>
                <th>初始權益</th>
                <th>保證金</th>
                <th>建立時間</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="acct in accounts" :key="acct.id">
                <td>{{ acct.id }}</td>
                <td>{{ acct.name }}</td>
                <td>{{ acct.product_symbol }}</td>
                <td>{{ formatCurrency(acct.starting_equity) }}</td>
                <td>
                  <div>{{ formatCurrency(acct.initial_margin_per_contract) }}</div>
                  <div class="pt-muted-line">{{ marginMetaLabel(acct) }}</div>
                  <div v-if="acct.margin_last_success_at" class="pt-muted-line">
                    最後成功：{{ formatTime(acct.margin_last_success_at) }}
                  </div>
                  <div v-if="acct.margin_last_error || acct.margin_sync_error" class="pt-error-line">
                    {{ marginErrorLabel(acct) }}
                  </div>
                  <div v-if="acct.margin_next_retry_at" class="pt-muted-line">
                    下次自動嘗試：{{ formatTime(acct.margin_next_retry_at) }}
                  </div>
                </td>
                <td>{{ formatTime(acct.created_at) }}</td>
                <td>
                  <button
                    class="pt-btn pt-btn-sm"
                    :disabled="refreshingAccountMargins[acct.id]"
                    @click="refreshAccountMargin(acct)"
                  >
                    {{ refreshingAccountMargins[acct.id] ? refreshingAccountMarginBusyLabel : refreshAccountMarginLabel }}
                  </button>
                  <button
                    class="pt-btn pt-btn-sm pt-btn-danger"
                    :disabled="deletingAccounts[acct.id]"
                    @click="deleteAccount(acct)"
                  >
                    {{ deletingAccounts[acct.id] ? '刪除中' : '刪除' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </PaperAccountSection>

    <!-- ─── Bot Management Tab ────────────────────────────── -->
    <PaperBotSection v-if="activeTab === 'bots'">
      <div v-if="sectionLoading.bots" class="pt-inline-state" data-testid="bots-loading">Bot 資料載入中…</div>
      <div v-else-if="sectionErrors.bots" class="pt-inline-state error" data-testid="bots-error">
        <span>Bot 資料載入失敗：{{ sectionErrors.bots }}</span>
        <button class="pt-btn pt-btn-sm" @click="loadBots">重試</button>
      </div>
      <div v-else-if="!bots.length" class="pt-inline-state" data-testid="bots-empty">
        尚未建立 Bot；建立後才會顯示於清單。
      </div>
      <div class="pt-card">
        <h2 class="pt-card-title">建立 Bot</h2>
        <div class="pt-form-grid">
          <div class="pt-field">
            <label>帳戶</label>
            <select v-model.number="botForm.account_id">
              <option v-for="acct in accounts" :key="acct.id" :value="acct.id">
                {{ acct.name }} (ID: {{ acct.id }})
              </option>
            </select>
          </div>
          <div class="pt-field">
            <label>Bot 名稱</label>
            <input v-model="botForm.name" type="text" placeholder="TMF 日盤 Bot" />
          </div>
          <div class="pt-field">
            <label>模式</label>
            <select v-model="botForm.mode">
              <option value="realtime">即時模擬</option>
              <option value="replay">回放模擬</option>
            </select>
          </div>
          <div class="pt-field">
            <label>持倉政策</label>
            <select v-model="botForm.holding_policy">
              <option value="day_only">僅日內</option>
              <option value="overnight_allowed">允許隔夜</option>
            </select>
          </div>
          <div class="pt-field">
            <label>策略引擎</label>
            <select v-model="botStrategyForm.strategy_type">
              <option value="tmf_auto_kd_psar_5m">TMF Auto: 5m KD/PSAR momentum</option>
              <option value="tmf_pullback_breakout">TMF C: 1m pullback breakout</option>
              <option value="tmf_psar_flip">TMF PSAR: 3m flip confirmation</option>
              <option value="tmf_kd_macd_ma_v14">TMF KD/MACD/MA v1.4</option>
              <option value="tmf_kd_macd_ma_v14_5m_kd">TMF KD/MACD/MA v1.4 + 5m KD</option>
              <option value="tmf_kd_macd_ma_v14_15m_kd">TMF KD/MACD/MA v1.4 + 15m KD</option>
              <option value="tmf_kd_macd_ma_v14_15m_macd">TMF KD/MACD/MA v1.4 + 15m MACD</option>
              <option value="v1">V1：固定點數停損停利</option>
              <option value="v2">V2：ATR 動態加碼與移動停損</option>
            </select>
          </div>
          <div class="pt-field" v-if="botStrategyForm.strategy_type === 'v2'">
            <label>V2 策略版本</label>
            <select v-model="botStrategyForm.v2_variant">
              <option v-for="option in v2VariantOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="pt-field" v-if="botStrategyForm.strategy_type === 'v1'">
            <label>停損點數</label>
            <input v-model.number="botStrategyForm.stop_loss_points" type="number" />
          </div>
          <div class="pt-field" v-if="botStrategyForm.strategy_type === 'v1'">
            <label>停利點數</label>
            <input v-model.number="botStrategyForm.take_profit_points" type="number" />
          </div>
        </div>
        <FuturesRiskSizerPanel
          :sizing="riskSizingPreview"
          :loading="riskSizingLoading"
          :error="riskSizingError"
        />
        <div class="pt-card-actions">
          <button class="pt-btn pt-btn-primary" :disabled="creatingBot" @click="createBot">
            {{ creatingBot ? '建立中...' : '建立 Bot' }}
          </button>
        </div>
      </div>

      <!-- Bot List -->
      <div v-if="bots.length" class="pt-card">
        <div class="pt-card-heading">
          <h2 class="pt-card-title">Bot 列表</h2>
          <button
            class="pt-btn pt-btn-sm pt-btn-success"
            :disabled="startingAllBots || !startableBotCount"
            @click="startAllBots"
          >
            {{ startingAllBots ? '啟動中...' : `啟動全部 (${startableBotCount})` }}
          </button>
        </div>
        <div class="pt-table-wrap">
          <table class="pt-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>名稱</th>
                <th>模式</th>
                <th>策略</th>
                <th>狀態</th>
                <th>K 棒數</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="bot in bots" :key="bot.id">
                <td>{{ bot.id }}</td>
                <td>{{ bot.name }}</td>
                <td>
                  <span class="pt-mode-badge" :class="bot.mode">{{ bot.mode === 'realtime' ? '即時' : '回放' }}</span>
                </td>
                <td>{{ strategyConfigLabel(bot.strategy_config) }}</td>
                <td>
                  <span class="pt-status-badge" :class="bot.status">{{ botStatusLabel(bot.status) }}</span>
                </td>
                <td>{{ bot.bar_count }}</td>
                <td>
                  <div class="pt-btn-group">
                    <button
                      v-if="bot.status !== 'running'"
                      class="pt-btn pt-btn-sm pt-btn-success"
                      @click="startBot(bot.id)"
                    >啟動</button>
                    <button
                      v-if="bot.status === 'running'"
                      class="pt-btn pt-btn-sm pt-btn-danger"
                      @click="stopBot(bot.id)"
                    >停止</button>
                    <button
                      class="pt-btn pt-btn-sm"
                      @click="refreshBotState(bot.id)"
                    >狀態</button>
                    <button
                      class="pt-btn pt-btn-sm pt-btn-danger"
                      :disabled="bot.status === 'running' || deletingBots[bot.id]"
                      @click="deleteBot(bot)"
                    >
                      {{ deletingBots[bot.id] ? '刪除中' : '刪除' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Live Bot State -->
      <div v-if="liveBotState" class="pt-card">
        <h2 class="pt-card-title">
          即時 Bot 狀態
          <span class="pt-live-dot"></span>
        </h2>
        <div class="pt-stats-grid">
          <div class="pt-stat">
            <div class="pt-stat-label">權益</div>
            <div class="pt-stat-value">{{ formatCurrency(liveBotState.account?.equity) }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">未平倉損益</div>
            <div class="pt-stat-value" :class="pnlClass(liveBotState.account?.unrealized_pnl)">
              {{ formatCurrency(liveBotState.account?.unrealized_pnl) }}
            </div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">已實現損益</div>
            <div class="pt-stat-value" :class="pnlClass(liveBotState.account?.total_realized_pnl)">
              {{ formatCurrency(liveBotState.account?.total_realized_pnl) }}
            </div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">今日損益</div>
            <div class="pt-stat-value" :class="pnlClass(liveBotState.account?.daily_realized_pnl)">
              {{ formatCurrency(liveBotState.account?.daily_realized_pnl) }}
            </div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">持倉</div>
            <div class="pt-stat-value">{{ liveBotState.account?.position?.qty || 0 }} 口</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">方向判斷</div>
            <div class="pt-stat-value">{{ directionLabel }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">策略版本</div>
            <div class="pt-stat-value">{{ strategyConfigLabel(liveBotState.strategy_config) }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">K 棒數</div>
            <div class="pt-stat-value">{{ liveBotState.bar_count?.toLocaleString() }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">最新 K 價</div>
            <div class="pt-stat-value">{{ liveBotState.latest_realtime_bar?.close ?? '--' }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">K 狀態</div>
            <div class="pt-stat-value">{{ liveBotState.latest_realtime_bar_is_partial ? '形成中' : '完成' }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">V2 初始停損</div>
            <div class="pt-stat-value">{{ formatPoints(liveBotState.v2_stop_distances?.initial_stop) }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">V2 移動停損</div>
            <div class="pt-stat-value">{{ formatPoints(liveBotState.v2_stop_distances?.trailing_stop) }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">預熱 K 棒</div>
            <div class="pt-stat-value">{{ liveBotState.warmup_bar_count?.toLocaleString() || 0 }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">資料來源</div>
            <div class="pt-stat-value">{{ dataSourceLabel }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">商品合約</div>
            <div class="pt-stat-value">{{ liveBotState.resolved_product_symbol || '--' }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">方向合約</div>
            <div class="pt-stat-value">{{ liveBotState.resolved_direction_symbol || '--' }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">最大回撤</div>
            <div class="pt-stat-value pt-negative">{{ ((liveBotState.account?.current_drawdown_pct || 0) * 100).toFixed(2) }}%</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">手續費</div>
            <div class="pt-stat-value">{{ formatCurrency(liveBotState.account?.total_fees) }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">待成交</div>
            <div class="pt-stat-value">{{ liveBotState.pending_orders || 0 }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">冷卻中</div>
            <div class="pt-stat-value">{{ liveBotState.account?.cooldown_remaining_bars || 0 }} bar</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">總成交</div>
            <div class="pt-stat-value">{{ liveBotState.total_fills || 0 }}</div>
          </div>
        </div>

        <!-- Current Position -->
        <div v-if="liveBotState.account?.position" class="pt-sub-section">
          <h3 class="pt-sub-title">當前持倉</h3>
          <div class="pt-stats-grid">
            <div class="pt-stat">
              <div class="pt-stat-label">方向</div>
              <div class="pt-stat-value">
                <span class="pt-side-badge" :class="liveBotState.account.position.side">
                  {{ liveBotState.account.position.side === 'buy' ? '多' : '空' }}
                </span>
              </div>
            </div>
            <div class="pt-stat">
              <div class="pt-stat-label">口數</div>
              <div class="pt-stat-value">{{ liveBotState.account.position.qty }}</div>
            </div>
            <div class="pt-stat">
              <div class="pt-stat-label">進場均價</div>
              <div class="pt-stat-value">{{ liveBotState.account.position.avg_entry_price }}</div>
            </div>
            <div class="pt-stat">
              <div class="pt-stat-label">最新價</div>
              <div class="pt-stat-value">{{ liveBotState.account.position.last_price }}</div>
            </div>
            <div class="pt-stat">
              <div class="pt-stat-label">未實現損益</div>
              <div class="pt-stat-value" :class="pnlClass(liveBotState.account.position.unrealized_pnl)">
                {{ formatCurrency(liveBotState.account.position.unrealized_pnl) }}
              </div>
            </div>
          </div>
        </div>

        <!-- Live Trades -->
        <div v-if="liveBotState.trades?.length" class="pt-sub-section">
          <h3 class="pt-sub-title">交易紀錄 ({{ liveBotState.trades.length }})</h3>
          <div class="pt-table-wrap pt-table-scroll">
            <table class="pt-table">
              <thead>
                <tr>
                  <th>進場時間</th><th>方向</th><th>口數</th>
                  <th>進場價</th><th>出場價</th><th>淨損益</th><th>出場原因</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in liveBotState.trades" :key="t.trade_id">
                  <td>{{ formatTime(t.entry_time) }}</td>
                  <td><span class="pt-side-badge" :class="t.side">{{ t.side === 'buy' ? '多' : '空' }}</span></td>
                  <td>{{ t.qty }}</td>
                  <td>{{ t.entry_price }}</td>
                  <td>{{ t.exit_price }}</td>
                  <td :class="pnlClass(t.net_pnl)">{{ formatCurrency(t.net_pnl) }}</td>
                  <td class="pt-reason" :title="t.exit_reason || ''">{{ t.exit_reason }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Risk Events -->
        <div v-if="liveBotState.risk_events?.length" class="pt-sub-section">
          <h3 class="pt-sub-title">風控事件 ({{ liveBotState.risk_events.length }})</h3>
          <div class="pt-table-wrap pt-table-scroll">
            <table class="pt-table">
              <thead><tr><th>類型</th><th>時間</th><th>詳情</th></tr></thead>
              <tbody>
                <tr v-for="(evt, i) in liveBotState.risk_events" :key="i">
                  <td>{{ evt.event_type }}</td>
                  <td>{{ formatTime(evt.timestamp || evt.details?.bar_time) }}</td>
                  <td class="pt-reason pt-detail-cell">
                    <pre class="pt-detail-text">{{ formatDetails(evt.details) }}</pre>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </PaperBotSection>

    <!-- ─── Replay Tab ────────────────────────────────────── -->
    <PaperReplaySection v-if="activeTab === 'replay'">
      <div v-if="sectionLoading.replay" class="pt-inline-state" data-testid="replay-loading">回放紀錄載入中…</div>
      <div v-else-if="sectionErrors.replay" class="pt-inline-state error" data-testid="replay-error">
        <span>回放紀錄載入失敗：{{ sectionErrors.replay }}</span>
        <button class="pt-btn pt-btn-sm" @click="loadReplayRuns">重試</button>
      </div>
      <div v-else-if="!replayRuns.length" class="pt-inline-state" data-testid="replay-empty">
        尚無歷史回放紀錄。
      </div>
      <div class="pt-card">
        <h2 class="pt-card-title">歷史回放</h2>
        <div class="pt-form-grid">
          <div class="pt-field">
            <label>帳戶</label>
            <select v-model.number="replayForm.account_id">
              <option v-for="acct in accounts" :key="acct.id" :value="acct.id">
                {{ acct.name }} (ID: {{ acct.id }})
              </option>
            </select>
          </div>
          <div class="pt-field">
            <label>開始日期</label>
            <input v-model="replayForm.start_date" type="date" />
          </div>
          <div class="pt-field">
            <label>結束日期</label>
            <input v-model="replayForm.end_date" type="date" />
          </div>
          <div class="pt-field">
            <label>回放策略引擎</label>
            <select v-model="replayStrategyForm.strategy_type">
              <option value="tmf_auto_kd_psar_5m">TMF Auto: 5m KD/PSAR momentum</option>
              <option value="tmf_pullback_breakout">TMF C: 1m pullback breakout</option>
              <option value="tmf_psar_flip">TMF PSAR: 3m flip confirmation</option>
              <option value="tmf_kd_macd_ma_v14">TMF KD/MACD/MA v1.4</option>
              <option value="tmf_kd_macd_ma_v14_5m_kd">TMF KD/MACD/MA v1.4 + 5m KD</option>
              <option value="tmf_kd_macd_ma_v14_15m_kd">TMF KD/MACD/MA v1.4 + 15m KD</option>
              <option value="tmf_kd_macd_ma_v14_15m_macd">TMF KD/MACD/MA v1.4 + 15m MACD</option>
              <option value="v1">V1：固定點數停損停利</option>
              <option value="v2">V2：ATR 動態加碼與移動停損</option>
            </select>
          </div>
          <div class="pt-field" v-if="replayStrategyForm.strategy_type === 'v2'">
            <label>回放 V2 策略版本</label>
            <select v-model="replayStrategyForm.v2_variant">
              <option v-for="option in v2VariantOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <div class="pt-field" v-if="replayStrategyForm.strategy_type === 'v1'">
            <label>回放停損點數</label>
            <input v-model.number="replayStrategyForm.stop_loss_points" type="number" />
          </div>
          <div class="pt-field" v-if="replayStrategyForm.strategy_type === 'v1'">
            <label>回放停利點數</label>
            <input v-model.number="replayStrategyForm.take_profit_points" type="number" />
          </div>
        </div>
        <FuturesRiskSizerPanel
          :sizing="riskSizingPreview"
          :loading="riskSizingLoading"
          :error="riskSizingError"
        />
        <div class="pt-card-actions">
          <button class="pt-btn pt-btn-primary" :disabled="runningReplay || !replayForm.account_id" @click="runReplay">
            {{ runningReplay ? '回放中...' : '執行回放' }}
          </button>
        </div>
      </div>

      <!-- Replay Result -->
      <div v-if="replayResult" class="pt-card">
        <h2 class="pt-card-title">回放結果</h2>
        <div class="pt-stats-grid">
          <div class="pt-stat">
            <div class="pt-stat-label">總交易數</div>
            <div class="pt-stat-value">{{ replayResult.summary?.trade_count || 0 }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">勝率</div>
            <div class="pt-stat-value">{{ replayResult.summary?.win_rate || 0 }}%</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">總損益</div>
            <div class="pt-stat-value" :class="pnlClass(replayResult.summary?.total_pnl)">
              {{ formatCurrency(replayResult.summary?.total_pnl) }}
            </div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">報酬率</div>
            <div class="pt-stat-value" :class="pnlClass(replayResult.summary?.total_return_pct)">
              {{ (replayResult.summary?.total_return_pct || 0).toFixed(2) }}%
            </div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">最大回撤</div>
            <div class="pt-stat-value pt-negative">{{ (replayResult.summary?.max_drawdown_pct || 0).toFixed(2) }}%</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">利潤因子</div>
            <div class="pt-stat-value">{{ replayResult.summary?.profit_factor || '--' }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">最大單筆獲利</div>
            <div class="pt-stat-value pt-positive">{{ formatCurrency(replayResult.summary?.max_win) }}</div>
          </div>
          <div class="pt-stat">
            <div class="pt-stat-label">最大單筆虧損</div>
            <div class="pt-stat-value pt-negative">{{ formatCurrency(replayResult.summary?.max_loss) }}</div>
          </div>
        </div>

        <!-- Trade List -->
        <div v-if="replayResult.trades?.length" class="pt-sub-section">
          <h3 class="pt-sub-title">交易紀錄 ({{ replayResult.trades.length }})</h3>
          <div class="pt-table-wrap pt-table-scroll">
            <table class="pt-table">
              <thead>
                <tr>
                  <th>進場時間</th>
                  <th>方向</th>
                  <th>口數</th>
                  <th>進場價</th>
                  <th>出場價</th>
                  <th>毛利</th>
                  <th>手續費</th>
                  <th>淨損益</th>
                  <th>出場原因</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="t in replayResult.trades" :key="t.trade_id">
                  <td>{{ formatTime(t.entry_time) }}</td>
                  <td>
                    <span class="pt-side-badge" :class="t.side">{{ t.side === 'buy' ? '多' : '空' }}</span>
                  </td>
                  <td>{{ t.qty }}</td>
                  <td>{{ t.entry_price }}</td>
                  <td>{{ t.exit_price }}</td>
                  <td :class="pnlClass(t.gross_pnl)">{{ formatCurrency(t.gross_pnl) }}</td>
                  <td>{{ formatCurrency(t.fee_total) }}</td>
                  <td :class="pnlClass(t.net_pnl)">{{ formatCurrency(t.net_pnl) }}</td>
                  <td class="pt-reason" :title="t.exit_reason || ''">{{ t.exit_reason }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Risk Events -->
        <div v-if="replayResult.risk_events?.length" class="pt-sub-section">
          <h3 class="pt-sub-title">風控事件 ({{ replayResult.risk_events.length }})</h3>
          <div class="pt-table-wrap pt-table-scroll">
            <table class="pt-table">
              <thead>
                <tr>
                  <th>類型</th>
                  <th>時間</th>
                  <th>詳情</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(evt, i) in replayResult.risk_events" :key="i">
                  <td>{{ evt.event_type }}</td>
                  <td>{{ formatTime(evt.timestamp || evt.details?.bar_time) }}</td>
                  <td class="pt-reason pt-detail-cell">
                    <pre class="pt-detail-text">{{ formatDetails(evt.details) }}</pre>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Past Replays -->
      <div v-if="replayRuns.length" class="pt-card">
        <h2 class="pt-card-title">歷史回放紀錄</h2>
        <div class="pt-table-wrap">
          <table class="pt-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>日期範圍</th>
                <th>交易數</th>
                <th>報酬率</th>
                <th>最大回撤</th>
                <th>勝率</th>
                <th>建立時間</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="run in replayRuns" :key="run.id">
                <td>{{ run.id }}</td>
                <td>{{ run.start_date }} ~ {{ run.end_date }}</td>
                <td>{{ run.trade_count }}</td>
                <td :class="pnlClass(run.total_return_pct)">{{ run.total_return_pct?.toFixed(2) }}%</td>
                <td class="pt-negative">{{ run.max_drawdown_pct?.toFixed(2) }}%</td>
                <td>{{ run.win_rate_pct?.toFixed(1) }}%</td>
                <td>{{ formatTime(run.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </PaperReplaySection>

    <!-- ─── Toast ─────────────────────────────────────────── -->
    <div v-if="toast" class="pt-toast" :class="toast.type" @click="toast = null">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from "vue";
import FuturesRiskSizerPanel from "./paper/FuturesRiskSizerPanel.vue";
import PaperAccountSection from "./paper/PaperAccountSection.vue";
import PaperBotSection from "./paper/PaperBotSection.vue";
import PaperReplaySection from "./paper/PaperReplaySection.vue";
import { createPaperApi } from "../composables/paper/paperApi";
import { usePaperAccounts } from "../composables/paper/usePaperAccounts";
import { usePaperBots } from "../composables/paper/usePaperBots";
import { usePaperMargin } from "../composables/paper/usePaperMargin";
import { usePaperReplays } from "../composables/paper/usePaperReplays";

const DEFAULT_INITIAL_MARGIN = 28900;

const activeTab = ref("setup");
const tabs = [
  { key: "setup", label: "帳戶設定" },
  { key: "bots", label: "Bot 管理" },
  { key: "replay", label: "歷史回放" },
];

// ─── State ───────────────────────────────────────────────────
const toast = ref(null);
const riskSizingPreview = ref(null);
const riskSizingLoading = ref(false);
const riskSizingError = ref("");
const sectionLoading = reactive({ accounts: true, bots: true, replay: true, margin: false });
const sectionErrors = reactive({ accounts: "", bots: "", replay: "", margin: "" });
let _riskSizingTimer = null;
const paperApi = createPaperApi();
const { apiFetch } = paperApi;

const v2VariantOptions = [
  { value: "baseline", label: "V2 原始動態 ATR" },
  { value: "v2_b15_c2", label: "前一版 B15+C2" },
  { value: "v2_profit_candidate", label: "損益候選版" },
  { value: "v2_winrate_candidate", label: "勝率候選版" },
];

const {
  bots,
  liveBotState,
  creatingBot,
  startingAllBots,
  deletingBots,
  botForm,
  botStrategyForm,
  runningBotIds,
  startableBotCount,
  activeBotStatusClass,
  activeBotStatusLabel,
  directionLabel,
  dataSourceLabel,
  loadBots: loadBotRecords,
  createBot: createBotRecord,
  removeBot,
  startBot: startBotRecord,
  startAllBots: startAllBotRecords,
  stopBot: stopBotRecord,
  refreshBotState: refreshBotStateRecord,
  startPolling: startBotPolling,
  stopPolling: stopBotPolling,
} = usePaperBots({ apiFetch, notify: showToast, sectionLoading, sectionErrors });

const {
  replayRuns,
  replayResult,
  runningReplay,
  replayStrategyForm,
  replayForm,
  loadReplayRuns: loadReplayRecords,
  runReplay: runReplayRecord,
} = usePaperReplays({ apiFetch, notify: showToast, sectionLoading, sectionErrors });

const {
  accounts,
  accountForm,
  riskForm,
  creatingAccount,
  deletingAccounts,
  loadAccounts: loadAccountRecords,
  createAccount: createAccountRecord,
  removeAccount,
} = usePaperAccounts({ apiFetch, notify: showToast, sectionLoading, sectionErrors });

const {
  marginPreview,
  marginPreviewLoading,
  refreshingAllMargins,
  refreshingAccountMargins,
  previewAccountMargin: previewMarginRecord,
  refreshAccountMargin: refreshAccountMarginRecord,
  refreshAllMargins: refreshAllMarginRecords,
} = usePaperMargin({
  apiFetch,
  notify: showToast,
  accountForm,
  sectionLoading,
  sectionErrors,
  reloadAccounts: () => loadAccountRecords({ botForm, replayForm }),
});

// ─── Computed ────────────────────────────────────────────────

const selectedBotAccount = computed(() => (
  accounts.value.find((acct) => Number(acct.id) === Number(botForm.account_id)) || null
));

const selectedReplayAccount = computed(() => (
  accounts.value.find((acct) => Number(acct.id) === Number(replayForm.account_id)) || null
));

const riskSizingCapital = computed(() => {
  if (activeTab.value === "replay") {
    return selectedReplayAccount.value?.starting_equity
      ?? accountForm.starting_equity;
  }
  if (activeTab.value === "bots") {
    return selectedBotAccount.value?.equity
      ?? selectedBotAccount.value?.starting_equity
      ?? accountForm.starting_equity;
  }
  return accountForm.starting_equity;
});

const activeInitialMargin = computed(() => {
  const previewMargin = marginPreview.value?.initial_margin_per_contract ?? DEFAULT_INITIAL_MARGIN;
  if (activeTab.value === "bots") {
    return selectedBotAccount.value?.initial_margin_per_contract
      ?? previewMargin;
  }
  if (activeTab.value === "replay") {
    return selectedReplayAccount.value?.initial_margin_per_contract
      ?? previewMargin;
  }
  return previewMargin;
});

const marginPreviewLabel = computed(() => {
  if (marginPreviewLoading.value) return "\u5bcc\u90a6 API \u67e5\u8a62\u4e2d";
  const preview = marginPreview.value;
  if (!preview) return "目前使用持久化／商品預設值；按「預查保證金」才會連線更新";
  return `${marginSourceLabel(preview.margin_source || preview.source)} · ${preview.margin_reference_symbol || "TMF"} · ${formatTime(preview.margin_last_success_at || preview.margin_synced_at)}`;
});
const refreshAllMarginsLabel = computed(() => (
  refreshingAllMargins.value ? "\u66f4\u65b0\u4e2d" : "\u66f4\u65b0\u5168\u90e8\u4fdd\u8b49\u91d1"
));
const refreshAccountMarginLabel = "\u66f4\u65b0\u4fdd\u8b49\u91d1";
const refreshAccountMarginBusyLabel = "\u66f4\u65b0\u4e2d";

const activeRiskConfig = computed(() => {
  if (activeTab.value === "bots" && selectedBotAccount.value?.risk_config) {
    return selectedBotAccount.value.risk_config;
  }
  if (activeTab.value === "replay" && selectedReplayAccount.value?.risk_config) {
    return selectedReplayAccount.value.risk_config;
  }
  return riskForm;
});

const activeRiskStrategyForm = computed(() => (
  activeTab.value === "replay" ? replayStrategyForm : botStrategyForm
));

function showToast(message, type = "info") {
  toast.value = { message, type };
  setTimeout(() => { toast.value = null; }, 4000);
}

function buildRiskSizingPayload() {
  const riskConfig = activeRiskConfig.value || {};
  return {
    product_symbol: "TMF",
    futures_capital: Number(riskSizingCapital.value || 0),
    initial_margin: Number(activeInitialMargin.value || 0),
    stop_loss_points: Number(riskSizingStopLossPoints(activeRiskStrategyForm.value) || 0),
    stress_points: Number(riskConfig.stress_points ?? riskForm.stress_points ?? 0),
    margin_usage_limit: Number(riskConfig.max_margin_usage_pct ?? riskForm.max_margin_usage_pct ?? 0),
    single_trade_risk_pct: Number(riskConfig.risk_per_trade_pct ?? riskForm.risk_per_trade_pct ?? 0),
    total_position_risk_pct: Number(riskConfig.total_position_risk_pct ?? riskForm.total_position_risk_pct ?? 0),
    user_max_contracts: Number(riskConfig.max_contracts_hard ?? riskForm.max_contracts_hard ?? 0),
  };
}

function riskSizingStopLossPoints(form) {
  const indicatorStops = {
    tmf_auto_kd_psar_5m: 160,
    tmf_pullback_breakout: 80,
    tmf_psar_flip: 120,
    tmf_kd_macd_ma_v14: 80,
    tmf_kd_macd_ma_v14_5m_kd: 80,
    tmf_kd_macd_ma_v14_15m_kd: 80,
    tmf_kd_macd_ma_v14_15m_macd: 80,
  };
  if (indicatorStops[form.strategy_type]) return indicatorStops[form.strategy_type];
  if (form.strategy_type !== "v2") return Number(form.stop_loss_points || 0);
  const variantStops = {
    v2_b15_c2: 150,
    v2_profit_candidate: 120,
    v2_winrate_candidate: 150,
  };
  return variantStops[form.v2_variant] || 120;
}

function buildStrategyConfig(form) {
  const stopLossPoints = riskSizingStopLossPoints(form);
  const profile = {
    stop_loss_points: Number(stopLossPoints || 0),
    take_profit_points: Number(form.take_profit_points || 0),
  };
  const config = {
    strategy_type: form.strategy_type,
    day_regular_profile: profile,
  };
  if (String(form.strategy_type || "").startsWith("tmf_kd_macd_ma_")) {
    config.day_open_profile = { ...profile };
  }
  if (form.strategy_type === "v2") {
    config.v2_variant = form.v2_variant || "baseline";
  }
  return config;
}

function strategyVariantLabel(value) {
  return v2VariantOptions.find((item) => item.value === value)?.label || "V2 原始動態 ATR";
}

function strategyTypeLabel(value) {
  return {
    v1: "V1 fixed points",
    tmf_auto_kd_psar_5m: "TMF Auto: 5m KD/PSAR momentum",
    tmf_pullback_breakout: "TMF C: 1m pullback breakout",
    tmf_psar_flip: "TMF PSAR: 3m flip confirmation",
    tmf_kd_macd_ma_v14: "TMF KD/MACD/MA v1.4",
    tmf_kd_macd_ma_v14_5m_kd: "TMF KD/MACD/MA v1.4 + 5m KD",
    tmf_kd_macd_ma_v14_15m_kd: "TMF KD/MACD/MA v1.4 + 15m KD",
    tmf_kd_macd_ma_v14_15m_macd: "TMF KD/MACD/MA v1.4 + 15m MACD",
  }[value] || "V1 fixed points";
}

function strategyConfigLabel(config) {
  const strategyType = config?.strategy_type || "v1";
  if (strategyType !== "v2") return strategyTypeLabel(strategyType);
  return strategyVariantLabel(config?.v2_variant || "baseline");
}

async function refreshRiskSizing() {
  if (!["bots", "replay"].includes(activeTab.value)) {
    riskSizingPreview.value = null;
    riskSizingError.value = "";
    return;
  }
  const payload = buildRiskSizingPayload();
  if (!payload.futures_capital || !payload.initial_margin || !payload.stop_loss_points) {
    riskSizingPreview.value = null;
    riskSizingError.value = "";
    return;
  }
  riskSizingLoading.value = true;
  try {
    const data = await apiFetch("/risk/position-size", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    riskSizingPreview.value = data.sizing;
    riskSizingError.value = "";
  } catch (e) {
    riskSizingError.value = e.message;
  } finally {
    riskSizingLoading.value = false;
  }
}

function scheduleRiskSizing() {
  if (_riskSizingTimer) clearTimeout(_riskSizingTimer);
  _riskSizingTimer = setTimeout(refreshRiskSizing, 250);
}

// ─── Actions ─────────────────────────────────────────────────
async function loadAccounts() {
  return loadAccountRecords({ botForm, replayForm });
}

async function loadBots() {
  return loadBotRecords();
}

async function loadReplayRuns() {
  return loadReplayRecords();
}

async function previewAccountMargin({ silent = false } = {}) {
  return previewMarginRecord({ silent });
}

async function refreshAccountMargin(account) {
  return refreshAccountMarginRecord(account);
}

async function refreshAllMargins() {
  return refreshAllMarginRecords();
}

async function createAccount() {
  return createAccountRecord({
    reload: loadAccounts,
    marginSyncErrorMessage: "帳戶已建立，保證金暫用預設值",
  });
}

async function createBot() {
  return createBotRecord(buildStrategyConfig);
}

async function deleteAccount(account) {
  if (!window.confirm(`確定要刪除帳戶「${account.name}」？相關 Bot、回放與交易紀錄也會一併刪除。`)) {
    return;
  }
  const relatedBotIds = bots.value
    .filter((bot) => Number(bot.account_id) === Number(account.id))
    .map((bot) => Number(bot.id));
  if (!await removeAccount(account)) return;
  if (Number(botForm.account_id) === Number(account.id)) botForm.account_id = null;
  if (Number(replayForm.account_id) === Number(account.id)) replayForm.account_id = null;
  if (relatedBotIds.includes(Number(liveBotState.value?.bot_id))) liveBotState.value = null;
  await Promise.all([loadAccounts(), loadBots(), loadReplayRuns()]);
}

async function deleteBot(bot) {
  if (!window.confirm(`確定要刪除 Bot「${bot.name}」？該 Bot 的模擬紀錄也會一併刪除。`)) {
    return;
  }
  if (await removeBot(bot)) await loadReplayRuns();
}

async function startBot(botId) {
  return startBotRecord(botId);
}

async function startAllBots() {
  return startAllBotRecords();
}

async function stopBot(botId) {
  return stopBotRecord(botId);
}

async function refreshBotState(botId) {
  return refreshBotStateRecord(botId);
}

async function runReplay() {
  return runReplayRecord(buildStrategyConfig);
}

function startPolling() {
  startBotPolling();
}

function stopPolling() {
  stopBotPolling();
}

// ─── Formatters ──────────────────────────────────────────────
function formatCurrency(val) {
  if (val == null) return "--";
  return new Intl.NumberFormat("zh-TW", { maximumFractionDigits: 0 }).format(val);
}

function formatPoints(val) {
  if (val == null || Number.isNaN(Number(val))) return "--";
  return `${Number(val).toFixed(1)} 點`;
}

function formatTime(val) {
  if (!val) return "--";
  try {
    return new Date(val).toLocaleString("zh-TW", {
      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  } catch { return val; }
}

function marginSourceLabel(source) {
  return {
    fubon_query_estimate_margin: "\u5bcc\u90a6 API",
    fallback_existing: "\u4fdd\u7559\u539f\u503c",
    fallback_product_spec: "\u5546\u54c1\u9810\u8a2d",
    fallback_default: "\u7cfb\u7d71\u9810\u8a2d",
    manual: "\u624b\u52d5",
  }[source] || source || "--";
}

function marginMetaLabel(account) {
  const source = marginSourceLabel(account?.margin_source);
  const symbol = account?.margin_reference_symbol || account?.product_symbol || "TMF";
  const syncedAt = formatTime(account?.margin_last_success_at || account?.margin_synced_at);
  return `${source} · ${symbol} · ${syncedAt}`;
}

function marginErrorLabel(account) {
  const category = {
    configuration_error: "設定錯誤（不會自動重試）",
    transient: "暫時連線錯誤",
    heartbeat_timeout: "連線逾時",
    session_invalid: "登入狀態失效",
    unknown: "更新錯誤",
  }[account?.margin_error_category] || "更新錯誤";
  return `${category}：${account?.margin_last_error || account?.margin_sync_error}`;
}

function formatDetails(value) {
  if (!value) return "{}";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function pnlClass(val) {
  if (val > 0) return "pt-positive";
  if (val < 0) return "pt-negative";
  return "";
}

function botStatusLabel(status) {
  return { idle: "待命", running: "運行中", stopped: "已停止", error: "錯誤" }[status] || status;
}

// ─── Init ────────────────────────────────────────────────────
watch(
  [
    () => activeTab.value,
    () => accountForm.starting_equity,
    () => replayForm.account_id,
    () => botForm.account_id,
    () => selectedBotAccount.value?.equity,
    () => selectedBotAccount.value?.starting_equity,
    () => selectedBotAccount.value?.initial_margin_per_contract,
    () => selectedReplayAccount.value?.starting_equity,
    () => selectedReplayAccount.value?.initial_margin_per_contract,
    () => JSON.stringify(selectedBotAccount.value?.risk_config || {}),
    () => JSON.stringify(selectedReplayAccount.value?.risk_config || {}),
    () => botStrategyForm.strategy_type,
    () => botStrategyForm.v2_variant,
    () => botStrategyForm.stop_loss_points,
    () => replayStrategyForm.strategy_type,
    () => replayStrategyForm.v2_variant,
    () => replayStrategyForm.stop_loss_points,
    () => riskForm.max_contracts_hard,
    () => riskForm.max_margin_usage_pct,
    () => riskForm.risk_per_trade_pct,
    () => riskForm.total_position_risk_pct,
    () => riskForm.stress_points,
  ],
  scheduleRiskSizing,
  { immediate: true },
);

onMounted(async () => {
  await Promise.all([loadAccounts(), loadBots(), loadReplayRuns()]);
  // Auto-start polling if any bot is running
  if (runningBotIds.value.length) {
    // Also fetch initial state for the first running bot
    await refreshBotState(runningBotIds.value[0]);
    startPolling();
  }
});

onUnmounted(() => {
  stopPolling();
  if (_riskSizingTimer) clearTimeout(_riskSizingTimer);
  paperApi.dispose();
});
</script>

<style scoped>
/* ─── Layout ──────────────────────────────────────────────── */
.pt-dashboard {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.pt-simulation-notice {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin: 0 0 18px;
  padding: 12px 14px;
  border: 1px solid rgba(255, 193, 92, 0.35);
  border-radius: 10px;
  color: rgba(255, 236, 202, 0.88);
  background: rgba(114, 70, 12, 0.18);
}

.pt-simulation-notice strong {
  color: #ffc15c;
}

.pt-inline-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(92, 139, 179, 0.28);
  border-radius: 8px;
  color: rgba(214, 230, 245, 0.78);
  background: rgba(17, 33, 48, 0.65);
}

.pt-inline-state.warning {
  border-color: rgba(255, 193, 92, 0.35);
  color: #ffd99b;
  background: rgba(114, 70, 12, 0.16);
}

.pt-inline-state.error {
  border-color: rgba(255, 92, 119, 0.4);
  color: #ff9aae;
  background: rgba(85, 22, 36, 0.35);
}

.pt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.pt-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.pt-back-btn {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  color: rgba(230,241,255,0.8);
  padding: 8px 14px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s;
}
.pt-back-btn:hover { background: rgba(255,255,255,0.1); }

.pt-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.pt-title-icon { font-size: 28px; }

.pt-badge {
  background: linear-gradient(135deg, rgba(90,170,255,0.2), rgba(56,119,179,0.3));
  color: #90deff;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
}

/* ─── Status Pill ────────────────────────────────────────── */
.pt-status-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 20px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  font-size: 13px;
}
.pt-status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #6b7d91;
}
.pt-status-pill.running .pt-status-dot { background: #5dd39e; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }

/* ─── Tabs ───────────────────────────────────────────────── */
.pt-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 24px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  padding-bottom: 4px;
}
.pt-tab {
  background: none;
  border: none;
  color: rgba(230,241,255,0.6);
  padding: 10px 20px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.pt-tab:hover { color: rgba(230,241,255,0.9); }
.pt-tab.active { color: #90deff; border-bottom-color: #90deff; }

/* ─── Cards ──────────────────────────────────────────────── */
.pt-section { display: flex; flex-direction: column; gap: 20px; }
.pt-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 16px;
  padding: 24px;
}
.pt-card-title {
  font-size: 16px;
  font-weight: 700;
  margin: 0 0 18px;
  color: #e6f1ff;
}
.pt-card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}
.pt-card-heading .pt-card-title { margin: 0; }
.pt-card-actions {
  margin-top: 18px;
  display: flex;
  gap: 10px;
}
.pt-card-actions-top {
  margin-top: 0;
  margin-bottom: 12px;
  justify-content: flex-end;
}

/* ─── Form ───────────────────────────────────────────────── */
.pt-form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}
.pt-field label {
  display: block;
  font-size: 12px;
  color: rgba(196,211,226,0.7);
  margin-bottom: 6px;
}
.pt-field input,
.pt-field select {
  width: 100%;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  color: #e6f1ff;
  padding: 10px 12px;
  outline: none;
  color-scheme: dark;
}
.pt-field input:focus,
.pt-field select:focus {
  border-color: rgba(144,222,255,0.5);
  box-shadow: 0 0 0 2px rgba(144,222,255,0.1);
}
.pt-field select option {
  background: #171f2b;
  color: #e6f1ff;
}
.pt-field select option:checked {
  background: #2563eb;
  color: #ffffff;
}
.pt-margin-auto-box {
  min-height: 42px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 10px;
  padding: 8px 12px;
}
.pt-margin-value {
  color: #e6f1ff;
  font-weight: 700;
  line-height: 1.2;
}
.pt-margin-meta,
.pt-muted-line {
  margin-top: 3px;
  color: rgba(196,211,226,0.6);
  font-size: 11px;
  line-height: 1.35;
  white-space: normal;
}
.pt-error-line {
  margin-top: 3px;
  color: #ff8c42;
  font-size: 11px;
  line-height: 1.35;
  white-space: normal;
  max-width: 260px;
}

/* ─── Buttons ────────────────────────────────────────────── */
.pt-btn {
  padding: 10px 20px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.06);
  color: #e6f1ff;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.15s;
}
.pt-btn:hover { background: rgba(255,255,255,0.1); }
.pt-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.pt-btn-primary { background: linear-gradient(135deg, #3877b3, #2d5f8f); border-color: rgba(56,119,179,0.5); }
.pt-btn-primary:hover { background: linear-gradient(135deg, #4088c4, #3877b3); }
.pt-btn-success { background: rgba(93,211,158,0.15); border-color: rgba(93,211,158,0.3); color: #5dd39e; }
.pt-btn-danger { background: rgba(255,90,95,0.15); border-color: rgba(255,90,95,0.3); color: #ff5a5f; }
.pt-btn-sm { padding: 6px 12px; font-size: 12px; border-radius: 8px; }
.pt-btn-group { display: flex; gap: 6px; }

/* ─── Stats Grid ─────────────────────────────────────────── */
.pt-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}
.pt-stat {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 12px;
  padding: 14px;
  text-align: center;
}
.pt-stat-label {
  font-size: 11px;
  color: rgba(196,211,226,0.6);
  margin-bottom: 6px;
}
.pt-stat-value { font-size: 18px; font-weight: 700; }

/* ─── Table ──────────────────────────────────────────────── */
.pt-table-wrap { overflow-x: auto; }
.pt-table-scroll { max-height: 400px; overflow-y: auto; }
.pt-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.pt-table th {
  text-align: left;
  padding: 10px 12px;
  color: rgba(196,211,226,0.7);
  font-weight: 600;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  white-space: nowrap;
  position: sticky;
  top: 0;
  background: rgba(8,12,19,0.95);
}
.pt-table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  white-space: nowrap;
  vertical-align: top;
}
.pt-table td .pt-btn + .pt-btn {
  margin-left: 6px;
}

/* ─── Badges ─────────────────────────────────────────────── */
.pt-side-badge, .pt-mode-badge, .pt-status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}
.pt-side-badge.buy { background: rgba(93,211,158,0.15); color: #5dd39e; }
.pt-side-badge.sell { background: rgba(255,90,95,0.15); color: #ff5a5f; }
.pt-mode-badge.realtime { background: rgba(144,222,255,0.15); color: #90deff; }
.pt-mode-badge.replay { background: rgba(255,200,100,0.15); color: #ffc864; }
.pt-status-badge.idle { background: rgba(107,125,145,0.2); color: #8a9db2; }
.pt-status-badge.running { background: rgba(93,211,158,0.15); color: #5dd39e; }
.pt-status-badge.stopped { background: rgba(255,140,66,0.15); color: #ff8c42; }
.pt-status-badge.error { background: rgba(255,90,95,0.15); color: #ff5a5f; }

/* ─── Colors ─────────────────────────────────────────────── */
.pt-positive { color: #5dd39e; }
.pt-negative { color: #ff5a5f; }
.pt-table td.pt-reason {
  min-width: 280px;
  max-width: 620px;
  overflow: visible;
  text-overflow: clip;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.45;
  font-size: 11px;
  color: rgba(196,211,226,0.68);
}
.pt-table td.pt-detail-cell {
  min-width: 420px;
  max-width: 760px;
}
.pt-detail-text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  font: inherit;
  color: inherit;
}

/* ─── Sub Section ────────────────────────────────────────── */
.pt-sub-section { margin-top: 20px; }
.pt-sub-title { font-size: 14px; font-weight: 600; margin: 0 0 12px; color: rgba(230,241,255,0.8); }

/* ─── Toast ──────────────────────────────────────────────── */
.pt-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  padding: 12px 20px;
  border-radius: 12px;
  background: rgba(11,17,26,0.95);
  border: 1px solid rgba(255,255,255,0.1);
  color: #e6f1ff;
  font-size: 13px;
  cursor: pointer;
  z-index: 100;
  animation: fadeIn 0.2s;
}
.pt-toast.success { border-color: rgba(93,211,158,0.4); }
.pt-toast.error { border-color: rgba(255,90,95,0.4); }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

/* ─── Live Dot ──────────────────────────────────────────────── */
.pt-live-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #5dd39e;
  margin-left: 8px;
  vertical-align: middle;
  animation: pulse 1.5s infinite;
}
</style>
